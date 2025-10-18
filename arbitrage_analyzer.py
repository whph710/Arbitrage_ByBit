import asyncio
from typing import List, Dict
from datetime import datetime


class ArbitrageAnalyzerAsync:
    """Анализатор арбитражных возможностей для Bybit и Binance"""

    def __init__(self, bybit_client, binance_client):
        self.bybit = bybit_client
        self.binance = binance_client

    async def find_arbitrage_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.3,
            top_count: int = 20
    ) -> List[Dict]:
        """
        Ищет все арбитражные возможности:
        1. Прямой арбитраж между биржами (A→B, B→A)
        2. Треугольный на одной бирже (A: USDT→X→Y→USDT)
        3. Треугольный кросс-биржевой (A: USDT→X, B: X→Y→USDT)
        """

        print(f"\n[Analyzer] 🔍 Начало поиска арбитражных возможностей")
        print(f"[Analyzer] Параметры: начальная сумма = ${start_amount}, мин. спред = {min_spread}%")

        opportunities = []

        # 1. Прямой арбитраж между биржами
        print("\n[Analyzer] 📊 Поиск прямого арбитража Bybit ↔ Binance...")
        direct_opps = await self._find_direct_arbitrage(start_amount, min_spread)
        opportunities.extend(direct_opps)
        print(f"[Analyzer]   ✓ Найдено возможностей: {len(direct_opps)}")

        # 2. Треугольный арбитраж на Bybit
        print("\n[Analyzer] 🔺 Поиск треугольного арбитража на Bybit...")
        bybit_tri = await self._find_triangular_single_exchange(
            start_amount, min_spread, "Bybit", self.bybit
        )
        opportunities.extend(bybit_tri)
        print(f"[Analyzer]   ✓ Найдено возможностей: {len(bybit_tri)}")

        # 3. Треугольный арбитраж на Binance
        print("\n[Analyzer] 🔺 Поиск треугольного арбитража на Binance...")
        binance_tri = await self._find_triangular_single_exchange(
            start_amount, min_spread, "Binance", self.binance
        )
        opportunities.extend(binance_tri)
        print(f"[Analyzer]   ✓ Найдено возможностей: {len(binance_tri)}")

        # 4. Треугольный кросс-биржевой (Bybit → Binance)
        print("\n[Analyzer] 🔀 Поиск кросс-биржевого треугольного арбитража Bybit → Binance...")
        cross_bb = await self._find_triangular_cross_exchange(
            start_amount, min_spread, "Bybit", "Binance",
            self.bybit, self.binance
        )
        opportunities.extend(cross_bb)
        print(f"[Analyzer]   ✓ Найдено возможностей: {len(cross_bb)}")

        # 5. Треугольный кросс-биржевой (Binance → Bybit)
        print("\n[Analyzer] 🔀 Поиск кросс-биржевого треугольного арбитража Binance → Bybit...")
        cross_ab = await self._find_triangular_cross_exchange(
            start_amount, min_spread, "Binance", "Bybit",
            self.binance, self.bybit
        )
        opportunities.extend(cross_ab)
        print(f"[Analyzer]   ✓ Найдено возможностей: {len(cross_ab)}")

        # Сортируем по спреду
        opportunities.sort(key=lambda x: x['spread'], reverse=True)

        # Ограничиваем топ
        if top_count:
            top_opportunities = opportunities[:top_count]
        else:
            top_opportunities = opportunities

        self._print_results(top_opportunities, min_spread, start_amount)

        return top_opportunities

    async def _find_direct_arbitrage(
            self,
            start_amount: float,
            min_spread: float
    ) -> List[Dict]:
        """
        Прямой арбитраж между биржами:
        - Bybit → Binance
        - Binance → Bybit
        """
        opportunities = []

        bybit_prices = self.bybit.usdt_pairs
        binance_prices = self.binance.usdt_pairs

        if not bybit_prices or not binance_prices:
            return opportunities

        common_coins = set(bybit_prices.keys()) & set(binance_prices.keys())

        for coin in common_coins:
            try:
                bybit_price = bybit_prices[coin]
                binance_price = binance_prices[coin]

                if bybit_price <= 0 or binance_price <= 0:
                    continue

                # Вариант 1: Покупка на Bybit → Продажа на Binance
                amount_coin = start_amount / bybit_price
                final_usdt = amount_coin * binance_price
                spread = ((final_usdt - start_amount) / start_amount) * 100

                if spread >= min_spread:
                    opportunities.append({
                        'type': 'direct',
                        'path': f"USDT → {coin} → USDT",
                        'scheme': "Bybit → Binance",
                        'coins': [coin],
                        'initial': start_amount,
                        'final': final_usdt,
                        'profit': final_usdt - start_amount,
                        'spread': spread,
                        'steps': [
                            f"1. Покупка {amount_coin:.6f} {coin} на Bybit по цене ${bybit_price:.6f}",
                            f"2. Перевод {amount_coin:.6f} {coin} с Bybit на Binance",
                            f"3. Продажа {amount_coin:.6f} {coin} на Binance по цене ${binance_price:.6f}"
                        ]
                    })

                # Вариант 2: Покупка на Binance → Продажа на Bybit
                amount_coin = start_amount / binance_price
                final_usdt = amount_coin * bybit_price
                spread = ((final_usdt - start_amount) / start_amount) * 100

                if spread >= min_spread:
                    opportunities.append({
                        'type': 'direct',
                        'path': f"USDT → {coin} → USDT",
                        'scheme': "Binance → Bybit",
                        'coins': [coin],
                        'initial': start_amount,
                        'final': final_usdt,
                        'profit': final_usdt - start_amount,
                        'spread': spread,
                        'steps': [
                            f"1. Покупка {amount_coin:.6f} {coin} на Binance по цене ${binance_price:.6f}",
                            f"2. Перевод {amount_coin:.6f} {coin} с Binance на Bybit",
                            f"3. Продажа {amount_coin:.6f} {coin} на Bybit по цене ${bybit_price:.6f}"
                        ]
                    })

            except (KeyError, ZeroDivisionError, TypeError):
                continue

        return opportunities

    async def _find_triangular_single_exchange(
            self,
            start_amount: float,
            min_spread: float,
            exchange_name: str,
            exchange_client
    ) -> List[Dict]:
        """
        Треугольный арбитраж на одной бирже:
        USDT → CoinA → CoinB → USDT
        """
        opportunities = []
        usdt_pairs = exchange_client.usdt_pairs
        coins = list(usdt_pairs.keys())
        checked = 0

        for i, coin_a in enumerate(coins):
            for coin_b in coins[i + 1:]:
                if coin_a == coin_b:
                    continue

                checked += 1

                # Проверяем, есть ли пара CoinA/CoinB
                if not exchange_client.has_trading_pair(coin_a, coin_b):
                    continue

                try:
                    price_a_usdt = usdt_pairs[coin_a]
                    price_b_usdt = usdt_pairs[coin_b]

                    if price_a_usdt <= 0 or price_b_usdt <= 0:
                        continue

                    price_a_to_b = price_a_usdt / price_b_usdt

                    # Путь 1: USDT → CoinA → CoinB → USDT
                    amount_a = start_amount / price_a_usdt
                    amount_b = amount_a * price_a_to_b
                    final_usdt = amount_b * price_b_usdt
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    if spread >= min_spread:
                        opportunities.append({
                            'type': 'triangular_single',
                            'scheme': exchange_name,
                            'path': f"USDT → {coin_a} → {coin_b} → USDT",
                            'coins': [coin_a, coin_b],
                            'initial': start_amount,
                            'final': final_usdt,
                            'profit': final_usdt - start_amount,
                            'spread': spread,
                            'steps': [
                                f"1. Покупка {amount_a:.6f} {coin_a} за USDT по цене ${price_a_usdt:.6f}",
                                f"2. Обмен {amount_a:.6f} {coin_a} на {amount_b:.6f} {coin_b} (курс {price_a_to_b:.6f})",
                                f"3. Продажа {amount_b:.6f} {coin_b} за USDT по цене ${price_b_usdt:.6f}"
                            ]
                        })

                    # Путь 2: USDT → CoinB → CoinA → USDT (обратное направление)
                    price_b_to_a = price_b_usdt / price_a_usdt
                    amount_b = start_amount / price_b_usdt
                    amount_a = amount_b * price_b_to_a
                    final_usdt = amount_a * price_a_usdt
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    if spread >= min_spread:
                        opportunities.append({
                            'type': 'triangular_single',
                            'scheme': exchange_name,
                            'path': f"USDT → {coin_b} → {coin_a} → USDT",
                            'coins': [coin_b, coin_a],
                            'initial': start_amount,
                            'final': final_usdt,
                            'profit': final_usdt - start_amount,
                            'spread': spread,
                            'steps': [
                                f"1. Покупка {amount_b:.6f} {coin_b} за USDT по цене ${price_b_usdt:.6f}",
                                f"2. Обмен {amount_b:.6f} {coin_b} на {amount_a:.6f} {coin_a} (курс {price_b_to_a:.6f})",
                                f"3. Продажа {amount_a:.6f} {coin_a} за USDT по цене ${price_a_usdt:.6f}"
                            ]
                        })

                except Exception:
                    continue

        return opportunities

    async def _find_triangular_cross_exchange(
            self,
            start_amount: float,
            min_spread: float,
            exchange_1: str,
            exchange_2: str,
            client_1,
            client_2
    ) -> List[Dict]:
        """
        Треугольный кросс-биржевой арбитраж:
        Exchange1: USDT → CoinA
        Exchange2: CoinA → CoinB → USDT
        """
        opportunities = []

        prices_1 = client_1.usdt_pairs
        prices_2 = client_2.usdt_pairs
        common_coins = set(prices_1.keys()) & set(prices_2.keys())

        for coin_a in common_coins:
            for coin_b in prices_2.keys():
                if coin_a == coin_b:
                    continue

                # Проверяем наличие пары CoinA/CoinB на второй бирже
                if not client_2.has_trading_pair(coin_a, coin_b):
                    continue

                try:
                    price_a_exch1 = prices_1[coin_a]
                    price_a_exch2 = prices_2[coin_a]
                    price_b_exch2 = prices_2[coin_b]

                    if price_a_exch1 <= 0 or price_a_exch2 <= 0 or price_b_exch2 <= 0:
                        continue

                    # Покупаем CoinA на Exchange1
                    amount_a = start_amount / price_a_exch1

                    # Обмениваем CoinA на CoinB на Exchange2
                    cross_rate = price_a_exch2 / price_b_exch2
                    amount_b = amount_a * cross_rate

                    # Продаём CoinB за USDT на Exchange2
                    final_usdt = amount_b * price_b_exch2
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    if spread >= min_spread:
                        opportunities.append({
                            'type': 'triangular_cross',
                            'scheme': f"{exchange_1} → {exchange_2}",
                            'path': f"USDT → {coin_a} → {coin_b} → USDT",
                            'coins': [coin_a, coin_b],
                            'initial': start_amount,
                            'final': final_usdt,
                            'profit': final_usdt - start_amount,
                            'spread': spread,
                            'steps': [
                                f"1. Покупка {amount_a:.6f} {coin_a} на {exchange_1} по цене ${price_a_exch1:.6f}",
                                f"2. Перевод {amount_a:.6f} {coin_a} с {exchange_1} на {exchange_2}",
                                f"3. Обмен {amount_a:.6f} {coin_a} на {amount_b:.6f} {coin_b} на {exchange_2} (курс {cross_rate:.6f})",
                                f"4. Продажа {amount_b:.6f} {coin_b} за USDT на {exchange_2} по цене ${price_b_exch2:.6f}"
                            ]
                        })

                except Exception:
                    continue

        return opportunities

    def _print_results(self, opportunities: List[Dict], min_spread: float, start_amount: float):
        """Выводит результаты анализа"""

        if opportunities:
            print("\n" + "=" * 100)
            print(f"🎯 ТОП-{len(opportunities)} АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
            print("=" * 100 + "\n")

            for idx, opp in enumerate(opportunities, 1):
                print(f"#{idx} | {opp['scheme']} | {opp['path']}")
                print(f"   ➜ Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}\n")
        else:
            print(f"\n❌ Арбитражных возможностей со спредом >= {min_spread}% не найдено.")