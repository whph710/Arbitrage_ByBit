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

                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: проверяем направление обмена CoinA -> CoinB
                if coin_a not in rates or coin_b not in rates.get(coin_a, {}):
                    continue

                exch_list_ab = rates[coin_a][coin_b]
                if not exch_list_ab:
                    continue

                try:
                    checked_paths += 1

                    # Шаг 1: USDT -> CoinA на Bybit (покупаем CoinA)
                    price_a = bybit_prices[coin_a]
                    if price_a <= 0:
                        continue
                    amount_a = start_amount / price_a

                    # Шаг 2: CoinA -> CoinB на BestChange
                    # rate показывает: сколько CoinB вы ПОЛУЧИТЕ за 1 CoinA
                    best_rate_ab = exch_list_ab[0]['rate']

                    # ВАЖНАЯ ПРОВЕРКА: курс должен быть разумным
                    # Если курс слишком большой (>1000000), это может быть ошибка данных
                    if best_rate_ab > 1000000:
                        print(f"[Analyzer] ⚠️ Подозрительный курс {coin_a}→{coin_b}: {best_rate_ab:.2f} (пропускаем)")
                        continue

                    if best_rate_ab <= 0:
                        continue

                    amount_b = amount_a * best_rate_ab

                    # Шаг 3: CoinB -> USDT на Bybit (продаем CoinB)
                    if coin_b not in bybit_prices:
                        continue
                    price_b = bybit_prices[coin_b]
                    if price_b <= 0:
                        continue

                    final_usdt = amount_b * price_b

                    # Дополнительная проверка на адекватность результата
                    # Если итоговая сумма больше начальной в 1000+ раз, это явная ошибка
                    if final_usdt > start_amount * 1000:
                        print(f"[Analyzer] ⚠️ Неадекватный результат для {coin_a}→{coin_b}: "
                              f"${start_amount:.2f} → ${final_usdt:.2f} (пропускаем)")
                        continue

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
                                f"1. Купить {coin_a} за {start_amount:.2f} USDT на Bybit (цена: {price_a:.8f})",
                                f"2. Обменять {amount_a:.8f} {coin_a} на {amount_b:.8f} {coin_b} через {exch_list_ab[0]['exchanger']} (курс: {best_rate_ab:.8f})",
                                f"3. Продать {amount_b:.8f} {coin_b} за {final_usdt:.2f} USDT на Bybit (цена: {price_b:.8f})"
                            ],
                            # Добавляем детали для отладки
                            'debug': {
                                'bybit_price_a': price_a,
                                'bybit_price_b': price_b,
                                'bestchange_rate': best_rate_ab,
                                'exchanger': exch_list_ab[0]['exchanger'],
                                'reserve': exch_list_ab[0].get('reserve', 0)
                            }
                        })
                except (KeyError, ZeroDivisionError, TypeError) as e:
                    # Тихо пропускаем ошибки, но можно раскомментировать для отладки
                    # print(f"[Analyzer] Ошибка при обработке {coin_a}→{coin_b}: {e}")
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

                # Показываем резерв обменника для первых 3 результатов
                if idx <= 3 and 'debug' in opp:
                    reserve = opp['debug'].get('reserve', 0)
                    if reserve > 0:
                        print(f"    💰 Резерв обменника: ${reserve:.2f}")
                print()
        else:
            print(f"\n❌ Арбитражных возможностей со спредом >= {min_spread}% не найдено\n")

        return top_opportunities