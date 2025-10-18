import aiohttp
from typing import Dict, Set
from configs import BYBIT_API_URL, REQUEST_TIMEOUT, ENABLE_COIN_FILTER, BLACKLIST_COINS, WHITELIST_COINS


class BybitClientAsync:
    """Асинхронный клиент для Bybit API"""

    def __init__(self):
        self.base_url = BYBIT_API_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/3.0)',
            'Accept': 'application/json'
        }
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = None
        self.usdt_pairs: Dict[str, float] = {}
        self.coins: Set[str] = set()
        self.trading_pairs: Set[tuple] = set()  # Реальные торговые пары (base, quote)

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

    def _should_include_coin(self, coin: str) -> bool:
        """
        Проверяет, должна ли монета быть включена в анализ

        Логика:
        1. Если фильтр отключён - включаем всё
        2. Если есть белый список - включаем только из него
        3. Иначе включаем всё, кроме чёрного списка
        """
        if not ENABLE_COIN_FILTER:
            return True

        # Если задан белый список - используем только его
        if WHITELIST_COINS:
            return coin in WHITELIST_COINS

        # Иначе исключаем только чёрный список
        return coin not in BLACKLIST_COINS

    async def load_usdt_pairs(self):
        """Загружает все USDT-пары с Bybit и сохраняет в usdt_pairs и coins"""
        if self.session is None:
            await self.create_session()

        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {'category': 'spot'}
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

            self.usdt_pairs.clear()
            self.coins.clear()
            self.trading_pairs.clear()  # Очищаем торговые пары

            result_list = data.get('result', {}).get('list', [])
            filtered_count = 0

            for ticker in result_list:
                symbol = ticker.get('symbol', '').replace('/', '').upper()

                # Обрабатываем USDT пары
                if symbol.endswith('USDT'):
                    base = symbol[:-4]

                    # Применяем фильтр монет
                    if not self._should_include_coin(base):
                        filtered_count += 1
                        continue

                    try:
                        price = float(ticker.get('lastPrice', 0))
                        if price > 0:
                            self.usdt_pairs[base] = price
                            self.coins.add(base)
                            self.trading_pairs.add(('USDT', base))  # USDT -> BASE
                    except (ValueError, TypeError):
                        continue

                # Сохраняем все остальные торговые пары для треугольного арбитража
                else:
                    # Пытаемся определить базу и квоту
                    # Проверяем распространенные квоты: BTC, ETH, BNB, USDT
                    for quote in ['BTC', 'ETH', 'BNB', 'USDT']:
                        if symbol.endswith(quote) and len(symbol) > len(quote):
                            base = symbol[:-len(quote)]
                            if self._should_include_coin(base) and self._should_include_coin(quote):
                                self.trading_pairs.add((quote, base))  # QUOTE -> BASE
                            break

            print(f"[Bybit] ✓ Загружено {len(self.usdt_pairs)} торговых пар USDT")
            print(f"[Bybit] ✓ Найдено {len(self.trading_pairs)} всех торговых пар")
            if filtered_count > 0:
                print(f"[Bybit] 🔍 Отфильтровано монет: {filtered_count}")

        except Exception as e:
            print(f"[Bybit] ❌ Ошибка при загрузке пар: {e}")

    def has_trading_pair(self, coin_a: str, coin_b: str) -> bool:
        """
        Проверяет наличие торговой пары между двумя монетами

        Args:
            coin_a: Первая монета (база)
            coin_b: Вторая монета (квота)

        Returns:
            True если пара существует (в любом направлении)
        """
        # Проверяем оба направления: A/B и B/A
        return (coin_a, coin_b) in self.trading_pairs or (coin_b, coin_a) in self.trading_pairs

    async def get_usdt_tickers(self) -> Dict[str, float]:
        """Получает все USDT-пары с Bybit (для совместимости со старым кодом)"""
        if not self.usdt_pairs:
            await self.load_usdt_pairs()
        return self.usdt_pairs