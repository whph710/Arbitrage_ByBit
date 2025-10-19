import aiohttp
import asyncio
from typing import Dict, List, Optional
from configs import REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY


class ChangeNowClientAsync:
    """Асинхронный клиент для ChangeNOW API с улучшенной обработкой ошибок"""

    def __init__(self, api_key: str = None):
        self.base_url = "https://api.changenow.io/v2"
        self.api_key = api_key
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/4.0)'
        }
        if self.api_key:
            self.headers['x-changenow-api-key'] = self.api_key

        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = None

        # Кэш доступных валют и пар
        self.available_currencies: Dict[str, Dict] = {}
        self.exchange_ranges: Dict[str, Dict] = {}
        self.failed_pairs: set = set()  # Кэш неудачных пар для избежания повторных запросов

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
                        print(f"[ChangeNOW] ⚠️ Rate limit, ожидание {wait_time:.1f}с")
                        await asyncio.sleep(wait_time)
                        continue

                    if response.status == 400:
                        # Ошибка 400 - неверные параметры, не повторяем запрос
                        error_text = await response.text()
                        # Не выводим каждую ошибку, только суммируем
                        return None

                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientResponseError as e:
                if e.status == 429 and attempt < retries:
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                    continue
                if e.status == 400:
                    # Ошибка валидации - не повторяем
                    return None
                # Для других ошибок выводим сообщение
                if attempt == retries:
                    print(f"[ChangeNOW] ❌ Ошибка {e.status} для {endpoint}")
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
        """Загружает список доступных валют для обмена"""
        print("[ChangeNOW] 📥 Загрузка доступных валют...")

        data = await self._make_request("exchange/currencies", params={'active': 'true'})

        if not data:
            print("[ChangeNOW] ❌ Не удалось загрузить валюты")
            return

        self.available_currencies.clear()

        for currency in data:
            ticker = currency.get('ticker', '').upper()
            if ticker:
                self.available_currencies[ticker] = {
                    'ticker': ticker,
                    'name': currency.get('name', ''),
                    'network': currency.get('network', ''),
                    'has_external_id': currency.get('hasExternalId', False),
                    'is_stable': currency.get('isStable', False),
                    'supports_fixed_rate': currency.get('supportsFixedRate', False)
                }

        print(f"[ChangeNOW] ✓ Загружено {len(self.available_currencies)} валют")

    async def get_exchange_range(self, from_currency: str, to_currency: str) -> Optional[Dict]:
        """Получает минимальную и максимальную сумму обмена"""
        pair_key = f"{from_currency}_{to_currency}"

        # Проверяем кэш неудачных пар
        if pair_key in self.failed_pairs:
            return None

        # Проверяем кэш успешных пар
        if pair_key in self.exchange_ranges:
            return self.exchange_ranges[pair_key]

        from_info = self.available_currencies.get(from_currency, {})
        to_info = self.available_currencies.get(to_currency, {})

        data = await self._make_request(
            "exchange/range",
            params={
                'fromCurrency': from_currency.lower(),
                'toCurrency': to_currency.lower(),
                'fromNetwork': from_info.get('network', ''),
                'toNetwork': to_info.get('network', ''),
                'flow': 'standard'
            }
        )

        if data and 'minAmount' in data:
            range_info = {
                'min_amount': float(data.get('minAmount', 0)),
                'max_amount': float(data.get('maxAmount', 0)) if data.get('maxAmount') else 999999999
            }
            self.exchange_ranges[pair_key] = range_info
            return range_info
        else:
            # Добавляем в список неудачных пар
            self.failed_pairs.add(pair_key)
            return None

    async def get_estimated_amount(
            self,
            from_currency: str,
            to_currency: str,
            from_amount: float
    ) -> Optional[Dict]:
        """
        Получает расчётную сумму обмена

        Returns:
            {
                'to_amount': float,
                'rate': float,
                'from_amount': float
            }
        """
        pair_key = f"{from_currency}_{to_currency}"

        # Проверяем кэш неудачных пар
        if pair_key in self.failed_pairs:
            return None

        from_info = self.available_currencies.get(from_currency, {})
        to_info = self.available_currencies.get(to_currency, {})

        params = {
            'fromCurrency': from_currency.lower(),
            'toCurrency': to_currency.lower(),
            'fromAmount': from_amount,
            'fromNetwork': from_info.get('network', ''),
            'toNetwork': to_info.get('network', ''),
            'flow': 'standard',
            'type': 'direct'
        }

        data = await self._make_request("exchange/estimated-amount", params=params)

        if data and 'toAmount' in data:
            try:
                to_amount = float(data['toAmount'])

                # НЕ рассчитываем rate здесь - это будет сделано в analyzer
                # потому что API возвращает результат, а не курс конверсии

                return {
                    'to_amount': to_amount,
                    'from_amount': from_amount,
                    'from_currency': from_currency,
                    'to_currency': to_currency
                }
            except (ValueError, TypeError, ZeroDivisionError):
                self.failed_pairs.add(pair_key)
                return None
        else:
            # Добавляем в список неудачных пар
            self.failed_pairs.add(pair_key)
            return None

    async def check_pair_availability(self, from_currency: str, to_currency: str) -> bool:
        """Проверяет, доступна ли пара для обмена"""
        pair_key = f"{from_currency}_{to_currency}"

        # Быстрая проверка кэша неудачных пар
        if pair_key in self.failed_pairs:
            return False

        if from_currency not in self.available_currencies:
            return False
        if to_currency not in self.available_currencies:
            return False

        # Проверяем минимальную сумму обмена
        range_info = await self.get_exchange_range(from_currency, to_currency)
        return range_info is not None and range_info['min_amount'] > 0

    async def get_best_rate_batch(
            self,
            pairs: List[tuple],
            delay: float = 0.1
    ) -> Dict[str, Optional[Dict]]:
        """
        Получает курсы для нескольких пар параллельно

        Returns:
            {'FROM_TO': {...}, ...}
        """
        results = {}

        for from_curr, to_curr, amount in pairs:
            pair_key = f"{from_curr}_{to_curr}"

            # Проверяем кэш неудачных пар
            if pair_key in self.failed_pairs:
                results[pair_key] = None
                continue

            # Проверяем доступность пары
            if not await self.check_pair_availability(from_curr, to_curr):
                results[pair_key] = None
                continue

            # Получаем курс
            rate_info = await self.get_estimated_amount(from_curr, to_curr, amount)
            results[pair_key] = rate_info

            # Небольшая задержка между запросами
            await asyncio.sleep(delay)

        return results

    def has_currency(self, currency: str) -> bool:
        """Проверяет, поддерживается ли валюта"""
        return currency.upper() in self.available_currencies

    def get_common_currencies(self, bybit_coins: set) -> set:
        """Возвращает пересечение валют Bybit и ChangeNOW"""
        changenow_coins = set(self.available_currencies.keys())
        common = bybit_coins & changenow_coins

        print(f"[ChangeNOW] 🔍 Общих монет с Bybit: {len(common)}")
        if common:
            preview = ', '.join(sorted(list(common)[:20]))
            more = f" и еще {len(common) - 20}" if len(common) > 20 else ""
            print(f"[ChangeNOW]   Примеры: {preview}{more}")

        return common

    def get_failed_pairs_count(self) -> int:
        """Возвращает количество неудачных пар"""
        return len(self.failed_pairs)