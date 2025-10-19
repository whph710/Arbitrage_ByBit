import aiohttp
import asyncio
from typing import Dict, Set, Optional, List, Tuple
from dataclasses import dataclass
from configs import (
    BESTCHANGE_API_KEY,
    MAX_CONCURRENT_REQUESTS,
    REQUEST_DELAY,
    BATCH_SIZE,
    MAX_RETRIES,
    RETRY_DELAY,
    REQUEST_TIMEOUT
)


@dataclass
class RateInfo:
    """Информация о курсе обмена"""
    rate: float
    rankrate: float  # Курс с учетом комиссий для $300
    exchanger: str
    exchanger_id: int
    reserve: float
    give_min: float
    give_max: float
    marks: List[str]


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
        self.rates: Dict[str, Dict[str, List[RateInfo]]] = {}

        # Настройки из конфига с валидацией
        self.max_concurrent_requests = max(1, min(MAX_CONCURRENT_REQUESTS, 10))
        self.request_delay = max(0.1, REQUEST_DELAY)
        self.batch_size = max(1, min(BATCH_SIZE, 500))  # Максимум 500 согласно документации
        self.max_retries = max(1, MAX_RETRIES)
        self.retry_delay = max(1, RETRY_DELAY)

        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        # Счетчики для статистики
        self.request_count = 0
        self.error_count = 0
        self.rate_limit_count = 0

        # Для отслеживания последнего запроса (rate limiting)
        self._last_request_time = 0
        self._min_request_interval = 0.05  # Минимум 50ms между запросами

    async def __aenter__(self):
        await self.create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def create_session(self):
        """Создает HTTP сессию с оптимизированными настройками"""
        if self.session is None:
            connector = aiohttp.TCPConnector(
                limit=self.max_concurrent_requests,
                limit_per_host=self.max_concurrent_requests,
                ttl_dns_cache=300
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip, deflate',
                    'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/2.0)',
                    'Connection': 'keep-alive'
                },
                timeout=self.timeout
            )

    async def close(self):
        """Закрывает HTTP сессию"""
        if self.session:
            await self.session.close()
            self.session = None

    async def _rate_limit_wait(self):
        """Умная задержка для предотвращения rate limit"""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_request_time

        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)

        self._last_request_time = asyncio.get_event_loop().time()

    async def _make_request(self, endpoint: str, retries: int = None) -> Optional[Dict]:
        """Выполняет HTTP запрос к API с улучшенной обработкой ошибок"""
        if self.session is None:
            await self.create_session()

        if retries is None:
            retries = self.max_retries

        url = f"{self.base_url}/v2/{self.api_key}/{endpoint}"

        for attempt in range(retries + 1):
            try:
                # Умная задержка перед запросом
                await self._rate_limit_wait()

                self.request_count += 1

                async with self.session.get(url) as response:
                    # Обработка rate limit
                    if response.status == 429:
                        self.rate_limit_count += 1
                        # Экспоненциальный backoff с jitter
                        wait_time = self.retry_delay * (2 ** attempt) * (0.5 + 0.5 * (attempt / retries))

                        if attempt < retries:
                            print(f"[BestChange] ⚠️  Rate limit (429) для {endpoint}")
                            print(f"[BestChange] ⏳ Ожидание {wait_time:.1f}с ({attempt + 1}/{retries + 1})")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            self.error_count += 1
                            print(f"[BestChange] ❌ Превышен лимит попыток для {endpoint}")
                            return None

                    # Обработка других HTTP ошибок
                    if response.status == 404:
                        return None  # Нет данных для этого endpoint

                    if response.status >= 400:
                        if attempt < retries:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        self.error_count += 1
                        print(f"[BestChange] ❌ HTTP {response.status} для {endpoint}")
                        return None

                    # Успешный ответ
                    try:
                        data = await response.json()
                        return data
                    except aiohttp.ContentTypeError:
                        self.error_count += 1
                        print(f"[BestChange] ❌ Невалидный JSON для {endpoint}")
                        return None

            except asyncio.TimeoutError:
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                self.error_count += 1
                print(f"[BestChange] ⏱️  Таймаут для {endpoint}")
                return None

            except aiohttp.ClientError as e:
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                self.error_count += 1
                print(f"[BestChange] ❌ Сетевая ошибка для {endpoint}: {e}")
                return None

            except Exception as e:
                self.error_count += 1
                print(f"[BestChange] ❌ Неожиданная ошибка для {endpoint}: {e}")
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
            code = currency.get('code', '').upper()

            self.currencies[currency_id] = {
                'id': currency_id,
                'name': currency.get('name', ''),
                'code': code,
                'viewname': currency.get('viewname', ''),
                'crypto': currency.get('crypto', False),
                'cash': currency.get('cash', False),
                'group': currency.get('group', 0)
            }

            # Индексируем криптовалюты по коду
            if currency.get('crypto', False) and code:
                self.crypto_currencies[code] = currency_id

        print(f"[BestChange] ✅ Загружено валют: {len(self.currencies)} (крипто: {len(self.crypto_currencies)})")

    async def load_exchangers(self):
        """Загрузка обменников"""
        print("[BestChange] 📥 Загрузка списка обменников...")
        data = await self._make_request(f"changers/{self.lang}")

        if not data or 'changers' not in data:
            print("[BestChange] ⚠️  Не удалось загрузить обменники")
            return

        self.changers.clear()
        active_count = 0

        for changer in data['changers']:
            changer_id = changer['id']
            is_active = changer.get('active', False)

            self.changers[changer_id] = {
                'id': changer_id,
                'name': changer.get('name', ''),
                'active': is_active,
                'rating': changer.get('rating', 0),
                'reserve': changer.get('reserve', 0)
            }

            if is_active:
                active_count += 1

        print(f"[BestChange] ✅ Загружено обменников: {len(self.changers)} (активных: {active_count})")

    @property
    def exchangers(self) -> Dict[int, str]:
        """Свойство для обратной совместимости"""
        return {cid: data['name'] for cid, data in self.changers.items()}

    async def load_rates(self, common_tickers: List[str], use_rankrate: bool = True):
        """
        Загрузка курсов с прогресс-баром

        Args:
            common_tickers: Список тикеров для загрузки
            use_rankrate: Использовать rankrate вместо rate (учитывает комиссии)
        """
        self.rates.clear()
        self.request_count = 0
        self.error_count = 0
        self.rate_limit_count = 0

        total_coins = len(common_tickers)
        print(f"\n[BestChange] 🔄 Загрузка курсов для {total_coins} монет...")
        print(f"[BestChange] ⚙️  Параметры:")
        print(f"  • Параллельных запросов: {self.max_concurrent_requests}")
        print(f"  • Задержка между запросами: {self.request_delay}с")
        print(f"  • Размер батча: {self.batch_size} пар")
        print(f"  • Использовать rankrate: {'Да' if use_rankrate else 'Нет'}")

        # Фильтруем только существующие криптовалюты
        valid_tickers = [
            ticker for ticker in common_tickers
            if ticker in self.crypto_currencies
        ]

        if len(valid_tickers) < len(common_tickers):
            print(f"[BestChange] ⚠️  Пропущено {len(common_tickers) - len(valid_tickers)} неизвестных тикеров")

        # Создаем задачи для каждой монеты
        tasks = []
        for ticker in valid_tickers:
            currency_id = self.crypto_currencies[ticker]
            tasks.append(
                self._load_rates_for_currency(ticker, currency_id, valid_tickers, use_rankrate)
            )

        # Семафор для ограничения параллелизма
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        completed = 0
        successful = 0

        async def bounded_task(task):
            nonlocal completed, successful
            async with semaphore:
                result = await task
                completed += 1

                if result:
                    successful += 1

                # Прогресс-бар
                if completed % 5 == 0 or completed == len(tasks):
                    progress = completed * 100 // len(tasks)
                    print(f"[BestChange] 📊 Прогресс: {completed}/{len(tasks)} ({progress}%) | Успешно: {successful}")

                # Динамическая задержка между батчами
                await asyncio.sleep(self.request_delay)
                return result

        # Запускаем все задачи
        results = await asyncio.gather(*[bounded_task(t) for t in tasks], return_exceptions=True)

        # Обрабатываем результаты
        for result in results:
            if isinstance(result, Exception):
                self.error_count += 1
                continue
            if result:
                from_ticker, pairs = result
                self.rates[from_ticker] = pairs

        # Финальная статистика
        print(f"\n[BestChange] 📈 Статистика загрузки:")
        print(f"  • Всего запросов: {self.request_count}")
        print(f"  • Успешных монет: {successful}/{len(tasks)}")
        print(f"  • Ошибок: {self.error_count}")
        print(f"  • Rate limit (429): {self.rate_limit_count}")
        print(f"  • Загружено пар: {sum(len(pairs) for pairs in self.rates.values())}")

    async def _load_rates_for_currency(
            self,
            from_ticker: str,
            from_id: int,
            common_tickers: List[str],
            use_rankrate: bool
    ) -> Optional[Tuple[str, Dict[str, List[RateInfo]]]]:
        """
        Загружает курсы для одной валюты

        Оптимизированный алгоритм:
        1. Получаем presences для определения доступных пар
        2. Загружаем rates батчами для всех доступных пар
        3. Парсим и сортируем результаты
        """
        try:
            # Шаг 1: Получаем presences (доступные направления обмена)
            presences = await self._make_request(f"presences/{from_id}-0")
            if not presences or 'presences' not in presences:
                return None

            # Фильтруем только нужные нам пары
            pair_list = []
            valid_targets = {}

            for presence in presences['presences']:
                pair_id = presence['pair']
                parts = pair_id.split('-')

                if len(parts) < 2:
                    continue

                try:
                    to_id = int(parts[1])
                except ValueError:
                    continue

                # Проверяем что целевая валюта существует и есть в списке
                if to_id not in self.currencies:
                    continue

                to_code = self.currencies[to_id]['code']

                # Только криптовалюты из нашего списка
                if to_code in common_tickers and from_ticker != to_code:
                    pair_list.append(pair_id)
                    valid_targets[to_id] = to_code

            if not pair_list:
                return None

            pairs: Dict[str, List[RateInfo]] = {}

            # Шаг 2: Загружаем курсы батчами
            for i in range(0, len(pair_list), self.batch_size):
                batch = pair_list[i:i + self.batch_size]
                pair_string = '+'.join(batch)

                # Небольшая задержка между батчами одной валюты
                if i > 0:
                    await asyncio.sleep(self.request_delay * 0.3)

                rates_data = await self._make_request(f"rates/{pair_string}")

                if not rates_data or 'rates' not in rates_data:
                    continue

                # Парсим курсы из ответа
                for pair_id, rates_list in rates_data['rates'].items():
                    parts = pair_id.split('-')
                    if len(parts) < 2:
                        continue

                    try:
                        to_id = int(parts[1])
                    except ValueError:
                        continue

                    to_code = valid_targets.get(to_id)
                    if not to_code:
                        continue

                    if to_code not in pairs:
                        pairs[to_code] = []

                    # Обрабатываем каждое предложение обменника
                    for rate_data in rates_list:
                        try:
                            rate = float(rate_data.get('rate', 0))
                            rankrate = float(rate_data.get('rankrate', rate))

                            # Используем rankrate если включено (более точный курс)
                            effective_rate = rankrate if use_rankrate else rate

                            if effective_rate <= 0:
                                continue

                            exchanger_id = rate_data['changer']

                            # Получаем информацию об обменнике
                            exchanger_info = self.changers.get(exchanger_id, {})
                            if not exchanger_info.get('active', False):
                                continue  # Пропускаем неактивные обменники

                            exchanger_name = exchanger_info.get('name', f"Exchanger #{exchanger_id}")

                            rate_info = RateInfo(
                                rate=rate,
                                rankrate=rankrate,
                                exchanger=exchanger_name,
                                exchanger_id=exchanger_id,
                                reserve=float(rate_data.get('reserve', 0)),
                                give_min=float(rate_data.get('inmin', 0)),
                                give_max=float(rate_data.get('inmax', 0)),
                                marks=rate_data.get('marks', [])
                            )

                            pairs[to_code].append(rate_info)

                        except (ValueError, TypeError, KeyError) as e:
                            # Пропускаем невалидные записи
                            continue

            # Сортируем по эффективному курсу (rankrate или rate)
            for to_code in pairs:
                pairs[to_code].sort(
                    key=lambda x: x.rankrate if use_rankrate else x.rate,
                    reverse=True
                )

            return (from_ticker, pairs) if pairs else None

        except Exception as e:
            print(f"[BestChange] ⚠️  Ошибка обработки {from_ticker}: {type(e).__name__}: {e}")
            return None

    async def get_rates_for_pairs(self, common_coins: Set[str], use_rankrate: bool = True) -> Dict:
        """
        Получает курсы обмена для всех общих монет

        Args:
            common_coins: Множество тикеров монет
            use_rankrate: Использовать rankrate (с учетом комиссий)

        Returns:
            Словарь курсов {from_ticker: {to_ticker: [RateInfo, ...]}}
        """
        if not self.rates:
            await self.load_rates(list(common_coins), use_rankrate)
        return self.rates

    def get_best_rate(self, from_ticker: str, to_ticker: str, min_reserve: float = 0) -> Optional[RateInfo]:
        """
        Получает лучший курс для пары с учетом минимального резерва

        Args:
            from_ticker: Тикер исходной валюты
            to_ticker: Тикер целевой валюты
            min_reserve: Минимальный резерв обменника

        Returns:
            Лучший RateInfo или None
        """
        if from_ticker not in self.rates:
            return None

        if to_ticker not in self.rates[from_ticker]:
            return None

        rates = self.rates[from_ticker][to_ticker]

        # Фильтруем по минимальному резерву
        if min_reserve > 0:
            rates = [r for r in rates if r.reserve >= min_reserve]

        return rates[0] if rates else None

    def get_top_rates(
            self,
            from_ticker: str,
            to_ticker: str,
            top_n: int = 5,
            min_reserve: float = 0
    ) -> List[RateInfo]:
        """
        Получает топ N лучших курсов для пары

        Args:
            from_ticker: Тикер исходной валюты
            to_ticker: Тикер целевой валюты
            top_n: Количество лучших курсов
            min_reserve: Минимальный резерв обменника

        Returns:
            Список из топ N RateInfo
        """
        if from_ticker not in self.rates:
            return []

        if to_ticker not in self.rates[from_ticker]:
            return []

        rates = self.rates[from_ticker][to_ticker]

        # Фильтруем по минимальному резерву
        if min_reserve > 0:
            rates = [r for r in rates if r.reserve >= min_reserve]

        return rates[:top_n]

    def print_statistics(self):
        """Выводит подробную статистику загруженных данных"""
        print("\n" + "=" * 60)
        print("📊 СТАТИСТИКА BESTCHANGE")
        print("=" * 60)
        print(f"Валют загружено: {len(self.currencies)}")
        print(f"Криптовалют: {len(self.crypto_currencies)}")
        print(f"Обменников: {len(self.changers)}")
        print(f"Направлений обмена: {len(self.rates)}")

        total_pairs = sum(len(pairs) for pairs in self.rates.values())
        print(f"Всего пар: {total_pairs}")

        if self.rates:
            avg_pairs = total_pairs / len(self.rates)
            print(f"Среднее пар на валюту: {avg_pairs:.1f}")

        print("=" * 60 + "\n")