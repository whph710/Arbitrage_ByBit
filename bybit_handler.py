import requests
from typing import Dict
from configs import Config


class BybitHandler:
    """Обработчик данных Bybit API"""

    def __init__(self):
        self.base_url = Config.BYBIT_TESTNET_URL if Config.USE_TESTNET else Config.BYBIT_BASE_URL
        self.api_key = Config.BYBIT_API_KEY
        self.api_secret = Config.BYBIT_API_SECRET

    def get_all_tickers(self) -> Dict[str, float]:
        """
        Получает все торговые пары и их цены с Bybit

        Returns:
            {symbol: price_in_usdt} например {'BTC': 67500.0, 'ETH': 3500.0}
        """
        try:
            print("[Bybit] Получение тикеров...")

            # Получаем все USDT пары
            url = f"{self.base_url}/v5/market/tickers"
            params = {
                'category': 'spot'
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get('retCode') != 0:
                print(f"[Bybit] ✗ Ошибка API: {data.get('retMsg')}")
                return {}

            tickers = {}
            for ticker in data.get('result', {}).get('list', []):
                symbol = ticker.get('symbol', '')

                # Берём только USDT пары
                if symbol.endswith('USDT'):
                    crypto = symbol.replace('USDT', '')
                    last_price = float(ticker.get('lastPrice', 0))

                    if last_price > 0:
                        tickers[crypto] = last_price

            print(f"[Bybit] ✓ Загружено {len(tickers)} торговых пар")
            return tickers

        except Exception as e:
            print(f"[Bybit] ✗ Ошибка: {e}")
            return {}

    def get_ticker_price(self, symbol: str) -> float:
        """
        Получает цену конкретной пары

        Args:
            symbol: символ криптовалюты (например 'BTC')

        Returns:
            цена в USDT
        """
        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {
                'category': 'spot',
                'symbol': f"{symbol}USDT"
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data.get('retCode') == 0:
                result = data.get('result', {}).get('list', [])
                if result:
                    return float(result[0].get('lastPrice', 0))

            return 0.0

        except Exception as e:
            print(f"[Bybit] Ошибка получения цены {symbol}: {e}")
            return 0.0