import asyncio
from typing import List, Dict
from datetime import datetime


class ArbitrageAnalyzerAsync:
    """Анализатор арбитражных возможностей с поддержкой Bybit, Binance и BestChange"""

    def __init__(self, bybit_client, binance_client, bestchange_client):
        self.bybit = bybit_client
        self.binance = binance_client
        self.bestchange = bestchange_client

    async def find_circular_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.5,
            top_count: int = 10
    ) -> List[Dict]:
        """
        Ищет круговые арбитражные возможности по схемам:
        1. Bybit → BestChange → Bybit (USDT → CoinA → CoinB → USDT)
        2. Binance → BestChange → Binance (USDT → CoinA → CoinB → USDT)
        3. Bybit → BestChange → Binance (USDT → CoinA → CoinB → USDT)
        4. Binance → BestChange → Bybit (USDT → CoinA → CoinB → USDT)
        5. Bybit → Binance (прямая связка) (USDT → Coin → USDT)
        """

        print(f"\n[Analyzer] 🔍 Начало поиска арбитражных возможностей")
        print(f"[Analyzer] Параметры: начальная сумма = ${start_amount}, мин. спред = {min_spread}%")

        opportunities = []

        # Собираем все возможности из разных схем
        opportunities.extend(await self._find_exchange_bestchange_exchange(
            start_amount, min_spread, "Bybit", self.bybit.usdt_pairs, self.bybit.usdt_pairs
        ))

        opportunities.extend(await self._find_exchange_bestchange_exchange(
            start_amount, min_spread, "Binance", self.binance.usdt_pairs, self.binance.usdt_pairs
        ))

        opportunities.extend(await self._find_cross_exchange_bestchange(
            start_amount, min_spread, "Bybit", "Binance", self.bybit.usdt_pairs, self.binance.usdt_pairs
        ))

        opportunities.extend(await self._find_cross_exchange_bestchange(
            start_amount, min_spread, "Binance", "Bybit", self.binance.usdt_pairs, self.bybit.usdt_pairs
        ))

        opportunities.extend(await self._find_direct_exchange_arbitrage(
            start_amount, min_spread
        ))

        # Сортируем и выводим результаты
        opportunities.sort(key=lambda x: x['spread'], reverse=True)
        top_opportunities = opportunities[:top_count]

        self._print_results(top_opportunities, min_spread, start_amount)

        return top_opportunities

    async def _find_exchange_bestchange_exchange(
            self,
            start_amount: float,
            min_spread: float,
            exchange_name: str,
            buy_prices: Dict[str, float],
            sell_prices: Dict[str, float]
    ) -> List[Dict]:
        """
        Схема: Exchange → BestChange → Exchange
        Например: Bybit (USDT→CoinA) → BestChange (CoinA→CoinB) → Bybit (CoinB→USDT)
        """

        print(f"\n[Analyzer] 🔄 Анализ схемы: {exchange_name} → BestChange → {exchange_name}")

        opportunities = []
        rates = self.bestchange.rates

        if not buy_prices or not rates:
            return opportunities

        common_coins = set(buy_prices.keys()) & set(rates.keys())
        checked = 0

        for coin_a in common_coins:
            for coin_b in common_coins:
                if coin_b == coin_a:
                    continue

                if coin_a not in rates or coin_b not in rates.get(coin_a, {}):
                    continue

                exch_list_ab = rates[coin_a][coin_b]
                if not exch_list_ab:
                    continue

                try:
                    checked += 1

                    # Шаг 1: USDT → CoinA на бирже
                    price_a = buy_prices[coin_a]
                    if price_a <= 0:
                        continue
                    amount_a = start_amount / price_a

                    # Шаг 2: CoinA → CoinB на BestChange
                    bestchange_rate = exch_list_ab[0]['rate']
                    if bestchange_rate <= 0:
                        continue
                    amount_b = amount_a / bestchange_rate

                    # Шаг 3: CoinB → USDT на бирже
                    if coin_b not in sell_prices:
                        continue
                    price_b = sell_prices[coin_b]
                    if price_b <= 0:
                        continue

                    final_usdt = amount_b * price_b
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    if spread < min_spread:
                        continue

                    opportunities.append({
                        'path': f"USDT → {coin_a} → {coin_b} → USDT",
                        'scheme': f"{exchange_name} → BestChange → {exchange_name}",
                        'coins': [coin_a, coin_b],
                        'initial': start_amount,
                        'final': final_usdt,
                        'profit': final_usdt - start_amount,
                        'spread': spread,
                        'steps': [
                            f"1. [{exchange_name}] Купить {amount_a:.8f} {coin_a} за {start_amount:.2f} USDT (цена: ${price_a:.8f})",
                            f"2. [BestChange] Обменять {amount_a:.8f} {coin_a} → {amount_b:.8f} {coin_b}",
                            f"   Курс: {bestchange_rate:.6f}, Обменник: {exch_list_ab[0]['exchanger']}",
                            f"3. [{exchange_name}] Продать {amount_b:.8f} {coin_b} за {final_usdt:.2f} USDT (цена: ${price_b:.8f})"
                        ],
                        'debug': {
                            'buy_exchange': exchange_name,
                            'sell_exchange': exchange_name,
                            'buy_price_a': price_a,
                            'sell_price_b': price_b,
                            'bestchange_rate': bestchange_rate,
                            'exchanger': exch_list_ab[0]['exchanger'],
                            'reserve': exch_list_ab[0].get('reserve', 0)
                        }
                    })

                except (KeyError, ZeroDivisionError, TypeError):
                    continue

        print(f"[Analyzer]   Проверено путей: {checked}, найдено возможностей: {len(opportunities)}")
        return opportunities

    async def _find_cross_exchange_bestchange(
            self,
            start_amount: float,
            min_spread: float,
            buy_exchange: str,
            sell_exchange: str,
            buy_prices: Dict[str, float],
            sell_prices: Dict[str, float]
    ) -> List[Dict]:
        """
        Схема: Exchange1 → BestChange → Exchange2
        Например: Bybit (USDT→CoinA) → BestChange (CoinA→CoinB) → Binance (CoinB→USDT)
        """

        print(f"\n[Analyzer] 🔄 Анализ схемы: {buy_exchange} → BestChange → {sell_exchange}")

        opportunities = []
        rates = self.bestchange.rates

        if not buy_prices or not sell_prices or not rates:
            return opportunities

        common_buy = set(buy_prices.keys()) & set(rates.keys())
        checked = 0

        for coin_a in common_buy:
            for coin_b in set(sell_prices.keys()):
                if coin_b == coin_a:
                    continue

                if coin_a not in rates or coin_b not in rates.get(coin_a, {}):
                    continue

                exch_list_ab = rates[coin_a][coin_b]
                if not exch_list_ab:
                    continue

                try:
                    checked += 1

                    # Шаг 1: USDT → CoinA на первой бирже
                    price_a = buy_prices[coin_a]
                    if price_a <= 0:
                        continue
                    amount_a = start_amount / price_a

                    # Шаг 2: CoinA → CoinB на BestChange
                    bestchange_rate = exch_list_ab[0]['rate']
                    if bestchange_rate <= 0:
                        continue
                    amount_b = amount_a / bestchange_rate

                    # Шаг 3: CoinB → USDT на второй бирже
                    price_b = sell_prices[coin_b]
                    if price_b <= 0:
                        continue

                    final_usdt = amount_b * price_b
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    if spread < min_spread:
                        continue

                    opportunities.append({
                        'path': f"USDT → {coin_a} → {coin_b} → USDT",
                        'scheme': f"{buy_exchange} → BestChange → {sell_exchange}",
                        'coins': [coin_a, coin_b],
                        'initial': start_amount,
                        'final': final_usdt,
                        'profit': final_usdt - start_amount,
                        'spread': spread,
                        'steps': [
                            f"1. [{buy_exchange}] Купить {amount_a:.8f} {coin_a} за {start_amount:.2f} USDT (цена: ${price_a:.8f})",
                            f"2. [BestChange] Обменять {amount_a:.8f} {coin_a} → {amount_b:.8f} {coin_b}",
                            f"   Курс: {bestchange_rate:.6f}, Обменник: {exch_list_ab[0]['exchanger']}",
                            f"3. [{sell_exchange}] Продать {amount_b:.8f} {coin_b} за {final_usdt:.2f} USDT (цена: ${price_b:.8f})"
                        ],
                        'debug': {
                            'buy_exchange': buy_exchange,
                            'sell_exchange': sell_exchange,
                            'buy_price_a': price_a,
                            'sell_price_b': price_b,
                            'bestchange_rate': bestchange_rate,
                            'exchanger': exch_list_ab[0]['exchanger'],
                            'reserve': exch_list_ab[0].get('reserve', 0)
                        }
                    })

                except (KeyError, ZeroDivisionError, TypeError):
                    continue

        print(f"[Analyzer]   Проверено путей: {checked}, найдено возможностей: {len(opportunities)}")
        return opportunities

    async def _find_direct_exchange_arbitrage(
            self,
            start_amount: float,
            min_spread: float
    ) -> List[Dict]:
        """
        Схема: Прямой арбитраж между биржами (оба направления)
        Bybit → Binance И Binance → Bybit
        """

        print(f"\n[Analyzer] 🔄 Анализ схемы: Прямой арбитраж Bybit ↔ Binance")

        opportunities = []

        bybit_prices = self.bybit.usdt_pairs
        binance_prices = self.binance.usdt_pairs

        if not bybit_prices or not binance_prices:
            return opportunities

        common_coins = set(bybit_prices.keys()) & set(binance_prices.keys())
        checked = 0

        for coin in common_coins:
            try:
                checked += 1

                bybit_price = bybit_prices[coin]
                binance_price = binance_prices[coin]

                if bybit_price <= 0 or binance_price <= 0:
                    continue

                # Вариант 1: Покупка на Bybit, продажа на Binance
                amount_coin_1 = start_amount / bybit_price
                final_usdt_1 = amount_coin_1 * binance_price
                spread_1 = ((final_usdt_1 - start_amount) / start_amount) * 100

                if spread_1 >= min_spread:
                    opportunities.append({
                        'path': f"USDT → {coin} → USDT",
                        'scheme': "Bybit → Binance (прямой арбитраж)",
                        'coins': [coin],
                        'initial': start_amount,
                        'final': final_usdt_1,
                        'profit': final_usdt_1 - start_amount,
                        'spread': spread_1,
                        'steps': [
                            f"1. [Bybit] Купить {amount_coin_1:.8f} {coin} за {start_amount:.2f} USDT (цена: ${bybit_price:.8f})",
                            f"2. Перевод {coin} с Bybit на Binance",
                            f"3. [Binance] Продать {amount_coin_1:.8f} {coin} за {final_usdt_1:.2f} USDT (цена: ${binance_price:.8f})"
                        ],
                        'debug': {
                            'buy_exchange': 'Bybit',
                            'sell_exchange': 'Binance',
                            'buy_price': bybit_price,
                            'sell_price': binance_price,
                            'price_diff': binance_price - bybit_price,
                            'price_diff_percent': ((binance_price - bybit_price) / bybit_price) * 100
                        }
                    })

                # Вариант 2: Покупка на Binance, продажа на Bybit
                amount_coin_2 = start_amount / binance_price
                final_usdt_2 = amount_coin_2 * bybit_price
                spread_2 = ((final_usdt_2 - start_amount) / start_amount) * 100

                if spread_2 >= min_spread:
                    opportunities.append({
                        'path': f"USDT → {coin} → USDT",
                        'scheme': "Binance → Bybit (прямой арбитраж)",
                        'coins': [coin],
                        'initial': start_amount,
                        'final': final_usdt_2,
                        'profit': final_usdt_2 - start_amount,
                        'spread': spread_2,
                        'steps': [
                            f"1. [Binance] Купить {amount_coin_2:.8f} {coin} за {start_amount:.2f} USDT (цена: ${binance_price:.8f})",
                            f"2. Перевод {coin} с Binance на Bybit",
                            f"3. [Bybit] Продать {amount_coin_2:.8f} {coin} за {final_usdt_2:.2f} USDT (цена: ${bybit_price:.8f})"
                        ],
                        'debug': {
                            'buy_exchange': 'Binance',
                            'sell_exchange': 'Bybit',
                            'buy_price': binance_price,
                            'sell_price': bybit_price,
                            'price_diff': bybit_price - binance_price,
                            'price_diff_percent': ((bybit_price - binance_price) / binance_price) * 100
                        }
                    })

            except (KeyError, ZeroDivisionError, TypeError):
                continue

        print(f"[Analyzer]   Проверено монет: {checked}, найдено возможностей: {len(opportunities)}")
        return opportunities

    def _print_results(self, opportunities: List[Dict], min_spread: float, start_amount: float):
        """Выводит результаты анализа"""

        if opportunities:
            print("\n" + "=" * 100)
            print(f"🎯 ТОП-{len(opportunities)} АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
            print("=" * 100 + "\n")

            for idx, opp in enumerate(opportunities, 1):
                print(f"#{idx} | Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                print(f"    Схема: {opp['scheme']}")
                print(f"    Путь: {opp['path']}")
                print(f"    Детали:")
                for step in opp['steps']:
                    print(f"       {step}")

                if 'debug' in opp and 'reserve' in opp['debug']:
                    reserve = opp['debug'].get('reserve', 0)
                    if reserve > 0:
                        print(f"    💰 Резерв обменника: ${reserve:.2f}")
                print()
        else:
            print(f"\n❌ Арбитражных возможностей со спредом >= {min_spread}% не найдено")
            print(f"\n💡 РЕКОМЕНДАЦИИ:")
            print(f"   1. Уменьшите MIN_SPREAD в configs.py (попробуйте 0.1% или даже 0.01%)")
            print(f"   2. Проверьте, что все API доступны и возвращают актуальные данные")
            print(f"   3. Учтите комиссии бирж (~0.1-0.2%) и обменников (~0.5-2%)")
            print(f"   4. Учтите комиссии за вывод и перевод между биржами")