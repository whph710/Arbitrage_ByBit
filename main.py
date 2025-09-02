#!/usr/bin/env python3
"""
Арбитражный бот для Bybit - main.py (полный файл)
Включает: rate limiter, graceful shutdown, улучшения кэширования и обработку сигналов.
"""

import aiohttp
import asyncio
import logging
import sqlite3
import json
import time
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, NamedTuple, Set
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

# Импорт настроек
try:
    from config import *
except ImportError:
    print("ОШИБКА: Файл config.py не найден!")
    print("Убедитесь, что файл config.py находится в той же папке.")
    sys.exit(1)


# =============================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# =============================================================================

def setup_logging():
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handlers.append(console_handler)
    if LOG_FILE:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_SIZE,
            backupCount=LOG_BACKUP_COUNT
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handlers.append(file_handler)
    logging.basicConfig(level=log_level, handlers=handlers, format=LOG_FORMAT)


setup_logging()
logger = logging.getLogger(__name__)


# =============================================================================
# СТРУКТУРЫ ДАННЫХ
# =============================================================================

class TradeDirection(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class OrderBookData:
    bid_price: float
    ask_price: float
    bid_qty: float
    ask_qty: float
    spread_percent: float = 0.0

    def __post_init__(self):
        if self.ask_price > 0 and self.bid_price > 0:
            self.spread_percent = ((self.ask_price - self.bid_price) / self.bid_price) * 100


class ArbitrageOpportunity(NamedTuple):
    path: List[str]
    directions: List[TradeDirection]
    prices: List[float]
    profit_percent: float
    min_volume_usdt: float
    execution_time: float
    spread_cost: float


# =============================================================================
# БАЗА ДАННЫХ
# =============================================================================

class DatabaseManager:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS opportunities
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                path TEXT NOT NULL,
                profit_percent REAL NOT NULL,
                min_volume_usdt REAL NOT NULL,
                prices TEXT NOT NULL,
                directions TEXT NOT NULL,
                execution_time REAL DEFAULT 0,
                spread_cost REAL DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats
            (
                date DATE PRIMARY KEY,
                total_opportunities INTEGER DEFAULT 0,
                avg_profit REAL DEFAULT 0,
                max_profit REAL DEFAULT 0,
                total_volume REAL DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON opportunities(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_profit ON opportunities(profit_percent)')
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")

    def save_opportunity(self, opportunity: ArbitrageOpportunity):
        if not SAVE_ALL_OPPORTUNITIES and opportunity.profit_percent <= 0:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO opportunities
                (path, profit_percent, min_volume_usdt, prices, directions, execution_time, spread_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                json.dumps(opportunity.path),
                opportunity.profit_percent,
                opportunity.min_volume_usdt,
                json.dumps(opportunity.prices),
                json.dumps([d.value for d in opportunity.directions]),
                opportunity.execution_time,
                opportunity.spread_cost
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения в БД: {e}")
        finally:
            conn.close()

    def cleanup_old_records(self):
        if not AUTO_CLEANUP_ENABLED:
            return
        cutoff_date = datetime.now() - timedelta(days=HISTORY_RETENTION_DAYS)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM opportunities WHERE timestamp < ?', (cutoff_date.isoformat(),))
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Удалено {deleted} старых записей из БД")
        except Exception as e:
            logger.error(f"Ошибка очистки БД: {e}")
        finally:
            conn.close()


# =============================================================================
# ОСНОВНОЙ КЛАСС API
# =============================================================================

class BybitArbitrageBot:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.tickers_set: Set[str] = set()
        self.orderbook_cache: Dict[str, Tuple[OrderBookData, float]] = {}
        self.db_manager = DatabaseManager()
        self.last_cleanup = time.time()
        self.stats = {
            'total_scans': 0,
            'opportunities_found': 0,
            'api_errors': 0,
            'last_scan_time': 0
        }
        self._rate_limit = API_RATE_LIMIT
        self._rate_window: List[float] = []
        self._rate_lock = asyncio.Lock()
        self._http_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._shutdown = asyncio.Event()
        # threadpool for blocking tasks (playsound)
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def start(self):
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, ssl=SSL_VERIFY)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        logger.info("Арбитражный бот запущен")
        return self

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
        self._executor.shutdown(wait=False)
        logger.info("Арбитражный бот остановлен")

    async def _acquire_rate_slot(self):
        async with self._rate_lock:
            now = time.time()
            self._rate_window = [t for t in self._rate_window if now - t < 60]
            while len(self._rate_window) >= self._rate_limit:
                await asyncio.sleep(0.1)
                now = time.time()
                self._rate_window = [t for t in self._rate_window if now - t < 60]
            self._rate_window.append(now)

    async def get_tickers(self) -> Set[str]:
        url = f"{BYBIT_BASE_URL}/market/tickers"
        params = {"category": "spot"}
        for attempt in range(API_RETRY_ATTEMPTS):
            try:
                await self._acquire_rate_slot()
                async with self._http_semaphore:
                    async with self.session.get(url, params=params) as response:
                        if response.status != 200:
                            logger.warning(f"API вернул статус {response.status}")
                            continue
                        data = await response.json()
                if not data.get("result") or not data["result"].get("list"):
                    logger.warning("Некорректный формат ответа API")
                    continue
                all_tickers = [pair["symbol"] for pair in data["result"]["list"]]
                filtered_tickers = self._filter_tickers(all_tickers)
                self.tickers_set = set(filtered_tickers)
                logger.info(f"Загружено {len(self.tickers_set)} торговых пар")
                return self.tickers_set
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Ошибка получения тикеров (попытка {attempt + 1}): {e}")
                if attempt < API_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(API_RETRY_DELAY)
                else:
                    self.stats['api_errors'] += 1
        return set()

    def _filter_tickers(self, tickers: List[str]) -> List[str]:
        filtered = []
        for ticker in tickers:
            excluded = any(exc == ticker or ticker.endswith(exc) or ticker.startswith(exc) for exc in EXCLUDED_CURRENCIES)
            if excluded:
                continue
            base_currency_found = any(ticker.endswith(base) for base in CROSS_CURRENCIES)
            if base_currency_found:
                filtered.append(ticker)
        return filtered

    async def get_orderbook(self, symbol: str) -> Optional[OrderBookData]:
        if USE_ORDERBOOK_CACHE and symbol in self.orderbook_cache:
            data, timestamp = self.orderbook_cache[symbol]
            if time.time() - timestamp < ORDERBOOK_CACHE_TTL:
                return data
        url = f"{BYBIT_BASE_URL}/market/orderbook"
        params = {
            "category": "spot",
            "symbol": symbol,
            "limit": ORDERBOOK_LEVELS if ORDERBOOK_DEPTH_ANALYSIS else 1
        }
        try:
            await self._acquire_rate_slot()
            async with self._http_semaphore:
                async with self.session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.debug(f"Orderbook {symbol} returned status {response.status}")
                        return None
                    data = await response.json()
            result = data.get("result", {})
            bids = result.get("b", [])
            asks = result.get("a", [])
            if not bids or not asks:
                return None
            orderbook = OrderBookData(
                bid_price=float(bids[0][0]),
                ask_price=float(asks[0][0]),
                bid_qty=float(bids[0][1]),
                ask_qty=float(asks[0][1])
            )
            if FILTER_LOW_LIQUIDITY and orderbook.spread_percent > MAX_SPREAD_PERCENT:
                return None
            if USE_ORDERBOOK_CACHE:
                self.orderbook_cache[symbol] = (orderbook, time.time())
            return orderbook
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"Ошибка получения стакана для {symbol}: {e}")
            return None

    def find_triangular_paths(self, base_currency: str = "USDT") -> List[List[str]]:
        paths = []
        base_pairs = [
            ticker for ticker in self.tickers_set
            if ticker.endswith(base_currency) and ticker != base_currency
        ]
        for pair1 in base_pairs:
            currency_a = pair1.replace(base_currency, '')
            for pair2 in self.tickers_set:
                if pair1 == pair2:
                    continue
                currency_b = None
                if pair2.startswith(currency_a):
                    currency_b = pair2.replace(currency_a, '')
                elif pair2.endswith(currency_a):
                    currency_b = pair2.replace(currency_a, '')
                if not currency_b or currency_b == base_currency:
                    continue
                pair3_variants = [f"{currency_b}{base_currency}", f"{base_currency}{currency_b}"]
                for pair3 in pair3_variants:
                    if pair3 in self.tickers_set:
                        path = [pair1, pair2, pair3]
                        if self._validate_path(path):
                            paths.append(path)
                        break
        return paths

    def _validate_path(self, path: List[str]) -> bool:
        if len(set(path)) != 3:
            return False
        return True

    def calculate_arbitrage_profit(
            self,
            path: List[str],
            orderbooks: Dict[str, OrderBookData]
    ) -> Optional[ArbitrageOpportunity]:
        if len(path) != 3:
            return None
        if not all(pair in orderbooks for pair in path):
            return None
        start_time = time.time()
        current_amount = INITIAL_AMOUNT
        prices = []
        directions = []
        min_volumes = []
        total_spread_cost = 0.0
        try:
            pair1 = path[0]
            ob1 = orderbooks[pair1]
            direction1 = TradeDirection.BUY
            price1 = ob1.ask_price
            current_amount = (current_amount / price1) * (1 - TRADING_COMMISSION)
            prices.append(price1)
            directions.append(direction1)
            min_volumes.append(ob1.ask_qty * price1)
            total_spread_cost += ob1.spread_percent
            pair2 = path[1]
            ob2 = orderbooks[pair2]
            currency_a = pair1.replace('USDT', '')
            if pair2.startswith(currency_a):
                direction2 = TradeDirection.SELL
                price2 = ob2.bid_price
                current_amount = (current_amount * price2) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob2.bid_qty * price2)
            else:
                direction2 = TradeDirection.BUY
                price2 = ob2.ask_price
                current_amount = (current_amount / price2) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob2.ask_qty * price2)
            prices.append(price2)
            directions.append(direction2)
            total_spread_cost += ob2.spread_percent
            pair3 = path[2]
            ob3 = orderbooks[pair3]
            direction3 = TradeDirection.SELL
            price3 = ob3.bid_price
            final_amount = (current_amount * price3) * (1 - TRADING_COMMISSION)
            prices.append(price3)
            directions.append(direction3)
            min_volumes.append(ob3.bid_qty * price3)
            total_spread_cost += ob3.spread_percent
            profit_percent = ((final_amount - INITIAL_AMOUNT) / INITIAL_AMOUNT) * 100
            min_volume_usdt = min(min_volumes) if min_volumes else 0.0
            execution_time = time.time() - start_time
            if FILTER_LOW_LIQUIDITY and min_volume_usdt < MIN_LIQUIDITY_VOLUME:
                return None
            return ArbitrageOpportunity(
                path=path,
                directions=directions,
                prices=prices,
                profit_percent=profit_percent,
                min_volume_usdt=min_volume_usdt,
                execution_time=execution_time,
                spread_cost=total_spread_cost
            )
        except Exception as e:
            logger.debug(f"Ошибка расчета для пути {path}: {e}")
            return None

    async def scan_arbitrage_opportunities(self) -> List[ArbitrageOpportunity]:
        scan_start = time.time()
        if not self.tickers_set:
            await self.get_tickers()
        paths = self.find_triangular_paths()
        logger.debug(f"Найдено {len(paths)} потенциальных путей")
        unique_pairs = set()
        for path in paths:
            unique_pairs.update(path)
        logger.debug(f"Загрузка стаканов для {len(unique_pairs)} пар")
        semaphore = asyncio.Semaphore(max(1, MAX_CONCURRENT_REQUESTS // 2))
        async def get_orderbook_with_semaphore(pair):
            async with semaphore:
                return await self.get_orderbook(pair)
        tasks = [get_orderbook_with_semaphore(pair) for pair in unique_pairs]
        orderbook_results = await asyncio.gather(*tasks, return_exceptions=True)
        orderbooks = {}
        for pair, result in zip(unique_pairs, orderbook_results):
            if isinstance(result, OrderBookData):
                orderbooks[pair] = result
        logger.debug(f"Загружено {len(orderbooks)} стаканов заявок")
        opportunities = []
        for path in paths:
            opportunity = self.calculate_arbitrage_profit(path, orderbooks)
            if opportunity and opportunity.profit_percent >= MIN_PROFIT_THRESHOLD:
                opportunities.append(opportunity)
                self.db_manager.save_opportunity(opportunity)
        opportunities.sort(key=lambda x: x.profit_percent, reverse=True)
        self.stats['total_scans'] += 1
        self.stats['opportunities_found'] += len(opportunities)
        self.stats['last_scan_time'] = time.time() - scan_start
        return opportunities

    def print_opportunity(self, opportunity: ArbitrageOpportunity, index: int):
        print(f"\n{'=' * 60}")
        print(f"🚀 АРБИТРАЖ #{index}")
        print(f"{'=' * 60}")
        print(f"📈 Прибыль: {opportunity.profit_percent:.3f}%")
        print(f"💰 Мин. капитал: ${opportunity.min_volume_usdt:.2f}")
        print(f"⚡ Время расчета: {opportunity.execution_time * 1000:.1f}ms")
        print(f"📊 Стоимость спредов: {opportunity.spread_cost:.3f}%")
        print(f"\n🔄 Торговый путь:")
        for i, (pair, direction, price) in enumerate(zip(
                opportunity.path, opportunity.directions, opportunity.prices
        ), 1):
            action = "ПОКУПКА" if direction == TradeDirection.BUY else "ПРОДАЖА"
            print(f"  {i}. {pair}: {action} по ${price:.8f}")
        print(f"{'=' * 60}")

    def print_statistics(self):
        print(f"\n📊 СТАТИСТИКА БОТА:")
        print(f"   Всего сканирований: {self.stats['total_scans']}")
        print(f"   Найдено возможностей: {self.stats['opportunities_found']}")
        print(f"   Ошибки API: {self.stats['api_errors']}")
        print(f"   Время последнего сканирования: {self.stats['last_scan_time']:.2f}s")
        print(f"   Торговых пар в работе: {len(self.tickers_set)}")

    async def cleanup_routine(self):
        current_time = time.time()
        if current_time - self.last_cleanup > 3600:
            self.db_manager.cleanup_old_records()
            self.last_cleanup = current_time
            if USE_ORDERBOOK_CACHE:
                expired_keys = [
                    key for key, (data, timestamp) in self.orderbook_cache.items()
                    if current_time - timestamp > ORDERBOOK_CACHE_TTL * 10
                ]
                for key in expired_keys:
                    del self.orderbook_cache[key]

    async def _play_sound(self, path):
        try:
            import playsound
            await asyncio.get_event_loop().run_in_executor(self._executor, playsound.playsound, path, False)
        except Exception as e:
            logger.debug(f"Ошибка воспроизведения звука: {e}")

    def request_shutdown(self):
        self._shutdown.set()


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

async def main_loop(shutdown_event: asyncio.Event):
    bot = BybitArbitrageBot()
    try:
        await bot.start()
        logger.info(f"Начинаем мониторинг арбитража (мин. прибыль: {MIN_PROFIT_THRESHOLD}%)")
        while not shutdown_event.is_set():
            try:
                opportunities = await bot.scan_arbitrage_opportunities()
                if opportunities:
                    print(f"\n🎯 Найдено {len(opportunities)} арбитражных возможностей!")
                    for i, opportunity in enumerate(opportunities[:MAX_OPPORTUNITIES_DISPLAY], 1):
                        if CONSOLE_NOTIFICATIONS:
                            bot.print_opportunity(opportunity, i)
                        if SOUND_NOTIFICATIONS and opportunity.profit_percent > 0.5:
                            asyncio.create_task(bot._play_sound(SOUND_FILE_PATH))
                else:
                    logger.debug("Прибыльных арбитражных возможностей не найдено")
                if bot.stats['total_scans'] % 10 == 0:
                    bot.print_statistics()
                await bot.cleanup_routine()
                await asyncio.wait_for(shutdown_event.wait(), timeout=SCAN_INTERVAL)
            except asyncio.TimeoutError:
                continue
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки (KeyboardInterrupt)...")
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в главном цикле: {e}")
                await asyncio.sleep(ERROR_RETRY_INTERVAL)
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
    finally:
        await bot.close()
        logger.info("Программа завершена")


def _setup_signal_handlers(loop, shutdown_event: asyncio.Event):
    try:
        loop.add_signal_handler(signal.SIGTERM, shutdown_event.set)
        loop.add_signal_handler(signal.SIGINT, shutdown_event.set)
    except NotImplementedError:
        # Windows compatibility fallback
        signal.signal(signal.SIGINT, lambda s, f: shutdown_event.set())


def check_dependencies():
    required_packages = ['aiohttp', 'sqlite3']
    optional_packages = {'playsound': SOUND_NOTIFICATIONS}
    missing_required = []
    missing_optional = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_required.append(package)
    for package, needed in optional_packages.items():
        if needed:
            try:
                __import__(package)
            except ImportError:
                missing_optional.append(package)
    if missing_required:
        logger.critical(f"Отсутствуют обязательные пакеты: {missing_required}")
        logger.critical("Установите их: pip install aiohttp")
        return False
    if missing_optional:
        logger.warning(f"Отсутствуют опциональные пакеты: {missing_optional}")
        logger.warning("Установите их: pip install playsound")
    return True


def print_startup_info():
    print("=" * 80)
    print("🚀 АРБИТРАЖНЫЙ БОТ BYBIT - ЗАПУСК")
    print("=" * 80)
    print(f"📊 Минимальная прибыль: {MIN_PROFIT_THRESHOLD}%")
    print(f"💰 Комиссия торгов: {TRADING_COMMISSION * 100}%")
    print(f"⏱️  Интервал сканирования: {SCAN_INTERVAL}s")
    print(f"🔢 Максимум показываемых возможностей: {MAX_OPPORTUNITIES_DISPLAY}")
    print(f"💱 Базовые валюты: {', '.join(CROSS_CURRENCIES)}")
    print(f"🗃️  База данных: {DATABASE_PATH}")
    print(f"📝 Уровень логирования: {LOG_LEVEL}")
    print("=" * 80)
    print("💡 Для остановки нажмите Ctrl+C")
    print("=" * 80)


if __name__ == "__main__":
    if not check_dependencies():
        sys.exit(1)
    print_startup_info()
    shutdown_event = asyncio.Event()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _setup_signal_handlers(loop, shutdown_event)
    try:
        loop.run_until_complete(main_loop(shutdown_event))
    except KeyboardInterrupt:
        pass
    finally:
        # попытка аккуратно завершить все задачи
        tasks = asyncio.all_tasks(loop=loop)
        for t in tasks:
            t.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        except Exception:
            pass
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
