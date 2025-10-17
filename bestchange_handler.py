import aiohttp
import asyncio
from typing import Dict, Set, Optional
from configs import BESTCHANGE_API_KEY


class BestChangeClientAsync:
    """Асинхронный клиент для BestChange API v2.0"""

    def __init__(self):
        if not BESTCHANGE_API_KEY:
            raise ValueError("BESTCHANGE_API_KEY не задан в configs.py")

        self.api_key = BESTCHANGE_API_KEY
        self.base_url = "https://bestchange.app"
        self.lang = "en"

        self.crypto_currencies: Dict[str, int] = {}  # ticker -> id
        self.changers: Dict[int, str] = {}           # id -> имя
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
            except Exception:
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return None
        return None

    async def initialize(self):
        """Загрузка валют и обменников"""
        await asyncio.gather(self._load_currencies(), self._load_changers())

    async def _load_currencies(self):
        data = await self._make_request(f"currencies/{self.lang}")
        if not data or 'currencies' not in data:
            raise ValueError("Не удалось загрузить список валют")
        for currency in data['currencies']:
            if currency.get('crypto', False):
                ticker = currency.get('code', '').upper()
                self.crypto_currencies[ticker] = currency['id']

    async def _load_changers(self):
        data = await self._make_request(f"changers/{self.lang}")
        if data and 'changers' in data:
            for changer in data['changers']:
                if changer.get('active', False):
                    self.changers[changer['id']] = changer['name']

    async def get_rates_for_pairs(self, common_coins: Set[str]) -> Dict:
        """Получает курсы обмена для всех общих монет"""
        crypto_pairs = {}
        tasks = []
        common_ids = {cid: ticker for ticker, cid in self.crypto_currencies.items() if ticker in common_coins}

        for from_id, from_ticker in common_ids.items():
            tasks.append(self._get_rates_for_currency(from_id, from_ticker, common_ids))

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
                crypto_pairs[from_ticker] = pairs

        return crypto_pairs

    async def _get_rates_for_currency(self, from_id, from_ticker, common_ids):
        presences = await self._make_request(f"presences/{from_id}-0")
        if not presences or 'presences' not in presences:
            return None

        pair_list = []
        valid_targets = {}
        for presence in presences['presences']:
            parts = presence['pair'].split('-')
            if len(parts) >= 2:
                to_id = int(parts[1])
                if to_id in common_ids and from_ticker != common_ids[to_id]:
                    pair_list.append(presence['pair'])
                    valid_targets[to_id] = common_ids[to_id]

        if not pair_list:
            return None

        pairs = {}
        batch_size = 100
        for i in range(0, len(pair_list), batch_size):
            batch = pair_list[i:i + batch_size]
            pair_string = '+'.join(batch)
            rates_data = await self._make_request(f"rates/{pair_string}")
            if not rates_data or 'rates' not in rates_data:
                continue

            for pair_id, rates_list in rates_data['rates'].items():
                parts = pair_id.split('-')
                if len(parts) < 2:
                    continue
                to_id = int(parts[1])
                to_ticker = valid_targets.get(to_id)
                if not to_ticker:
                    continue

                if to_ticker not in pairs:
                    pairs[to_ticker] = []

                for rate_data in rates_list:
                    try:
                        rate = float(rate_data['rate'])
                        if rate <= 0:
                            continue
                        exchanger_id = rate_data['changer']
                        exchanger_name = self.changers.get(exchanger_id, f"Exchanger #{exchanger_id}")
                        pairs[to_ticker].append({
                            'rate': rate,
                            'exchanger': exchanger_name,
                            'exchanger_id': exchanger_id,
                            'reserve': float(rate_data.get('reserve', 0)),
                            'give': float(rate_data.get('inmin', 0)),
                        })
                    except (ValueError, TypeError, KeyError):
                        continue

        for to_ticker in pairs:
            pairs[to_ticker].sort(key=lambda x: x['rate'], reverse=True)

        return (from_ticker, pairs) if pairs else None
