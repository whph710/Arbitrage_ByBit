import aiohttp
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class TradingPair:
    pair1: str
    pair2: str
    pair3: str

    def __str__(self):
        return f"({self.pair1}, {self.pair2}, {self.pair3})"


class BybitAPI:
    BASE_URL = "https://api.bybit.com/v5"
    CROSS_PAIRS = ['USDT', 'EUR', 'BRL', 'PLN', 'TRY', 'SOL', 'BTC', 'ETH', 'DAI', 'BRZ']

    def __init__(self):
        self.session = None
        self.tickers_set = set()

    async def start(self):
        """Инициализация сессии."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self

    async def close(self):
        """Закрытие сессии."""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_tickers(self) -> Tuple[List[str], set]:
        """Получает список тикеров."""
        url = f"{self.BASE_URL}/market/tickers"
        params = {"category": "spot"}

        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Error status {response.status} when getting tickers")
                    return [], set()

                data = await response.json()
                if not data.get("result") or not data["result"].get("list"):
                    logger.error("Invalid data format in tickers response")
                    return [], set()

                tickers_all = [pair["symbol"] for pair in data["result"]["list"]]
                self.tickers_set = set(tickers_all)
                return tickers_all, self.tickers_set
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            return [], set()

    def check_and_flip_pair(self, symbol: str) -> str:
        """Проверяет и при необходимости переворачивает пару."""
        if symbol in self.tickers_set:
            return symbol

        if 'USDT' in symbol:
            base = symbol.replace('USDT', '')
            flipped = f'USDT{base}'
            if flipped in self.tickers_set:
                return flipped

        return symbol

    async def get_last_price(self, symbol: str) -> Optional[float]:
        """Получает последнюю цену."""
        symbol = self.check_and_flip_pair(symbol)
        url = f"{self.BASE_URL}/market/tickers"
        params = {
            "category": "spot",
            "symbol": symbol
        }

        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Error status {response.status} for {symbol}")
                    return None

                data = await response.json()
                if not data.get("result") or not data["result"].get("list"):
                    logger.error(f"Invalid data format for {symbol}")
                    return None

                ticker_data = data["result"]["list"][0]
                if "lastPrice" not in ticker_data:
                    logger.error(f"No lastPrice in response for {symbol}")
                    return None

                price = float(ticker_data["lastPrice"])
                if symbol != self.check_and_flip_pair(symbol):
                    price = 1 / price

                return price
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None

    async def get_trading_pairs(self) -> Dict[str, List[TradingPair]]:
        """Формирует торговые пары."""
        tickers_all, _ = await self.get_tickers()

        list_tickers = {base: [] for base in self.CROSS_PAIRS}
        for ticker in tickers_all:
            for base in self.CROSS_PAIRS:
                if ticker.endswith(base):
                    list_tickers[base].append(ticker[:-len(base)])

        trading_pairs = {}
        for base in self.CROSS_PAIRS:
            if base == 'USDT':
                continue

            trading_pairs[base] = []
            for quote in list_tickers[base]:
                if quote in list_tickers['USDT']:
                    pair1 = f"{quote}USDT"
                    pair2 = f"{quote}{base}"
                    pair3 = f"{base}USDT"

                    if pair2 not in self.tickers_set and f"{base}{quote}" in self.tickers_set:
                        pair2 = f"{base}{quote}"

                    trading_pairs[base].append(TradingPair(pair1, pair2, pair3))

        return trading_pairs

    async def process_pair(self, pair: TradingPair, base: str) -> (
            Optional)[Tuple[float, float, float]]:
        """Обрабатывает пару."""
        prices = []
        for symbol in [pair.pair1, pair.pair2, pair.pair3]:
            price = await self.get_last_price(symbol)
            if price is None:
                logger.warning(f"Could not get price for {symbol}")
                return None
            prices.append(price)
        return tuple(prices)


def calculate_profit(a, b, c, commission=0.002):
    money = 100

    # Покупка по цене 'a' с учётом комиссии
    money_after_buy = (money / float(a)) * (1 - commission)

    # Продажа по цене 'b' с учётом комиссии
    money_after_sell = (money_after_buy * float(b)) * (1 - commission)

    # Покупка по цене 'c' с учётом комиссии
    final_money = (money_after_sell / float(c)) * (1 - commission)

    # Рассчитываем процентное изменение
    percentage_change = ((final_money - money) / money) * 100

    return round(percentage_change, 3)

