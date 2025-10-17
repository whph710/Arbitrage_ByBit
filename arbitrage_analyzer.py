import asyncio
from typing import List, Dict
from datetime import datetime


class ArbitrageAnalyzerAsync:
    """Асинхронный анализатор кругового арбитража (3-ступенчатые цепочки)"""

    def __init__(self, bybit_client, bestchange_client):
        self.bybit = bybit_client
        self.bestchange = bestchange_client

    async def find_circular_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.5,
            top_count: int = 10
    ) -> List[Dict]:
        """Ищет круговые арбитражные возможности через 2 промежуточные монеты"""

        print(f"[Analyzer] Начало поиска кругового арбитража (USDT → CoinA → CoinB → USDT)")
        print(f"[Analyzer] Параметры: начальная сумма = ${start_amount}, мин. спред = {min_spread}%")

        bybit_prices = self.bybit.usdt_pairs
        rates = self.bestchange.rates

        if not bybit_prices or not rates:
            print("[Analyzer] Ошибка: данные Bybit или BestChange не загружены")
            return []

        common_coins = set(bybit_prices.keys()) & set(rates.keys())
        print(f"[Analyzer] Найдено общих монет для анализа: {len(common_coins)}")

        if not common_coins:
            print("[Analyzer] Нет общих монет для анализа")
            return []

        opportunities = []
        checked_paths = 0

        # Ограничиваем цепочку до двух промежуточных монет
        for coin_a in common_coins:
            for coin_b in common_coins:
                if coin_b == coin_a:
                    continue
                if coin_b not in rates[coin_a]:
                    continue

                exch_list_ab = rates[coin_a][coin_b]
                if not exch_list_ab:
                    continue

                try:
                    checked_paths += 1

                    # USDT -> CoinA на Bybit
                    amount_a = start_amount / bybit_prices[coin_a]

                    # CoinA -> CoinB на BestChange
                    best_rate_ab = exch_list_ab[0]['rate']
                    amount_b = amount_a * best_rate_ab

                    # CoinB -> USDT на Bybit
                    if coin_b not in bybit_prices:
                        continue
                    final_usdt = amount_b * bybit_prices[coin_b]

                    # Вычисляем спред
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    if spread >= min_spread:
                        opportunities.append({
                            'path': f"USDT → {coin_a} → {coin_b} → USDT",
                            'coins': [coin_a, coin_b],
                            'initial': start_amount,
                            'final': final_usdt,
                            'profit': final_usdt - start_amount,
                            'spread': spread,
                            'steps': [
                                f"1. Купить {coin_a} за {start_amount:.2f} USDT на Bybit (цена: {bybit_prices[coin_a]:.8f})",
                                f"2. Обменять {amount_a:.8f} {coin_a} на {amount_b:.8f} {coin_b} через {exch_list_ab[0]['exchanger']} (курс: {best_rate_ab:.8f})",
                                f"3. Продать {amount_b:.8f} {coin_b} за {final_usdt:.2f} USDT на Bybit (цена: {bybit_prices[coin_b]:.8f})"
                            ]
                        })
                except (KeyError, ZeroDivisionError, TypeError):
                    continue

        print(f"[Analyzer] Проверено путей: {checked_paths}")
        print(f"[Analyzer] Найдено возможностей со спредом >= {min_spread}%: {len(opportunities)}")

        opportunities.sort(key=lambda x: x['spread'], reverse=True)
        top_opportunities = opportunities[:top_count]

        if top_opportunities:
            print("\n" + "=" * 90)
            print(f"🎯 ТОП-{len(top_opportunities)} КРУГОВЫХ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
            print("=" * 90 + "\n")

            for idx, opp in enumerate(top_opportunities, 1):
                print(f"#{idx} | Спред: {opp['spread']:.2f}% | Прибыль: ${opp['profit']:.2f}")
                print(f"    Путь: {opp['path']}")
                print(f"    Детали:")
                for step in opp['steps']:
                    print(f"       {step}")
                print()
        else:
            print(f"\n❌ Арбитражных возможностей со спредом >= {min_spread}% не найдено\n")

        return top_opportunities
