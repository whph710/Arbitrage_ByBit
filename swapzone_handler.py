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
                        return None

                    if response.status == 401:
                        if attempt == 0:
                            print(f"[Swapzone] ❌ Ошибка авторизации (401): Проверьте API ключ")
                        return None

                    response.raise_for_status()
                    data = await response.json()

                    return data

            except aiohttp.ClientResponseError as e:
                if e.status == 429 and attempt < retries:
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                    continue
                if e.status in (400, 401):
                    return None
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
        """Загружает список доступных валют по документации Swapzone API"""
        print("[Swapzone] 📥 Загрузка доступных валют...")

        # По документации endpoint: /v1/exchange/currencies
        data = await self._make_request("exchange/currencies")

        if not data:
            print("[Swapzone] ❌ Не удалось загрузить валюты (пустой ответ)")
            return

        self.available_currencies.clear()

        # По документации Swapzone возвращает объект с полем "result"
        currencies_list = []

        if isinstance(data, dict) and 'result' in data:
            currencies_list = data['result']
        elif isinstance(data, list):
            currencies_list = data
        else:
            print(f"[Swapzone] ⚠️ Неизвестный формат ответа")
            return

        if not currencies_list:
            print("[Swapzone] ❌ Список валют пуст")
            return

        # По документации каждая валюта имеет поля: ticker, name, network
        for currency in currencies_list:
            if not isinstance(currency, dict):
                continue

            # Основное поле - ticker
            ticker = currency.get('ticker', currency.get('symbol', '')).upper()

            if not ticker:
                continue

            # Сохраняем информацию о валюте
            self.available_currencies[ticker] = {
                'ticker': ticker,
                'name': currency.get('name', ''),
                'network': currency.get('network', ''),
                'has_memo': currency.get('hasMemo', False),
                'is_available': currency.get('isAvailable', True)
            }

        print(f"[Swapzone] ✓ Загружено {len(self.available_currencies)} валют")

        if len(self.available_currencies) > 0:
            # Показываем примеры валют
            sample = list(self.available_currencies.keys())[:10]
            print(f"[Swapzone] 💎 Примеры: {', '.join(sample)}")
        else:
            print(f"[Swapzone] ⚠️ ВНИМАНИЕ: Ни одна валюта не загружена!")
            print(f"[Swapzone] Проверьте API ключ и доступность сервиса")

    async def get_best_exchange_rate(
            self,
            from_currency: str,
            to_currency: str,
            from_amount: float,
            rateType: str = "all"
    ) -> Optional[Dict]:
        """
        Получает лучший курс обмена через Swapzone API
        """
        pair_key = f"{from_currency}_{to_currency}"

        # Проверяем кэш неудачных пар
        if pair_key in self.failed_pairs:
            return None

        # Параметры запроса
        params = {
            'from': from_currency.lower(),
            'to': to_currency.lower(),
            'amount': str(from_amount)
        }

        # Сначала пробуем get-offers
        data = await self._make_request("exchange/get-offers", params=params)

        # Если не сработало (Empty response), пробуем get-rate
        if not data or 'error' in data:
            data = await self._make_request("exchange/get-rate", params={**params, 'rateType': rateType})

        if not data:
            self.failed_pairs.add(pair_key)
            return None

        try:
            # Проверяем на ошибку API
            if 'error' in data and data.get('error') is True:
                self.failed_pairs.add(pair_key)
                return None

            # Вариант 1: Ответ - это массив офферов
            if isinstance(data, list) and len(data) > 0:
                offers = data
            # Вариант 2: Ответ - объект с полем offers
            elif 'offers' in data:
                offers = data['offers']
            # Вариант 3: Ответ - это один оффер с полями adapter, amountTo
            elif 'amountTo' in data and 'adapter' in data:
                offers = [data]
            else:
                self.failed_pairs.add(pair_key)
                return None

            if not offers or len(offers) == 0:
                self.failed_pairs.add(pair_key)
                return None

            # Находим лучший оффер (с максимальной суммой получения)
            best_offer = None
            max_amount = 0

            for offer in offers:
                if not isinstance(offer, dict):
                    continue

                # Ищем сумму получения
                amount_to = offer.get('amountTo', offer.get('toAmount', 0))

                try:
                    amount_to = float(amount_to)
                except (ValueError, TypeError):
                    continue

                if amount_to > max_amount:
                    max_amount = amount_to
                    best_offer = offer

            if not best_offer or max_amount <= 0:
                self.failed_pairs.add(pair_key)
                return None

            # Получаем имя провайдера (adapter)
            provider = best_offer.get('adapter',
                                      best_offer.get('exchangeName',
                                                     best_offer.get('provider', 'Swapzone')))

            return {
                'to_amount': max_amount,
                'from_amount': from_amount,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'exchange_name': provider
            }

        except (ValueError, TypeError, KeyError):
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