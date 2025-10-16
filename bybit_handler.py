import requests
from typing import Dict
from configs import Config


class BybitHandler:
    """Обработчик данных Bybit API"""

    def __init__(self):
        self.base_url = Config.CURRENT_BYBIT_URL
        self.api_key = Config.BYBIT_API_KEY
        self.api_secret = Config.BYBIT_API_SECRET
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/1.0)',
            'Accept': 'application/json'
        }
        self.timeout = Config.REQUEST_TIMEOUT

    def get_all_tickers(self) -> Dict[str, float]:
        """
        Получает все торговые пары с суффиксом USDT и их цены.
        Возвращает словарь: {'BTC': 67500.0, 'ETH': 3500.0, ...}
        """
        try:
            print("[Bybit] Получение тикеров...")

            url = f"{self.base_url}/v5/market/tickers"
            params = {'category': 'spot'}

            response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            data = response.json()
            ret_code = data.get('retCode', data.get('ret_code', None))
            if ret_code is not None and int(ret_code) != 0:
                print(f"[Bybit] ✗ Ошибка API: {data.get('retMsg') or data.get('ret_msg')}")
                return {}

            tickers = {}
            result_list = []
            if isinstance(data.get('result'), dict):
                result_list = data['result'].get('list', [])
            elif isinstance(data.get('result'), list):
                result_list = data['result']

            for ticker in result_list:
                symbol = ticker.get('symbol', '').replace('/', '').upper()
                if not symbol.endswith('USDT'):
                    continue

                base = symbol[:-4]
                try:
                    price = float(ticker.get('lastPrice', ticker.get('last_price', 0)))
                    if price > 0:
                        tickers[base] = price
                except Exception:
                    continue

            print(f"[Bybit] ✓ Загружено {len(tickers)} торговых пар USDT")
            return tickers

        except Exception as e:
            print(f"[Bybit] ✗ Ошибка: {e}")
            return {}
