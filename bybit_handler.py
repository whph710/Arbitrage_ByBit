import aiohttp
import asyncio
import json
from typing import Dict, Set, Tuple, Optional, Callable
from collections import deque
from datetime import datetime
from configs import (
    BYBIT_API_URL, BYBIT_WS_URL, REQUEST_TIMEOUT, ENABLE_COIN_FILTER,
    BLACKLIST_COINS, WHITELIST_COINS, MIN_24H_VOLUME_USDT,
    MIN_LIQUIDITY_SCORE, USE_ONLY_TOP_LIQUID_COINS, WEBSOCKET_ENABLED,
    WEBSOCKET_RECONNECT_DELAY, WEBSOCKET_PING_INTERVAL
)


class BybitClientAsync:
    """Асинхронный клиент для Bybit с WebSocket поддержкой"""

    def __init__(self):
        self.base_url = BYBIT_API_URL
        self.ws_url = BYBIT_WS_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/8.0)',
            'Accept': 'application/json'
        }
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = None
        self.ws_session = None
        self.ws_connection = None

        # Структуры данных
        self.usdt_pairs: Dict[str, float] = {}
        self.coins: Set[str] = set()
        self.trading_pairs: Dict[Tuple[str, str], float] = {}
        self.pair_volumes: Dict[Tuple[str, str], float] = {}
        self.pair_liquidity: Dict[Tuple[str, str], float] = {}

        # WebSocket данные
        self.ws_prices: Dict[str, float] = {}
        self.price_updates: deque = deque(maxlen=1000)
        self.last_update_time: Dict[str, datetime] = {}

        # Статистика
        self.filtered_by_volume = 0
        self.filtered_by_liquidity = 0
        self.ws_updates_count = 0
        self.ws_running = False

        # Callback для обновлений
        self.on_price_update: Optional[Callable] = None

    async def __aenter__(self):
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def create_session(self):
        """Создаёт HTTP и WebSocket сессии"""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers, timeout=self.timeout)

        if WEBSOCKET_ENABLED and self.ws_session is None:
            self.ws_session = aiohttp.ClientSession()

    async def close(self):
        """Закрывает все соединения"""
        self.ws_running = False

        if self.ws_connection:
            await self.ws_connection.close()
            self.ws_connection = None

        if self.ws_session:
            await self.ws_session.close()
            self.ws_session = None

        if self.session:
            await self.session.close()
            self.session = None

    def _should_include_coin(self, coin: str) -> bool:
        """Проверяет, должна ли монета быть включена в анализ"""
        if not ENABLE_COIN_FILTER:
            return True
        if WHITELIST_COINS:
            return coin in WHITELIST_COINS
        return coin not in BLACKLIST_COINS

    def _calculate_liquidity_score(
            self,
            volume_24h: float,
            turnover_24h: float,
            bid_ask_spread_pct: float = None
    ) -> float:
        """Рассчитывает оценку ликвидности пары (0-100)"""
        score = 0.0

        # Оценка по объёму
        if volume_24h >= 5000000:
            score += 50
        elif volume_24h >= 1000000:
            score += 45
        elif volume_24h >= 500000:
            score += 40
        elif volume_24h >= 100000:
            score += 30
        elif volume_24h >= 50000:
            score += 20

        # Оценка по обороту
        if turnover_24h >= 50000000:
            score += 30
        elif turnover_24h >= 10000000:
            score += 25
        elif turnover_24h >= 5000000:
            score += 20
        elif turnover_24h >= 1000000:
            score += 15
        elif turnover_24h >= 500000:
            score += 10

        # Оценка по спреду
        if bid_ask_spread_pct is not None:
            if bid_ask_spread_pct <= 0.02:
                score += 20
            elif bid_ask_spread_pct <= 0.05:
                score += 15
            elif bid_ask_spread_pct <= 0.1:
                score += 10
            elif bid_ask_spread_pct <= 0.2:
                score += 5
        else:
            score += 10

        return min(score, 100.0)

    async def load_usdt_pairs(self):
        """Загружает все торговые пары с Bybit с фильтрацией"""
        if self.session is None:
            await self.create_session()

        try:
            print("[Bybit] 📥 Загрузка торговых пар...")

            url = f"{self.base_url}/v5/market/tickers"
            params = {'category': 'spot'}

            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

            # Очистка данных
            self.usdt_pairs.clear()
            self.coins.clear()
            self.trading_pairs.clear()
            self.pair_volumes.clear()
            self.pair_liquidity.clear()

            filtered_count = 0
            self.filtered_by_volume = 0
            self.filtered_by_liquidity = 0

            result_list = data.get('result', {}).get('list', [])
            quote_currencies = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB', 'BUSD', 'DAI', 'TRX', 'XRP', 'SOL', 'DOGE']

            all_pairs = []

            for ticker in result_list:
                symbol = ticker.get('symbol', '').replace('/', '').upper()

                try:
                    price = float(ticker.get('lastPrice', 0))
                    if price <= 0:
                        continue

                    volume_24h = float(ticker.get('volume24h', 0))
                    turnover_24h = float(ticker.get('turnover24h', 0))
                    bid = float(ticker.get('bid1Price', 0))
                    ask = float(ticker.get('ask1Price', 0))

                    bid_ask_spread_pct = None
                    if bid > 0 and ask > 0:
                        bid_ask_spread_pct = ((ask - bid) / bid) * 100

                except (ValueError, TypeError):
                    continue

                # Определяем base и quote
                base = None
                quote = None
                for potential_quote in quote_currencies:
                    if symbol.endswith(potential_quote) and len(symbol) > len(potential_quote):
                        quote = potential_quote
                        base = symbol[:-len(potential_quote)]
                        break

                if not base or not quote:
                    continue

                # Применяем фильтр монет
                if not self._should_include_coin(base) or not self._should_include_coin(quote):
                    filtered_count += 1
                    continue

                # Рассчитываем объём в USDT
                volume_usdt = turnover_24h if quote == 'USDT' else volume_24h * price

                # Оценка ликвидности
                liquidity_score = self._calculate_liquidity_score(
                    volume_24h, turnover_24h, bid_ask_spread_pct
                )

                all_pairs.append({
                    'base': base,
                    'quote': quote,
                    'price': price,
                    'volume_usdt': volume_usdt,
                    'liquidity_score': liquidity_score,
                    'symbol': symbol
                })

            # Фильтруем и сортируем по ликвидности
            filtered_pairs = []
            for pair in all_pairs:
                if pair['volume_usdt'] < MIN_24H_VOLUME_USDT:
                    self.filtered_by_volume += 1
                    continue

                if pair['liquidity_score'] < MIN_LIQUIDITY_SCORE:
                    self.filtered_by_liquidity += 1
                    continue

                filtered_pairs.append(pair)

            # Сортируем по ликвидности
            filtered_pairs.sort(key=lambda x: x['liquidity_score'], reverse=True)

            # Берём топ монет если указано
            if USE_ONLY_TOP_LIQUID_COINS > 0:
                filtered_pairs = filtered_pairs[:USE_ONLY_TOP_LIQUID_COINS * 3]  # *3 потому что одна монета имеет несколько пар

            # Сохраняем данные
            for pair in filtered_pairs:
                base = pair['base']
                quote = pair['quote']
                price = pair['price']
                volume_usdt = pair['volume_usdt']
                liquidity_score = pair['liquidity_score']

                self.trading_pairs[(base, quote)] = price
                self.pair_volumes[(base, quote)] = volume_usdt
                self.pair_liquidity[(base, quote)] = liquidity_score
                self.coins.add(base)
                self.coins.add(quote)

                if quote == 'USDT':
                    self.usdt_pairs[base] = price

            print(f"[Bybit] ✓ Загружено {len(self.usdt_pairs)} USDT-пар")
            print(f"[Bybit] ✓ Всего уникальных монет: {len(self.coins)}")
            print(f"[Bybit] ✓ Всего торговых пар (ликвидных): {len(self.trading_pairs)}")

            if filtered_count > 0:
                print(f"[Bybit] 🔍 Отфильтровано по white/blacklist: {filtered_count}")
            if self.filtered_by_volume > 0:
                print(f"[Bybit] 📉 Отфильтровано по объёму (<${MIN_24H_VOLUME_USDT:,.0f}): {self.filtered_by_volume}")
            if self.filtered_by_liquidity > 0:
                print(f"[Bybit] 💧 Отфильтровано по ликвидности (score <{MIN_LIQUIDITY_SCORE}): {self.filtered_by_liquidity}")

            # Топ-10 самых ликвидных пар
            top_liquid = sorted(self.pair_liquidity.items(), key=lambda x: x[1], reverse=True)[:10]
            print(f"\n[Bybit] 🏆 Топ-10 самых ликвидных пар:")
            for (base, quote), score in top_liquid:
                volume = self.pair_volumes.get((base, quote), 0)
                price = self.trading_pairs.get((base, quote), 0)
                print(f"        {base}/{quote}: оценка {score:.1f}, объём ${volume:,.0f}, цена {price:.8f}")

            # Инициализируем WebSocket данные
            self.ws_prices = self.usdt_pairs.copy()

        except Exception as e:
            print(f"[Bybit] ❌ Ошибка при загрузке пар: {e}")

    async def start_websocket(self, callback: Optional[Callable] = None):
        """Запускает WebSocket соединение для обновления цен в реальном времени"""
        if not WEBSOCKET_ENABLED:
            print("[Bybit] WebSocket отключен в конфигурации")
            return

        if not self.usdt_pairs:
            print("[Bybit] ⚠️  Сначала загрузите пары через load_usdt_pairs()")
            return

        self.on_price_update = callback
        self.ws_running = True

        print(f"\n[Bybit] 🔌 Запуск WebSocket для {len(self.usdt_pairs)} пар...")

        # Подписываемся на тикеры
        symbols = [f"{coin}USDT" for coin in self.usdt_pairs.keys()]

        # Разбиваем на батчи (максимум 50 пар в одной подписке)
        batch_size = 50
        tasks = []

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            tasks.append(self._websocket_worker(batch))

        print(f"[Bybit] 📡 Создано {len(tasks)} WebSocket соединений")

        # Запускаем все воркеры
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _websocket_worker(self, symbols: list):
        """Воркер для обработки WebSocket подписки на группу символов"""
        while self.ws_running:
            try:
                async with self.ws_session.ws_connect(self.ws_url) as ws:
                    # Подписываемся на тикеры
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [f"tickers.{symbol}" for symbol in symbols]
                    }
                    await ws.send_json(subscribe_msg)

                    print(f"[Bybit WS] ✓ Подписка на {len(symbols)} символов")

                    # Обрабатываем сообщения
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_ws_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            print(f"[Bybit WS] ⚠️  Соединение закрыто")
                            break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print(f"[Bybit WS] ❌ Ошибка: {ws.exception()}")
                            break

            except Exception as e:
                if self.ws_running:
                    print(f"[Bybit WS] ❌ Ошибка соединения: {e}")
                    print(f"[Bybit WS] 🔄 Переподключение через {WEBSOCKET_RECONNECT_DELAY}с...")
                    await asyncio.sleep(WEBSOCKET_RECONNECT_DELAY)
                else:
                    break

    async def _handle_ws_message(self, data: str):
        """Обрабатывает сообщения от WebSocket"""
        try:
            msg = json.loads(data)

            # Пропускаем служебные сообщения
            if 'op' in msg:
                return

            # Обрабатываем обновление тикера
            if 'topic' in msg and msg['topic'].startswith('tickers.'):
                ticker_data = msg.get('data', {})
                symbol = ticker_data.get('symbol', '').upper()

                # Извлекаем base монету
                if symbol.endswith('USDT'):
                    coin = symbol[:-4]
                    price = float(ticker_data.get('lastPrice', 0))

                    if price > 0 and coin in self.usdt_pairs:
                        old_price = self.ws_prices.get(coin, 0)
                        self.ws_prices[coin] = price
                        self.usdt_pairs[coin] = price
                        self.last_update_time[coin] = datetime.now()
                        self.ws_updates_count += 1

                        # Логируем каждые 100 обновлений
                        if self.ws_updates_count % 100 == 0:
                            print(f"[Bybit WS] 📊 Обработано обновлений: {self.ws_updates_count}")

                        # Вызываем callback если задан
                        if self.on_price_update and abs(price - old_price) / old_price > 0.001:  # > 0.1% изменение
                            await self.on_price_update(coin, old_price, price)

        except Exception as e:
            print(f"[Bybit WS] ⚠️  Ошибка обработки сообщения: {e}")

    def get_price(self, base: str, quote: str) -> Optional[float]:
        """Получает цену для пары BASE/QUOTE"""
        direct = self.trading_pairs.get((base, quote))
        if direct is not None:
            return direct
        reverse = self.trading_pairs.get((quote, base))
        if reverse is not None and reverse > 0:
            return 1.0 / reverse
        return None

    def get_liquidity_score(self, base: str, quote: str) -> float:
        """Получает оценку ликвидности пары"""
        score = self.pair_liquidity.get((base, quote))
        if score is not None:
            return score
        score = self.pair_liquidity.get((quote, base))
        return score if score is not None else 0.0

    def get_volume_24h(self, base: str, quote: str) -> float:
        """Получает объём торгов за 24ч в USDT"""
        volume = self.pair_volumes.get((base, quote))
        if volume is not None:
            return volume
        volume = self.pair_volumes.get((quote, base))
        return volume if volume is not None else 0.0

    def has_trading_pair(self, base: str, quote: str) -> bool:
        """Проверяет наличие торговой пары"""
        return self.get_price(base, quote) is not None

    def is_liquid_pair(self, base: str, quote: str) -> bool:
        """Проверяет, является ли пара ликвидной"""
        return self.get_liquidity_score(base, quote) >= MIN_LIQUIDITY_SCORE

    async def get_usdt_tickers(self) -> Dict[str, float]:
        """Получает все USDT-пары"""
        if not self.usdt_pairs:
            await self.load_usdt_pairs()
        return self.usdt_pairs

    def get_available_quotes_for(self, base: str) -> Set[str]:
        """Возвращает все валюты, с которыми может торговаться base"""
        quotes = set()
        for (b, q) in self.trading_pairs.keys():
            if b == base:
                quotes.add(q)
            elif q == base:
                quotes.add(b)
        return quotes

    def get_liquid_usdt_coins(self) -> list:
        """Возвращает список монет с USDT-парами, отсортированных по ликвидности"""
        coins_with_scores = []
        for coin in self.usdt_pairs.keys():
            score = self.get_liquidity_score(coin, 'USDT')
            volume = self.get_volume_24h(coin, 'USDT')
            coins_with_scores.append((coin, score, volume))
        coins_with_scores.sort(key=lambda x: x[1], reverse=True)
        return [coin for coin, score, volume in coins_with_scores]

    def get_ws_statistics(self) -> Dict:
        """Возвращает статистику WebSocket"""
        return {
            'running': self.ws_running,
            'updates_count': self.ws_updates_count,
            'tracked_pairs': len(self.ws_prices),
            'last_updates': len([t for t in self.last_update_time.values()
                               if (datetime.now() - t).seconds < 60])
        }