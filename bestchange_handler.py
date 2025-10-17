import aiohttp
import asyncio
from typing import Dict, Set, Optional, List
from configs import (
    BESTCHANGE_API_KEY,
    MAX_CONCURRENT_REQUESTS,
    REQUEST_DELAY,
    BATCH_SIZE,
    MAX_RETRIES,
    RETRY_DELAY,
    REQUEST_TIMEOUT
)


class BestChangeClientAsync:
    """Асинхронный клиент для BestChange API v2.0 с оптимизированной загрузкой"""

    def __init__(self):
        if not BESTCHANGE_API_KEY:
            raise ValueError("BESTCHANGE_API_KEY не задан в configs.py или .env файле")

        self.api_key = BESTCHANGE_API_KEY
        self.base_url = "https://bestchange.app"
        self.lang = "en"

        # Хранилища данных
        self.currencies: Dict[int, Dict] = {}
        self.crypto_currencies: Dict[str, int] = {}
        self.changers: Dict[int, Dict] = {}
        self.rates: Dict[str, Dict[str, List[Dict]]] = {}

        # Настройки из конфига
        self.max_concurrent_requests = MAX_CONCURRENT_REQUESTS
        self.request_delay = REQUEST_DELAY
        self.batch_size = BATCH_SIZE
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY

        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        # Счетчики для статистики
        self.request_count = 0
        self.error_count = 0

    async def __aenter__(self):
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def create_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip',
                    'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/2.0)'
                },
                timeout=self.timeout
            )

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def _make_request(self, endpoint: str, retries: int = None) -> Optional[Dict]:
        """Выполняет HTTP запрос к API с экспоненциальным backoff"""
        if self.session is None:
            await self.create_session()
        if retries is None:
            retries = self.max_retries

        url = f"{self.base_url}/v2/{self.api_key}/{endpoint}"
        self.request_count += 1

        for attempt in range(retries + 1):
            try:
                async with self.session.get(url) as response:
                    if response.status == 429:  # Too Many Requests
                        wait_time = self.retry_delay * (2 ** attempt)  # Экспоненциальный backoff
                        print(f"[BestChange] ⚠️  429 Too Many Requests для {endpoint}")
                        print(f"[BestChange] ⏳ Ожидание {wait_time:.1f}с перед повтором ({attempt + 1}/{retries + 1})")
                        await asyncio.sleep(wait_time)
                        continue

                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientResponseError as e:
                if e.status == 429 and attempt < retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue
                self.error_count += 1
                print(f"[BestChange] ❌ Ошибка {e.status} для {endpoint}: {e.message}")
                return None

            except asyncio.TimeoutError:
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                self.error_count += 1
                print(f"[BestChange] ⏱️  Таймаут для {endpoint}")
                return None

            except Exception as e:
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                self.error_count += 1
                print(f"[BestChange] ❌ Ошибка запроса {endpoint}: {e}")
                return None

        return None

    async def load_currencies(self):
        """Загрузка валют"""
        print("[BestChange] 📥 Загрузка списка валют...")
        data = await self._make_request(f"currencies/{self.lang}")
        if not data or 'currencies' not in data:
            raise ValueError("Не удалось загрузить список валют")

        self.currencies.clear()
        self.crypto_currencies.clear()

        for currency in data['currencies']:
            currency_id = currency['id']
            self.currencies[currency_id] = {
                'id': currency_id,
                'name': currency.get('name', ''),
                'code': currency.get('code', '').upper(),
                'viewname': currency.get('viewname', ''),
                'crypto': currency.get('crypto', False),
                'cash': currency.get('cash', False),
                'group': currency.get('group', 0)
            }

            if currency.get('crypto', False):
                code = currency.get('code', '').upper()
                if code:
                    self.crypto_currencies[code] = currency_id

    async def load_exchangers(self):
        """Загрузка обменников"""
        print("[BestChange] 📥 Загрузка списка обменников...")
        data = await self._make_request(f"changers/{self.lang}")
        if not data or 'changers' not in data:
            print("[BestChange] ⚠️  Не удалось загрузить обменники")
            return

        self.changers.clear()
        for changer in data['changers']:
            if changer.get('active', False):
                changer_id = changer['id']
                self.changers[changer_id] = {
                    'id': changer_id,
                    'name': changer.get('name', ''),
                    'active': changer.get('active', False),
                    'rating': changer.get('rating', 0),
                    'reserve': changer.get('reserve', 0)
                }

    @property
    def exchangers(self) -> Dict[int, str]:
        """Свойство для обратной совместимости"""
        return {cid: data['name'] for cid, data in self.changers.items()}

    async def load_rates(self, common_tickers: List[str]):
        """Загрузка курсов с прогресс-баром"""
        self.rates.clear()
        self.request_count = 0
        self.error_count = 0

        total_coins = len(common_tickers)
        print(f"[BestChange] 🔄 Загрузка курсов для {total_coins} монет...")
        print(
            f"[BestChange] ⚙️  Настройки: {self.max_concurrent_requests} параллельных запросов, задержка {self.request_delay}с")

        # Создаем задачи для каждой монеты
        tasks = []
        for ticker in common_tickers:
            if ticker not in self.crypto_currencies:
                continue
            currency_id = self.crypto_currencies[ticker]
            tasks.append(self._load_rates_for_currency(ticker, currency_id, common_tickers))

        # Семафор для ограничения параллелизма
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        completed = 0

        async def bounded_task(task):
            nonlocal completed
            async with semaphore:
                result = await task
                completed += 1
                if completed % 5 == 0 or completed == total_coins:
                    print(
                        f"[BestChange] 📊 Прогресс: {completed}/{total_coins} монет ({completed * 100 // total_coins}%)")
                await asyncio.sleep(self.request_delay)
                return result

        results = await asyncio.gather(*[bounded_task(t) for t in tasks], return_exceptions=True)

        # Обрабатываем результаты
        for result in results:
            if isinstance(result, Exception):
                self.error_count += 1
                continue
            if result:
                from_ticker, pairs = result
                self.rates[from_ticker] = pairs

        print(f"[BestChange] 📈 Статистика: {self.request_count} запросов, {self.error_count} ошибок")

    async def _load_rates_for_currency(self, from_ticker: str, from_id: int, common_tickers: List[str]):
        """Загружает курсы для одной валюты"""
        try:
            # Шаг 1: Получаем presences
            presences = await self._make_request(f"presences/{from_id}-0")
            if not presences or 'presences' not in presences:
                return None

            pair_list = []
            valid_targets = {}

            for presence in presences['presences']:
                parts = presence['pair'].split('-')
                if len(parts) >= 2:
                    to_id = int(parts[1])
                    if to_id in self.currencies:
                        to_code = self.currencies[to_id]['code']
                        if to_code in common_tickers and from_ticker != to_code:
                            pair_list.append(presence['pair'])
                            valid_targets[to_id] = to_code

            if not pair_list:
                return None

            pairs = {}

            # Шаг 2: Загружаем курсы пакетами (уменьшенный размер батча)
            for i in range(0, len(pair_list), self.batch_size):
                batch = pair_list[i:i + self.batch_size]
                pair_string = '+'.join(batch)

                # Дополнительная задержка между батчами
                if i > 0:
                    await asyncio.sleep(self.request_delay * 0.5)

                rates_data = await self._make_request(f"rates/{pair_string}")

                if not rates_data or 'rates' not in rates_data:
                    continue

                # Парсим курсы
                for pair_id, rates_list in rates_data['rates'].items():
                    parts = pair_id.split('-')
                    if len(parts) < 2:
                        continue

                    to_id = int(parts[1])
                    to_code = valid_targets.get(to_id)
                    if not to_code:
                        continue

                    if to_code not in pairs:
                        pairs[to_code] = []

                    for rate_data in rates_list:
                        try:
                            rate = float(rate_data['rate'])
                            if rate <= 0:
                                continue

                            exchanger_id = rate_data['changer']
                            exchanger_name = self.changers.get(exchanger_id, {}).get('name',
                                                                                     f"Exchanger #{exchanger_id}")

                            pairs[to_code].append({
                                'rate': rate,
                                'exchanger': exchanger_name,
                                'exchanger_id': exchanger_id,
                                'reserve': float(rate_data.get('reserve', 0)),
                                'give': float(rate_data.get('inmin', 0)),
                                'inmax': float(rate_data.get('inmax', 0)),
                                'rankrate': float(rate_data.get('rankrate', rate)),
                                'marks': rate_data.get('marks', [])
                            })
                        except (ValueError, TypeError, KeyError):
                            continue

            # Сортируем по курсу
            for to_code in pairs:
                pairs[to_code].sort(key=lambda x: x['rate'], reverse=True)

            return (from_ticker, pairs) if pairs else None

        except Exception as e:
            print(f"[BestChange] ⚠️  Ошибка обработки {from_ticker}: {e}")
            return None

    async def get_rates_for_pairs(self, common_coins: Set[str]) -> Dict:
        """Получает курсы обмена для всех общих монет"""
        if not self.rates:
            await self.load_rates(list(common_coins))
        return self.rates