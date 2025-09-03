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
        """Находит треугольные арбитражные пути"""
        try:
            paths = []
            base_pairs = [
                ticker for ticker in self.api_client.tickers_set
                if ticker.endswith(base_currency) and ticker != base_currency
            ]

            logger.debug(f"Найдено {len(base_pairs)} базовых пар с {base_currency}")

            for pair1 in base_pairs:
                currency_a = pair1.replace(base_currency, '')

                # Ищем пары с currency_a
                for pair2 in self.api_client.tickers_set:
                    if pair1 == pair2:
                        continue

                    currency_b = None
                    pair2_direction = None

                    # ИСПРАВЛЕНО: Более точное определение currency_b и направления
                    if pair2.startswith(currency_a) and len(pair2) > len(currency_a):
                        currency_b = pair2[len(currency_a):]
                        pair2_direction = "sell_first"  # Продаем currency_a за currency_b
                    elif pair2.endswith(currency_a) and len(pair2) > len(currency_a):
                        currency_b = pair2[:-len(currency_a)]
                        pair2_direction = "buy_first"  # Покупаем currency_a за currency_b

                    if not currency_b or currency_b == base_currency or currency_b == currency_a:
                        continue

                    # Ищем третью пару: currency_b с base_currency
                    pair3_variants = [f"{currency_b}{base_currency}", f"{base_currency}{currency_b}"]
                    for pair3 in pair3_variants:
                        if pair3 in self.api_client.tickers_set:
                            path = [pair1, pair2, pair3]
                            if self._validate_path(path, currency_a, currency_b, base_currency):
                                paths.append(path)

                            break

            logger.debug(f"Всего найдено {len(paths)} валидных путей")
            return paths

        except Exception as e:
            logger.error(f"Ошибка при поиске треугольных путей: {e}")
            return []

    def _validate_path(self, path: List[str], currency_a: str, currency_b: str, base_currency: str) -> bool:
        """Валидирует треугольный путь"""
        try:
            if len(set(path)) != 3:
                return False

            # Проверяем, что путь действительно образует треугольник
            pair1, pair2, pair3 = path

            # pair1 должна быть currency_a/base_currency
            if not pair1 == f"{currency_a}{base_currency}":
                return False

            # pair2 должна содержать currency_a и currency_b
            if not ((currency_a in pair2 and currency_b in pair2) and
                    (pair2 == f"{currency_a}{currency_b}" or pair2 == f"{currency_b}{currency_a}")):
                return False

            # pair3 должна быть currency_b/base_currency
            if not (pair3 == f"{currency_b}{base_currency}" or pair3 == f"{base_currency}{currency_b}"):
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
        """Рассчитывает прибыль от арбитража"""
        if len(path) != 3:
            return None
        if not all(pair in orderbooks for pair in path):
            return None

        try:
            start_time = time.time()
            current_amount = INITIAL_AMOUNT
            prices = []
            directions = []
            min_volumes = []
            total_spread_cost = 0.0

            pair1, pair2, pair3 = path

            # Извлекаем валюты из пути
            base_currency = "USDT"  # Предполагаем USDT как базу
            currency_a = pair1.replace(base_currency, '')

            # Определяем currency_b из второй пары
            currency_b = None
            if pair2.startswith(currency_a):
                currency_b = pair2[len(currency_a):]
            elif pair2.endswith(currency_a):
                currency_b = pair2[:-len(currency_a)]
            else:
                logger.debug(f"Не удалось определить currency_b для пути {path}")
                return None



            # ШАГ 1: Покупаем currency_a за base_currency
            ob1 = orderbooks[pair1]
            direction1 = TradeDirection.BUY
            price1 = ob1.ask_price
            # Получаем currency_a
            amount_currency_a = (current_amount / price1) * (1 - TRADING_COMMISSION)

            prices.append(price1)
            directions.append(direction1)
            min_volumes.append(ob1.ask_qty * price1)
            total_spread_cost += ob1.spread_percent

            # ШАГ 2: Обмениваем currency_a на currency_b
            ob2 = orderbooks[pair2]

            if pair2 == f"{currency_a}{currency_b}":
                # Продаем currency_a за currency_b
                direction2 = TradeDirection.SELL
                price2 = ob2.bid_price
                amount_currency_b = (amount_currency_a * price2) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob2.bid_qty * price2)
            elif pair2 == f"{currency_b}{currency_a}":
                # Покупаем currency_b за currency_a
                direction2 = TradeDirection.BUY
                price2 = ob2.ask_price
                amount_currency_b = (amount_currency_a / price2) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob2.ask_qty * price2)
            else:
                logger.debug(f"Неизвестный формат pair2: {pair2}")
                return None

            prices.append(price2)
            directions.append(direction2)
            total_spread_cost += ob2.spread_percent

            # ШАГ 3: Продаем currency_b за base_currency
            ob3 = orderbooks[pair3]

            if pair3 == f"{currency_b}{base_currency}":
                # Продаем currency_b за base_currency
                direction3 = TradeDirection.SELL
                price3 = ob3.bid_price
                final_amount = (amount_currency_b * price3) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob3.bid_qty * price3)
            elif pair3 == f"{base_currency}{currency_b}":
                # Покупаем base_currency за currency_b (редкий случай)
                direction3 = TradeDirection.BUY
                price3 = ob3.ask_price
                final_amount = (amount_currency_b / price3) * (1 - TRADING_COMMISSION)
                min_volumes.append(ob3.ask_qty * price3)
            else:
                logger.debug(f"Неизвестный формат pair3: {pair3}")
                return None

            prices.append(price3)
            directions.append(direction3)
            total_spread_cost += ob3.spread_percent

            profit_percent = ((final_amount - INITIAL_AMOUNT) / INITIAL_AMOUNT) * 100
            min_volume_usdt = min(min_volumes) if min_volumes else 0.0
            execution_time = time.time() - start_time

            # Фильтрация по ликвидности
            if FILTER_LOW_LIQUIDITY and min_volume_usdt < MIN_LIQUIDITY_VOLUME:
                return None

            # Фильтрация по прибыльности
            if profit_percent < MIN_PROFIT_THRESHOLD:
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
        """Сканирует арбитражные возможности"""
        try:
            scan_start = time.time()

            # Получаем список тикеров, если его нет
            if not self.api_client.tickers_set:
                tickers_result = await self.api_client.get_tickers()
                if not tickers_result:
                    logger.warning("Не удалось получить список тикеров")
                    return []

            # Находим возможные пути
            paths = self.find_triangular_paths()
            if not paths:
                logger.debug("Не найдено треугольных путей")
                return []

            logger.debug(f"Найдено {len(paths)} потенциальных путей")

            # Собираем уникальные пары
            unique_pairs = set()
            for path in paths:
                unique_pairs.update(path)

            logger.debug(f"Загрузка стаканов для {len(unique_pairs)} пар")

            # Ограничиваем количество одновременных запросов
            semaphore = asyncio.Semaphore(max(1, min(50, MAX_CONCURRENT_REQUESTS // 2)))

            async def get_orderbook_with_semaphore(pair):
                """Получает стакан с семафором"""
                if self.api_client._shutdown_event.is_set():
                    return None
                try:
                    async with semaphore:
                        result = await self.api_client.get_orderbook(pair)
                        return result
                except Exception as e:
                    logger.debug(f"Ошибка получения стакана для {pair}: {e}")
                    return None
            # Получаем все стаканы
            try:
                tasks = [get_orderbook_with_semaphore(pair) for pair in unique_pairs]
                orderbook_results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Ошибка при получении стаканов: {e}")
                return []

            # Обрабатываем результаты
            orderbooks = {}
            for pair, result in zip(unique_pairs, orderbook_results):
                if isinstance(result, OrderBookData):
                    orderbooks[pair] = result
                elif isinstance(result, Exception):
                    logger.debug(f"Исключение при получении стакана {pair}: {result}")

            logger.debug(f"Загружено {len(orderbooks)} стаканов заявок из {len(unique_pairs)} запрошенных")

            # Рассчитываем арбитражные возможности
            opportunities = []
            processed_paths = 0

            for path in paths:
                try:
                    processed_paths += 1
                    opportunity = self.calculate_arbitrage_profit(path, orderbooks)
                    if opportunity:
                        opportunities.append(opportunity)
                        logger.debug(f"Найдена возможность: {path} -> {opportunity.profit_percent:.4f}%")

                        # Сохраняем в CSV
                        try:
                            self.csv_manager.save_opportunity(opportunity)
                        except Exception as e:
                            logger.debug(f"Ошибка сохранения в CSV: {e}")

                except Exception as e:
                    logger.debug(f"Ошибка расчета прибыли для пути {path}: {e}")
                    continue

            # Сортируем по прибыльности
            opportunities.sort(key=lambda x: x.profit_percent, reverse=True)

            scan_time = time.time() - scan_start
            logger.debug(f"Сканирование завершено за {scan_time:.2f}с")
            logger.debug(f"Обработано путей: {processed_paths}, найдено возможностей: {len(opportunities)}")

            return opportunities

        except Exception as e:
            logger.error(f"Критическая ошибка в scan_arbitrage_opportunities: {e}", exc_info=True)
            return []

    def print_opportunity(self, opportunity: ArbitrageOpportunity, index: int):
        """Выводит информацию о арбитражной возможности"""
        try:
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
        except Exception as e:
            logger.error(f"Ошибка печати возможности {index}: {e}")
            print(f"Ошибка отображения арбитража #{index}: {e}")