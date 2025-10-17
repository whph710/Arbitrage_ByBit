import aiohttp
import asyncio
from typing import Dict, Set, Optional, List
from configs import BESTCHANGE_API_KEY


class BestChangeClientAsync:
    """Асинхронный клиент для BestChange API v2.0"""

    def __init__(self):
        if not BESTCHANGE_API_KEY:
            raise ValueError("BESTCHANGE_API_KEY не задан в configs.py или .env файле")

        self.api_key = BESTCHANGE_API_KEY
        self.base_url = "https://bestchange.app"
        self.lang = "en"

        # Хранилища данных согласно API документации
        self.currencies: Dict[int, Dict] = {}  # id -> данные валюты (name, code, crypto, etc)
        self.crypto_currencies: Dict[str, int] = {}  # code (ticker) -> id (только крипто)
        self.changers: Dict[int, Dict] = {}  # id -> данные обменника (name, active, etc)
        self.rates: Dict[str, Dict[str, List[Dict]]] = {}  # from_code -> to_code -> список курсов

        self.max_concurrent_requests = 10
        self.request_delay = 0.1
        self.max_retries = 2
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=15)

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
                    'User-Agent': 'Mozilla/5.0'
                },
                timeout=self.timeout
            )

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def _make_request(self, endpoint: str, retries: int = None) -> Optional[Dict]:
        """Выполняет HTTP запрос к API"""
        if self.session is None:
            await self.create_session()
        if retries is None:
            retries = self.max_retries

        url = f"{self.base_url}/v2/{self.api_key}/{endpoint}"

        for attempt in range(retries + 1):
            try:
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                print(f"[BestChange] Ошибка запроса {endpoint}: {e}")
                return None
        return None

    async def load_currencies(self):
        """Загрузка валют согласно API документации"""
        data = await self._make_request(f"currencies/{self.lang}")
        if not data or 'currencies' not in data:
            raise ValueError("Не удалось загрузить список валют")

        self.currencies.clear()
        self.crypto_currencies.clear()

        for currency in data['currencies']:
            currency_id = currency['id']
            # Сохраняем полные данные валюты
            self.currencies[currency_id] = {
                'id': currency_id,
                'name': currency.get('name', ''),
                'code': currency.get('code', '').upper(),  # API использует поле "code"
                'viewname': currency.get('viewname', ''),
                'crypto': currency.get('crypto', False),
                'cash': currency.get('cash', False),
                'group': currency.get('group', 0)
            }

            # Если это криптовалюта, добавляем в отдельный словарь
            if currency.get('crypto', False):
                code = currency.get('code', '').upper()
                if code:
                    self.crypto_currencies[code] = currency_id

    async def load_exchangers(self):
        """Загрузка обменников согласно API документации"""
        data = await self._make_request(f"changers/{self.lang}")
        if not data or 'changers' not in data:
            print("[BestChange] Предупреждение: не удалось загрузить обменники")
            return

        self.changers.clear()
        for changer in data['changers']:
            if changer.get('active', False):  # Только активные
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
        """Свойство для обратной совместимости - возвращает {id: name}"""
        return {cid: data['name'] for cid, data in self.changers.items()}

    async def load_rates(self, common_tickers: List[str]):
        """Загрузка курсов для общих монет"""
        self.rates.clear()
        tasks = []

        for ticker in common_tickers:
            if ticker not in self.crypto_currencies:
                continue
            currency_id = self.crypto_currencies[ticker]
            tasks.append(self._load_rates_for_currency(ticker, currency_id, common_tickers))

        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def bounded_task(task):
            async with semaphore:
                result = await task
                await asyncio.sleep(self.request_delay)
                return result

        results = await asyncio.gather(*[bounded_task(t) for t in tasks])

        for result in results:
            if result:
                from_ticker, pairs = result
                self.rates[from_ticker] = pairs

    async def _load_rates_for_currency(self, from_ticker: str, from_id: int, common_tickers: List[str]):
        """Загружает курсы для одной валюты согласно API документации"""
        # Шаг 1: Получаем presences (доступные направления)
        presences = await self._make_request(f"presences/{from_id}-0")
        if not presences or 'presences' not in presences:
            return None

        pair_list = []
        valid_targets = {}

        # Парсим доступные направления
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
        batch_size = 100

        # Шаг 2: Получаем курсы пакетами (до 500 пар за запрос)
        for i in range(0, len(pair_list), batch_size):
            batch = pair_list[i:i + batch_size]
            pair_string = '+'.join(batch)  # Формат API: "305-89+305-89-1+305-89-2"
            rates_data = await self._make_request(f"rates/{pair_string}")

            if not rates_data or 'rates' not in rates_data:
                continue

            # Парсим курсы согласно структуре API
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

                # Обрабатываем каждый курс от обменника
                for rate_data in rates_list:
                    try:
                        rate = float(rate_data['rate'])
                        if rate <= 0:
                            continue

                        exchanger_id = rate_data['changer']
                        exchanger_name = self.changers.get(exchanger_id, {}).get('name', f"Exchanger #{exchanger_id}")

                        pairs[to_code].append({
                            'rate': rate,
                            'exchanger': exchanger_name,
                            'exchanger_id': exchanger_id,
                            'reserve': float(rate_data.get('reserve', 0)),
                            'give': float(rate_data.get('inmin', 0)),  # минимальная сумма
                            'inmax': float(rate_data.get('inmax', 0)),  # максимальная сумма
                            'rankrate': float(rate_data.get('rankrate', rate)),
                            'marks': rate_data.get('marks', [])
                        })
                    except (ValueError, TypeError, KeyError) as e:
                        continue

        # Сортируем по курсу (лучший сверху)
        for to_code in pairs:
            pairs[to_code].sort(key=lambda x: x['rate'], reverse=True)

        return (from_ticker, pairs) if pairs else None

    async def get_rates_for_pairs(self, common_coins: Set[str]) -> Dict:
        """Получает курсы обмена для всех общих монет (для совместимости)"""
        if not self.rates:
            await self.load_rates(list(common_coins))
        return self.rates