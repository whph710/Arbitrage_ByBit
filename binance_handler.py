import aiohttp
from typing import Dict, Set
from configs import BINANCE_API_URL, REQUEST_TIMEOUT


class BinanceClientAsync:
    """Асинхронный клиент для Binance API"""

    def __init__(self):
        self.base_url = BINANCE_API_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/2.0)',
            'Accept': 'application/json'
        }
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = None
        self.usdt_pairs: Dict[str, float] = {}
        self.coins: Set[str] = set()

    async def __aenter__(self):
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def create_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers, timeout=self.timeout)

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def load_usdt_pairs(self):
        """Загружает все USDT-пары с Binance и сохраняет в usdt_pairs и coins"""
        if self.session is None:
            await self.create_session()

        try:
            url = f"{self.base_url}/api/v3/ticker/price"
            async with self.session.get(url) as response:
                response.raise_for_status()
                data = await response.json()

            self.usdt_pairs.clear()
            self.coins.clear()

            for ticker in data:
                symbol = ticker.get('symbol', '').upper()
                if not symbol.endswith('USDT'):
                    continue

                base = symbol[:-4]  # Убираем 'USDT' из конца

                try:
                    price = float(ticker.get('price', 0))
                    if price > 0:
                        self.usdt_pairs[base] = price
                        self.coins.add(base)
                except (ValueError, TypeError):
                    continue

            print(f"[Binance] ✓ Загружено {len(self.usdt_pairs)} торговых пар USDT")

        except Exception as e:
            print(f"[Binance] ❌ Ошибка при загрузке пар: {e}")

    async def get_usdt_tickers(self) -> Dict[str, float]:
        """Получает все USDT-пары с Binance (для совместимости со старым кодом)"""
        if not self.usdt_pairs:
            await self.load_usdt_pairs()
        return self.usdt_pairs