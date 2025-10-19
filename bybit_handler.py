import aiohttp
from typing import Dict, Set, Tuple, Optional
from configs import (
    BYBIT_API_URL, REQUEST_TIMEOUT, ENABLE_COIN_FILTER,
    BLACKLIST_COINS, WHITELIST_COINS, MIN_24H_VOLUME_USDT,
    MIN_LIQUIDITY_SCORE
)


class BybitClientAsync:
    """Асинхронный клиент для Bybit API с поддержкой фильтрации по ликвидности"""

    def __init__(self):
        self.base_url = BYBIT_API_URL
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ArbitrageBot/7.0)',
            'Accept': 'application/json'
        }
        self.timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        self.session = None

        # Структуры данных
        self.usdt_pairs: Dict[str, float] = {}  # {coin: price}
        self.coins: Set[str] = set()
        self.trading_pairs: Dict[Tuple[str, str], float] = {}  # {(base, quote): price}

        # Данные о ликвидности
        self.pair_volumes: Dict[Tuple[str, str], float] = {}  # 24h объём в USDT
        self.pair_liquidity: Dict[Tuple[str, str], float] = {}  # Оценка ликвидности (0-100)

        # Статистика фильтрации
        self.filtered_by_volume = 0
        self.filtered_by_liquidity = 0

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
        """Проверяет, должна ли монета быть включена в анализ"""
        if not ENABLE_COIN_FILTER:
            return True
        if WHITELIST_COINS:
            return coin in WHITELIST_COINS
        return coin not in BLACKLIST_COINS

    def _calculate_liquidity_score(
            self,
            volume_24h: float,
            turnover_24h: float,
            bid_ask_spread_pct: float = None
    ) -> float:
        """
        Рассчитывает оценку ликвидности пары (0-100)

        Факторы:
        - Объём торгов за 24ч (0-50 баллов)
        - Оборот за 24ч (0-30 баллов)
        - Спред bid/ask (0-20 баллов)
        """
        score = 0.0

        # Оценка по объёму
        if volume_24h >= 1000000:
            score += 50
        elif volume_24h >= 500000:
            score += 40
        elif volume_24h >= 100000:
            score += 30
        elif volume_24h >= 50000:
            score += 20
        elif volume_24h >= 10000:
            score += 10

        # Оценка по обороту
        if turnover_24h >= 10000000:
            score += 30
        elif turnover_24h >= 5000000:
            score += 25
        elif turnover_24h >= 1000000:
            score += 20
        elif turnover_24h >= 500000:
            score += 15
        elif turnover_24h >= 100000:
            score += 10

        # Оценка по спреду
        if bid_ask_spread_pct is not None:
            if bid_ask_spread_pct <= 0.05:
                score += 20
            elif bid_ask_spread_pct <= 0.1:
                score += 15
            elif bid_ask_spread_pct <= 0.2:
                score += 10
            elif bid_ask_spread_pct <= 0.5:
                score += 5
        else:
            score += 10  # Средний балл если спред неизвестен

        return min(score, 100.0)

    async def load_usdt_pairs(self):
        """Загружает все торговые пары с Bybit с фильтрацией по ликвидности"""
        if self.session is None:
            await self.create_session()

        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {'category': 'spot'}

            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

            # Очистка данных
            self.usdt_pairs.clear()
            self.coins.clear()
            self.trading_pairs.clear()
            self.pair_volumes.clear()
            self.pair_liquidity.clear()

            filtered_count = 0
            self.filtered_by_volume = 0
            self.filtered_by_liquidity = 0

            result_list = data.get('result', {}).get('list', [])
            quote_currencies = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB', 'BUSD', 'DAI', 'TRX', 'XRP', 'SOL', 'DOGE']

            for ticker in result_list:
                symbol = ticker.get('symbol', '').replace('/', '').upper()

                try:
                    price = float(ticker.get('lastPrice', 0))
                    if price <= 0:
                        continue

                    volume_24h = float(ticker.get('volume24h', 0))
                    turnover_24h = float(ticker.get('turnover24h', 0))
                    bid = float(ticker.get('bid1Price', 0))
                    ask = float(ticker.get('ask1Price', 0))

                    bid_ask_spread_pct = None
                    if bid > 0 and ask > 0:
                        bid_ask_spread_pct = ((ask - bid) / bid) * 100

                except (ValueError, TypeError):
                    continue

                # Определяем base и quote
                base = None
                quote = None
                for potential_quote in quote_currencies:
                    if symbol.endswith(potential_quote) and len(symbol) > len(potential_quote):
                        quote = potential_quote
                        base = symbol[:-len(potential_quote)]
                        break

                if not base or not quote:
                    continue

                # Применяем фильтр монет
                if not self._should_include_coin(base) or not self._should_include_coin(quote):
                    filtered_count += 1
                    continue

                # ФИЛЬТР 1: Минимальный объём за 24ч
                volume_usdt = turnover_24h if quote == 'USDT' else volume_24h * price
                if volume_usdt < MIN_24H_VOLUME_USDT:
                    self.filtered_by_volume += 1
                    continue

                # ФИЛЬТР 2: Оценка ликвидности
                liquidity_score = self._calculate_liquidity_score(
                    volume_24h, turnover_24h, bid_ask_spread_pct
                )
                if liquidity_score < MIN_LIQUIDITY_SCORE:
                    self.filtered_by_liquidity += 1
                    continue

                # Сохраняем пару
                self.trading_pairs[(base, quote)] = price
                self.pair_volumes[(base, quote)] = volume_usdt
                self.pair_liquidity[(base, quote)] = liquidity_score
                self.coins.add(base)
                self.coins.add(quote)

                if quote == 'USDT':
                    self.usdt_pairs[base] = price

            print(f"[Bybit] ✓ Загружено {len(self.usdt_pairs)} USDT-пар")
            print(f"[Bybit] ✓ Всего уникальных монет: {len(self.coins)}")
            print(f"[Bybit] ✓ Всего торговых пар (ликвидных): {len(self.trading_pairs)}")

            if filtered_count > 0:
                print(f"[Bybit] 🔍 Отфильтровано по white/blacklist: {filtered_count}")
            if self.filtered_by_volume > 0:
                print(
                    f"[Bybit] 📉 Отфильтровано по объёму (<${MIN_24H_VOLUME_USDT:,.0f} за 24ч): {self.filtered_by_volume}")
            if self.filtered_by_liquidity > 0:
                print(
                    f"[Bybit] 💧 Отфильтровано по ликвидности (score <{MIN_LIQUIDITY_SCORE}): {self.filtered_by_liquidity}")

            # Топ-10 самых ликвидных пар
            top_liquid = sorted(self.pair_liquidity.items(), key=lambda x: x[1], reverse=True)[:10]
            print(f"\n[Bybit] 🏆 Топ-10 самых ликвидных пар:")
            for (base, quote), score in top_liquid:
                volume = self.pair_volumes.get((base, quote), 0)
                price = self.trading_pairs.get((base, quote), 0)
                print(f"        {base}/{quote}: оценка {score:.1f}, объём ${volume:,.0f}, цена {price:.8f}")

        except Exception as e:
            print(f"[Bybit] ❌ Ошибка при загрузке пар: {e}")

    def get_price(self, base: str, quote: str) -> Optional[float]:
        """Получает цену для пары BASE/QUOTE"""
        direct = self.trading_pairs.get((base, quote))
        if direct is not None:
            return direct
        reverse = self.trading_pairs.get((quote, base))
        if reverse is not None and reverse > 0:
            return 1.0 / reverse
        return None

    def get_liquidity_score(self, base: str, quote: str) -> float:
        """Получает оценку ликвидности пары"""
        score = self.pair_liquidity.get((base, quote))
        if score is not None:
            return score
        score = self.pair_liquidity.get((quote, base))
        return score if score is not None else 0.0

    def get_volume_24h(self, base: str, quote: str) -> float:
        """Получает объём торгов за 24ч в USDT"""
        volume = self.pair_volumes.get((base, quote))
        if volume is not None:
            return volume
        volume = self.pair_volumes.get((quote, base))
        return volume if volume is not None else 0.0

    def has_trading_pair(self, base: str, quote: str) -> bool:
        """Проверяет наличие торговой пары"""
        return self.get_price(base, quote) is not None

    def is_liquid_pair(self, base: str, quote: str) -> bool:
        """Проверяет, является ли пара ликвидной"""
        return self.get_liquidity_score(base, quote) >= MIN_LIQUIDITY_SCORE

    async def get_usdt_tickers(self) -> Dict[str, float]:
        """Получает все USDT-пары (для совместимости)"""
        if not self.usdt_pairs:
            await self.load_usdt_pairs()
        return self.usdt_pairs

    def get_available_quotes_for(self, base: str) -> Set[str]:
        """Возвращает все валюты, с которыми может торговаться base"""
        quotes = set()
        for (b, q) in self.trading_pairs.keys():
            if b == base:
                quotes.add(q)
            elif q == base:
                quotes.add(b)
        return quotes

    def get_liquid_usdt_coins(self) -> list:
        """Возвращает список монет с USDT-парами, отсортированных по ликвидности"""
        coins_with_scores = []
        for coin in self.usdt_pairs.keys():
            score = self.get_liquidity_score(coin, 'USDT')
            volume = self.get_volume_24h(coin, 'USDT')
            coins_with_scores.append((coin, score, volume))
        coins_with_scores.sort(key=lambda x: x[1], reverse=True)
        return [coin for coin, score, volume in coins_with_scores]