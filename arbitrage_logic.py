import time
from typing import Dict, List, Optional
from models import OrderBookData, ArbitrageOpportunity, TradeDirection
from api_client import BybitAPIClient
from csv_manager import CSVManager
from config import *
import logging
import asyncio

logger = logging.getLogger(__name__)


class ArbitrageLogic:
    def __init__(self, api_client: BybitAPIClient, csv_manager: CSVManager):
        self.api_client = api_client
        self.csv_manager = csv_manager

    def find_triangular_paths(self, base_currency: str = "USDT") -> List[List[str]]:
        """Находит треугольные арбитражные пути - ИСПРАВЛЕНО"""
        try:
            paths = []
            base_pairs = [
                ticker for ticker in self.api_client.tickers_set
                if ticker.endswith(base_currency) and ticker != base_currency
            ]

            logger.debug(f"Найдено {len(base_pairs)} базовых пар с {base_currency}")

            for pair1 in base_pairs:
                currency_a = pair1.replace(base_currency, '')

                # Ищем все пары с currency_a
                for pair2 in self.api_client.tickers_set:
                    if pair1 == pair2:
                        continue

                    currency_b = None

                    # ИСПРАВЛЕНО: Более точное определение currency_b
                    if pair2.startswith(currency_a) and pair2 != currency_a:
                        remaining = pair2[len(currency_a):]
                        # Проверяем, что оставшаяся часть - валидная валюта
                        if remaining in CROSS_CURRENCIES and remaining != base_currency:
                            currency_b = remaining
                    elif pair2.endswith(currency_a) and pair2 != currency_a:
                        remaining = pair2[:-len(currency_a)]
                        if remaining in CROSS_CURRENCIES and remaining != base_currency:
                            currency_b = remaining

                    if not currency_b or currency_b == currency_a:
                        continue

                    # Ищем третью пару: currency_b с base_currency
                    pair3_candidates = [f"{currency_b}{base_currency}", f"{base_currency}{currency_b}"]

                    for pair3 in pair3_candidates:
                        if pair3 in self.api_client.tickers_set:
                            path = [pair1, pair2, pair3]
                            if self._validate_path(path, currency_a, currency_b, base_currency):
                                paths.append(path)

                            break

            logger.debug(f"Всего найдено {len(paths)} валидных арбитражных путей")
            return paths

        except Exception as e:
            logger.error(f"Ошибка при поиске треугольных путей: {e}")
            return []

    def _validate_path(self, path: List[str], currency_a: str, currency_b: str, base_currency: str) -> bool:
        """Валидирует треугольный путь - ИСПРАВЛЕНО"""
        try:
            if len(set(path)) != 3:  # Все пары должны быть уникальными
                return False

            pair1, pair2, pair3 = path

            # Проверка 1: pair1 должна быть currency_a/base_currency
            if pair1 != f"{currency_a}{base_currency}":
                return False

            # Проверка 2: pair2 должна содержать currency_a и currency_b
            valid_pair2_formats = [f"{currency_a}{currency_b}", f"{currency_b}{currency_a}"]
            if pair2 not in valid_pair2_formats:
                return False

            # Проверка 3: pair3 должна быть currency_b/base_currency
            valid_pair3_formats = [f"{currency_b}{base_currency}", f"{base_currency}{currency_b}"]
            if pair3 not in valid_pair3_formats:
                return False

            return True

        except Exception as e:
            logger.debug(f"Ошибка валидации пути {path}: {e}")
            return False

    def calculate_arbitrage_profit(
            self,
            path: List[str],
            orderbooks: Dict[str, OrderBookData]
    ) -> Optional[ArbitrageOpportunity]:
        """Рассчитывает прибыль от арбитража - ИСПРАВЛЕНО"""
        if len(path) != 3:
            return None
        if not all(pair in orderbooks for pair in path):
            return None

        try:
            start_time = time.time()
            pair1, pair2, pair3 = path

            # Определяем валюты из путей
            base_currency = "USDT"

            # ИСПРАВЛЕНО: Правильное извлечение валют
            currency_a = pair1.replace(base_currency, '')

            # Определяем currency_b из второй пары
            currency_b = None
            if pair2.startswith(currency_a):
                currency_b = pair2[len(currency_a):]
            elif pair2.endswith(currency_a):
                currency_b = pair2[:-len(currency_a)]

            if not currency_b or currency_b not in CROSS_CURRENCIES:
                logger.debug(f"Не удалось определить currency_b для пути {path}")
                return None

            # Начальная сумма
            current_amount = float(INITIAL_AMOUNT)
            prices = []
            directions = []
            min_volumes = []
            total_spread_cost = 0.0

            # ШАГ 1: USDT -> currency_a (покупаем currency_a за USDT)
            ob1 = orderbooks[pair1]
            direction1 = TradeDirection.BUY
            price1 = ob1.ask_price  # Покупаем по ask

            # Получаем currency_a после комиссии
            amount_currency_a = (current_amount / price1) * (1 - TRADING_COMMISSION)

            prices.append(price1)
            directions.append(direction1)
            min_volumes.append(ob1.ask_qty * price1)
            total_spread_cost += ob1.spread_percent

            # ШАГ 2: currency_a -> currency_b
            ob2 = orderbooks[pair2]

            if pair2 == f"{currency_a}{currency_b}":
                # Продаем currency_a, получаем currency_b
                direction2 = TradeDirection.SELL
                price2 = ob2.bid_price  # Продаем по bid
                amount_currency_b = (amount_currency_a * price2) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob2.bid_qty * price2)
            elif pair2 == f"{currency_b}{currency_a}":
                # Покупаем currency_b за currency_a
                direction2 = TradeDirection.BUY
                price2 = ob2.ask_price  # Покупаем по ask
                amount_currency_b = (amount_currency_a / price2) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob2.ask_qty * price2)
            else:
                logger.debug(f"Неопределенный формат pair2: {pair2}")
                return None

            prices.append(price2)
            directions.append(direction2)
            total_spread_cost += ob2.spread_percent

            # ШАГ 3: currency_b -> USDT (получаем обратно USDT)
            ob3 = orderbooks[pair3]

            if pair3 == f"{currency_b}{base_currency}":
                # Продаем currency_b за USDT
                direction3 = TradeDirection.SELL
                price3 = ob3.bid_price  # Продаем по bid
                final_amount = (amount_currency_b * price3) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob3.bid_qty * price3)
            elif pair3 == f"{base_currency}{currency_b}":
                # Покупаем USDT за currency_b (редкий случай)
                direction3 = TradeDirection.BUY
                price3 = ob3.ask_price  # Покупаем по ask
                final_amount = (amount_currency_b / price3) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob3.ask_qty * price3)
            else:
                logger.debug(f"Неопределенный формат pair3: {pair3}")
                return None

            prices.append(price3)
            directions.append(direction3)
            total_spread_cost += ob3.spread_percent

            # ИСПРАВЛЕНО: Правильный расчет прибыли
            profit_absolute = final_amount - INITIAL_AMOUNT
            profit_percent = (profit_absolute / INITIAL_AMOUNT) * 100

            min_volume_usdt = min(min_volumes) if min_volumes else 0.0
            execution_time = time.time() - start_time

            # Дополнительные фильтры
            if FILTER_LOW_LIQUIDITY and min_volume_usdt < MIN_LIQUIDITY_VOLUME:
                return None

            if profit_percent < MIN_PROFIT_THRESHOLD:
                return None

            # Логируем детали для отладки
            logger.debug(f"Арбитраж {path}: {INITIAL_AMOUNT} -> {final_amount:.2f} ({profit_percent:.4f}%)")
            logger.debug(f"Путь: {currency_a} -> {currency_b} -> {base_currency}")

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
        """Сканирует арбитражные возможности - ОПТИМИЗИРОВАНО"""
        try:
            scan_start = time.time()

            # Получаем тикеры если их нет
            if not self.api_client.tickers_set:
                tickers_result = await self.api_client.get_tickers()
                if not tickers_result:
                    logger.warning("Не удалось получить список тикеров")
                    return []

            # Ищем арбитражные пути
            paths = self.find_triangular_paths()
            if not paths:
                logger.debug("Треугольные пути не найдены")
                return []

            logger.debug(f"Найдено {len(paths)} потенциальных путей для анализа")

            # Собираем уникальные пары для загрузки стаканов
            unique_pairs = set()
            for path in paths:
                unique_pairs.update(path)

            logger.debug(f"Загружаем стаканы для {len(unique_pairs)} торговых пар")

            # ОПТИМИЗАЦИЯ: Ограничиваем concurrent requests
            max_concurrent = min(MAX_CONCURRENT_REQUESTS // 3, 150)  # Безопасное значение
            semaphore = asyncio.Semaphore(max_concurrent)

            async def safe_get_orderbook(pair):
                """Безопасно получает стакан заявок"""
                try:
                    async with semaphore:
                        if self.api_client._shutdown_event.is_set():
                            return pair, None
                        result = await self.api_client.get_orderbook(pair)
                        return pair, result
                except Exception as e:
                    logger.debug(f"Ошибка получения стакана {pair}: {e}")
                    return pair, None

            # Получаем все стаканы параллельно
            tasks = [safe_get_orderbook(pair) for pair in unique_pairs]

            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Критическая ошибка при получении стаканов: {e}")
                return []

            # Обрабатываем результаты
            orderbooks = {}
            successful_loads = 0

            for result in results:
                if isinstance(result, Exception):
                    logger.debug(f"Исключение при получении стакана: {result}")
                    continue

                try:
                    pair, orderbook_data = result
                    if orderbook_data and isinstance(orderbook_data, OrderBookData):
                        orderbooks[pair] = orderbook_data
                        successful_loads += 1
                except Exception as e:
                    logger.debug(f"Ошибка обработки результата: {e}")

            logger.debug(f"Успешно загружено {successful_loads}/{len(unique_pairs)} стаканов")

            if successful_loads == 0:
                logger.warning("Не удалось загрузить ни одного стакана заявок")
                return []

            # Анализируем арбитражные возможности
            opportunities = []
            processed = 0

            for path in paths:
                try:
                    # Проверяем что все пары из пути имеют стаканы
                    if not all(pair in orderbooks for pair in path):
                        continue

                    opportunity = self.calculate_arbitrage_profit(path, orderbooks)
                    if opportunity:
                        opportunities.append(opportunity)

                        # Сохраняем в CSV
                        try:
                            self.csv_manager.save_opportunity(opportunity)
                        except Exception as e:
                            logger.debug(f"Ошибка сохранения в CSV: {e}")

                    processed += 1

                except Exception as e:
                    logger.debug(f"Ошибка анализа пути {path}: {e}")
                    continue

            # Сортируем по прибыльности
            opportunities.sort(key=lambda x: x.profit_percent, reverse=True)

            scan_time = time.time() - scan_start

            logger.debug(f"Сканирование завершено: {scan_time:.2f}с")
            logger.debug(f"Проанализировано путей: {processed}/{len(paths)}")
            logger.debug(f"Найдено возможностей: {len(opportunities)}")

            if opportunities:
                best_profit = opportunities[0].profit_percent
                logger.debug(f"Лучшая возможность: {best_profit:.4f}%")

            return opportunities

        except Exception as e:
            logger.error(f"Критическая ошибка в scan_arbitrage_opportunities: {e}", exc_info=True)
            return []

    def print_opportunity(self, opportunity: ArbitrageOpportunity, index: int):
        """Выводит информацию об арбитражной возможности - УЛУЧШЕНО"""
        try:
            print(f"\n{'=' * 70}")
            print(f"🚀 АРБИТРАЖ #{index}")
            print(f"{'=' * 70}")
            print(
                f"📈 Прибыль: {opportunity.profit_percent:.4f}% (${(INITIAL_AMOUNT * opportunity.profit_percent / 100):.2f})")
            print(f"💰 Мин. объем: ${opportunity.min_volume_usdt:.2f} USDT")
            print(f"⚡ Время: {opportunity.execution_time * 1000:.1f}ms")
            print(f"📊 Спреды: {opportunity.spread_cost:.3f}%")

            # Извлекаем валюты для понимания
            base_currency = "USDT"
            currency_a = opportunity.path[0].replace(base_currency, '')

            currency_b = None
            pair2 = opportunity.path[1]
            if pair2.startswith(currency_a):
                currency_b = pair2[len(currency_a):]
            elif pair2.endswith(currency_a):
                currency_b = pair2[:-len(currency_a)]

            print(f"🔄 Маршрут: {base_currency} → {currency_a} → {currency_b} → {base_currency}")
            print(f"\n📋 Детальный план:")

            step_names = [f"{base_currency}→{currency_a}", f"{currency_a}→{currency_b}",
                          f"{currency_b}→{base_currency}"]

            for i, (pair, direction, price, step_name) in enumerate(zip(
                    opportunity.path, opportunity.directions, opportunity.prices, step_names
            ), 1):
                action = "ПОКУПКА" if direction == TradeDirection.BUY else "ПРОДАЖА"
                print(f"   {i}. {step_name}: {action} {pair} по ${price:.8f}")

            print(f"{'=' * 70}")

        except Exception as e:
            logger.error(f"Ошибка отображения возможности #{index}: {e}")
            print(f"❌ Ошибка отображения арбитража #{index}")