import aiohttp
import asyncio
from typing import Dict, List, Optional, Set
from configs import REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY


class SwapzoneClientAsync:
    """Асинхронный клиент для Swapzone API"""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("SWAPZONE_API_KEY не задан")

        self.api_key = api_key
        self.base_url = "https://api.swapzone.io/v1"
        self.headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/4.0)'
        }
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = None

        # Кэш доступных валют и пар
        self.available_currencies: Dict[str, Dict] = {}
        self.failed_pairs: Set[str] = set()

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

    async def _make_request(self, endpoint: str, params: Dict = None, retries: int = None) -> Optional[Dict]:
        """Выполняет HTTP запрос к API с повторами"""
        if self.session is None:
            await self.create_session()
        if retries is None:
            retries = MAX_RETRIES

        url = f"{self.base_url}/{endpoint}"

        for attempt in range(retries + 1):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 429:
                        wait_time = RETRY_DELAY * (2 ** attempt)
                        print(f"[Swapzone] ⚠️ Rate limit, ожидание {wait_time:.1f}с")
                        await asyncio.sleep(wait_time)
                        continue

                    if response.status == 400:
                        # Ошибка 400 - неверные параметры
                        return None

                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientResponseError as e:
                if e.status == 429 and attempt < retries:
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                    continue
                if e.status == 400:
                    return None
                if attempt == retries:
                    print(f"[Swapzone] ❌ Ошибка {e.status} для {endpoint}")
                return None

            except asyncio.TimeoutError:
                if attempt < retries:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return None

            except Exception as e:
                if attempt < retries:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                return None

        return None

    async def load_available_currencies(self):
        """Загружает список доступных валют"""
        print("[Swapzone] 📥 Загрузка доступных валют...")

        data = await self._make_request("currencies")

        if not data:
            print("[Swapzone] ❌ Не удалось загрузить валюты")
            return

        self.available_currencies.clear()

        # Swapzone возвращает массив валют
        if isinstance(data, list):
            for currency in data:
                ticker = currency.get('symbol', '').upper()
                if ticker:
                    self.available_currencies[ticker] = {
                        'ticker': ticker,
                        'name': currency.get('name', ''),
                        'network': currency.get('network', ''),
                        'is_available': currency.get('isAvailable', True)
                    }
        elif isinstance(data, dict) and 'currencies' in data:
            for currency in data['currencies']:
                ticker = currency.get('symbol', '').upper()
                if ticker:
                    self.available_currencies[ticker] = {
                        'ticker': ticker,
                        'name': currency.get('name', ''),
                        'network': currency.get('network', ''),
                        'is_available': currency.get('isAvailable', True)
                    }

        print(f"[Swapzone] ✓ Загружено {len(self.available_currencies)} валют")

    async def get_best_exchange_rate(
            self,
            from_currency: str,
            to_currency: str,
            from_amount: float,
            rateType: str = "all"  # all, fixed, float
    ) -> Optional[Dict]:
        """
        Получает лучший курс обмена через все доступные обменники

        Returns:
            {
                'to_amount': float,
                'from_amount': float,
                'from_currency': str,
                'to_currency': str,
                'exchange_name': str,
                'rate': float (опционально)
            }
        """
        pair_key = f"{from_currency}_{to_currency}"

        # Проверяем кэш неудачных пар
        if pair_key in self.failed_pairs:
            return None

        params = {
            'from': from_currency.lower(),
            'to': to_currency.lower(),
            'amount': from_amount,
            'rateType': rateType
        }

        data = await self._make_request("exchange/get-rate", params=params)

        if not data:
            self.failed_pairs.add(pair_key)
            return None

        try:
            # Swapzone возвращает массив предложений от разных обменников
            # Берём лучшее предложение (с максимальной суммой получения)
            offers = data if isinstance(data, list) else data.get('offers', [])

            if not offers:
                self.failed_pairs.add(pair_key)
                return None

            # Находим предложение с максимальной суммой получения
            best_offer = max(offers, key=lambda x: float(x.get('amountTo', 0)))

            to_amount = float(best_offer.get('amountTo', 0))

            if to_amount <= 0:
                self.failed_pairs.add(pair_key)
                return None

            return {
                'to_amount': to_amount,
                'from_amount': from_amount,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'exchange_name': best_offer.get('provider', 'Unknown')
            }

        except (ValueError, TypeError, KeyError) as e:
            self.failed_pairs.add(pair_key)
            return None

    async def get_estimated_amount(
            self,
            from_currency: str,
            to_currency: str,
            from_amount: float
    ) -> Optional[Dict]:
        """
        Алиас для совместимости с другими обменниками
        """
        return await self.get_best_exchange_rate(from_currency, to_currency, from_amount)

    def has_currency(self, currency: str) -> bool:
        """Проверяет, поддерживается ли валюта"""
        return currency.upper() in self.available_currencies

    def get_common_currencies(self, bybit_coins: set) -> set:
        """Возвращает пересечение валют Bybit и Swapzone"""
        swapzone_coins = set(self.available_currencies.keys())
        common = bybit_coins & swapzone_coins

        print(f"[Swapzone] 🔍 Общих монет с Bybit: {len(common)}")
        if common:
            preview = ', '.join(sorted(list(common)[:20]))
            more = f" и еще {len(common) - 20}" if len(common) > 20 else ""
            print(f"[Swapzone]   Примеры: {preview}{more}")

        return common

    def get_failed_pairs_count(self) -> int:
        """Возвращает количество неудачных пар"""
        return len(self.failed_pairs)