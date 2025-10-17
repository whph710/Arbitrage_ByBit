import asyncio
from typing import List, Dict, Optional
from datetime import datetime


class ArbitrageAnalyzerAsync:
    """Асинхронный анализатор кругового арбитража"""

    def __init__(self, bybit_client, bestchange_client):
        self.bybit = bybit_client
        self.bestchange = bestchange_client

    async def find_circular_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.5,
            top_count: int = 10
    ) -> List[Dict]:
        """Ищет круговые арбитражные возможности"""

        print(f"[Analyzer] Начало поиска круговых арбитражных возможностей...")
        print(f"[Analyzer] Параметры: начальная сумма = ${start_amount}, мин. спред = {min_spread}%")

        # Получаем цены с Bybit
        bybit_prices = self.bybit.usdt_pairs
        if not bybit_prices:
            print("[Analyzer] Ошибка: цены Bybit не загружены")
            return []

        # Получаем курсы BestChange
        rates = self.bestchange.rates
        if not rates:
            print("[Analyzer] Ошибка: курсы BestChange не загружены")
            return []

        # Находим общие монеты
        common_coins = set(bybit_prices.keys()) & set(rates.keys())
        print(f"[Analyzer] Найдено общих монет для анализа: {len(common_coins)}")

        if not common_coins:
            print("[Analyzer] Нет общих монет между Bybit и BestChange")
            return []

        opportunities = []
        checked_paths = 0

        # Перебираем все возможные круговые пути
        for coin_a in common_coins:
            if coin_a not in rates:
                continue

            for coin_b in rates[coin_a].keys():
                if coin_b not in bybit_prices:
                    continue

                exch_list_ab = rates[coin_a][coin_b]
                if not exch_list_ab:
                    continue

                for coin_c in common_coins:
                    if coin_c == coin_a or coin_c not in bybit_prices:
                        continue

                    # Путь: USDT -> coin_a (Bybit) -> coin_b (BestChange) -> coin_c (Bybit) -> USDT (Bybit)
                    try:
                        checked_paths += 1

                        # Шаг 1: USDT -> coin_a на Bybit
                        amount_a = start_amount / bybit_prices[coin_a]

                        # Шаг 2: coin_a -> coin_b на BestChange
                        best_rate_ab = exch_list_ab[0]['rate']
                        amount_b = amount_a * best_rate_ab

                        # Шаг 3: coin_b -> coin_c на Bybit
                        if coin_b not in bybit_prices:
                            continue
                        amount_c = amount_b / bybit_prices[coin_b]

                        # Шаг 4: coin_c -> USDT на Bybit
                        final_usdt = amount_c * bybit_prices[coin_c]

                        # Вычисляем спред
                        spread = ((final_usdt - start_amount) / start_amount) * 100

                        if spread >= min_spread:
                            opportunities.append({
                                'path': f"USDT → {coin_a} → {coin_b} → {coin_c} → USDT",
                                'coins': [coin_a, coin_b, coin_c],
                                'initial': start_amount,
                                'final': final_usdt,
                                'profit': final_usdt - start_amount,
                                'spread': spread,
                                'steps': [
                                    f"1. Купить {coin_a} за {start_amount:.2f} USDT на Bybit (цена: {bybit_prices[coin_a]:.8f})",
                                    f"2. Обменять {amount_a:.8f} {coin_a} на {amount_b:.8f} {coin_b} через {exch_list_ab[0]['exchanger']} (курс: {best_rate_ab:.8f})",
                                    f"3. Продать {amount_b:.8f} {coin_b} за {amount_c:.8f} {coin_c} на Bybit (цена: {bybit_prices[coin_b]:.8f})",
                                    f"4. Продать {amount_c:.8f} {coin_c} за {final_usdt:.2f} USDT на Bybit (цена: {bybit_prices[coin_c]:.8f})"
                                ]
                            })
                    except (KeyError, ZeroDivisionError, TypeError) as e:
                        continue

        print(f"[Analyzer] Проверено путей: {checked_paths}")
        print(f"[Analyzer] Найдено возможностей со спредом >= {min_spread}%: {len(opportunities)}")

        # Сортируем по спреду
        opportunities.sort(key=lambda x: x['spread'], reverse=True)
        top_opportunities = opportunities[:top_count]

        # Выводим результаты
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