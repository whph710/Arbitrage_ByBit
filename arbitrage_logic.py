import time
from typing import Dict, List, Optional
from models import OrderBookData, ArbitrageOpportunity, TradeDirection
from api_client import BybitAPIClient
from csv_manager import CSVManager
from config import *
import logging
import asyncio  # Добавлен импорт asyncio

logger = logging.getLogger(__name__)

class ArbitrageLogic:
    def __init__(self, api_client: BybitAPIClient, csv_manager: CSVManager):
        self.api_client = api_client
        self.csv_manager = csv_manager

    def find_triangular_paths(self, base_currency: str = "USDT") -> List[List[str]]:
        paths = []
        base_pairs = [
            ticker for ticker in self.api_client.tickers_set
            if ticker.endswith(base_currency) and ticker != base_currency
        ]
        for pair1 in base_pairs:
            currency_a = pair1.replace(base_currency, '')
            for pair2 in self.api_client.tickers_set:
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
                    if pair3 in self.api_client.tickers_set:
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
        if not self.api_client.tickers_set:
            await self.api_client.get_tickers()
        paths = self.find_triangular_paths()
        logger.debug(f"Найдено {len(paths)} потенциальных путей")
        unique_pairs = set()
        for path in paths:
            unique_pairs.update(path)
        logger.debug(f"Загрузка стаканов для {len(unique_pairs)} пар")
        semaphore = asyncio.Semaphore(max(1, MAX_CONCURRENT_REQUESTS // 2))
        async def get_orderbook_with_semaphore(pair):
            if self.api_client._shutdown_event.is_set():
                return None
            async with semaphore:
                return await self.api_client.get_orderbook(pair)
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
                self.csv_manager.save_opportunity(opportunity)
        opportunities.sort(key=lambda x: x.profit_percent, reverse=True)
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
