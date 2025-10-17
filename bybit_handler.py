import aiohttp
from typing import Dict
from configs import BYBIT_API_URL, REQUEST_TIMEOUT


class BybitClientAsync:
    """Асинхронный клиент для Bybit API"""

    def __init__(self):
        self.base_url = BYBIT_API_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/2.0)',
            'Accept': 'application/json'
        }
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = None

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

    async def get_usdt_tickers(self) -> Dict[str, float]:
        """Получает все USDT-пары с Bybit"""
        if self.session is None:
            await self.create_session()

        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {'category': 'spot'}
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

            tickers = {}
            result_list = data.get('result', {}).get('list', [])

            for ticker in result_list:
                symbol = ticker.get('symbol', '').replace('/', '').upper()
                if not symbol.endswith('USDT'):
                    continue
                base = symbol[:-4]
                try:
                    price = float(ticker.get('lastPrice', 0))
                    if price > 0:
                        tickers[base] = price
                except (ValueError, TypeError):
                    continue

            return tickers

        except Exception as e:
            print(f"[Bybit] Ошибка: {e}")
            return {}
