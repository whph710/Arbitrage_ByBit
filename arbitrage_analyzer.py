import asyncio
from typing import List, Dict
from datetime import datetime


class ArbitrageAnalyzerAsync:
    """Анализатор с детальной отладкой"""

    def __init__(self, bybit_client, bestchange_client):
        self.bybit = bybit_client
        self.bestchange = bestchange_client

    async def find_circular_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.5,
            top_count: int = 10
    ) -> List[Dict]:
        """Ищет круговые арбитражные возможности с детальной отладкой"""

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

        # Детальная статистика
        debug_stats = {
            'total_combinations': 0,
            'has_bestchange_rate': 0,
            'passed_filters': 0,
            'negative_spread': 0,
            'below_min_spread': 0,
            'examples': []  # Сохраним несколько примеров для анализа
        }

        example_count = 0
        max_examples = 5

        for coin_a in common_coins:
            for coin_b in common_coins:
                if coin_b == coin_a:
                    continue

                debug_stats['total_combinations'] += 1

                # Проверяем наличие курса в BestChange
                if coin_a not in rates or coin_b not in rates.get(coin_a, {}):
                    continue

                exch_list_ab = rates[coin_a][coin_b]
                if not exch_list_ab:
                    continue

                debug_stats['has_bestchange_rate'] += 1

                try:
                    checked_paths += 1

                    # ═══════════════════════════════════════════════════════════
                    # Шаг 1: USDT -> CoinA на Bybit
                    # ═══════════════════════════════════════════════════════════
                    price_a = bybit_prices[coin_a]
                    if price_a <= 0:
                        continue

                    amount_a = start_amount / price_a

                    # ═══════════════════════════════════════════════════════════
                    # Шаг 2: CoinA -> CoinB на BestChange
                    # ═══════════════════════════════════════════════════════════
                    bestchange_rate = exch_list_ab[0]['rate']

                    if bestchange_rate <= 0:
                        continue

                    # ПРАВИЛЬНАЯ формула (без инверсии):
                    # Если BestChange говорит "курс 32.42", это значит:
                    # "Нужно отдать 32.42 CoinA, чтобы получить 1 CoinB"
                    # Поэтому: amount_b = amount_a / bestchange_rate

                    amount_b = amount_a / bestchange_rate

                    # ═══════════════════════════════════════════════════════════
                    # Шаг 3: CoinB -> USDT на Bybit
                    # ═══════════════════════════════════════════════════════════
                    if coin_b not in bybit_prices:
                        continue

                    price_b = bybit_prices[coin_b]
                    if price_b <= 0:
                        continue

                    final_usdt = amount_b * price_b
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    # Сохраняем пример для анализа (первые 5 путей)
                    if example_count < max_examples:
                        example = {
                            'path': f"{coin_a} → {coin_b}",
                            'bybit_price_a': price_a,
                            'bybit_price_b': price_b,
                            'bestchange_rate': bestchange_rate,
                            'amount_a': amount_a,
                            'amount_b': amount_b,
                            'final_usdt': final_usdt,
                            'spread': spread,
                            'exchanger': exch_list_ab[0]['exchanger'],
                            'calculation': f"{start_amount} USDT → {amount_a:.4f} {coin_a} → {amount_b:.4f} {coin_b} → {final_usdt:.2f} USDT"
                        }
                        debug_stats['examples'].append(example)
                        example_count += 1

                    # Подсчёт статистики
                    if spread < 0:
                        debug_stats['negative_spread'] += 1
                        continue

                    if spread < min_spread:
                        debug_stats['below_min_spread'] += 1
                        continue

                    debug_stats['passed_filters'] += 1

                    # Теоретический курс для проверки
                    theoretical_rate = price_a / price_b if price_b > 0 else 0

                    opportunities.append({
                        'path': f"USDT → {coin_a} → {coin_b} → USDT",
                        'coins': [coin_a, coin_b],
                        'initial': start_amount,
                        'final': final_usdt,
                        'profit': final_usdt - start_amount,
                        'spread': spread,
                        'steps': [
                            f"1. Купить {amount_a:.8f} {coin_a} за {start_amount:.2f} USDT (цена: ${price_a:.8f})",
                            f"2. Обменять {amount_a:.8f} {coin_a} → {amount_b:.8f} {coin_b} (курс BC: {bestchange_rate:.6f})",
                            f"   через {exch_list_ab[0]['exchanger']}",
                            f"3. Продать {amount_b:.8f} {coin_b} за {final_usdt:.2f} USDT (цена: ${price_b:.8f})"
                        ],
                        'debug': {
                            'bybit_price_a': price_a,
                            'bybit_price_b': price_b,
                            'bestchange_rate': bestchange_rate,
                            'theoretical_rate': theoretical_rate,
                            'exchanger': exch_list_ab[0]['exchanger'],
                            'reserve': exch_list_ab[0].get('reserve', 0)
                        }
                    })

                except (KeyError, ZeroDivisionError, TypeError) as e:
                    continue

        # ═══════════════════════════════════════════════════════════
        # ВЫВОД ДЕТАЛЬНОЙ СТАТИСТИКИ
        # ═══════════════════════════════════════════════════════════
        print(f"\n[Analyzer] 📊 ДЕТАЛЬНАЯ СТАТИСТИКА:")
        print(f"  ├─ Всего комбинаций монет: {debug_stats['total_combinations']}")
        print(f"  ├─ Комбинаций с курсом BC: {debug_stats['has_bestchange_rate']}")
        print(f"  ├─ Проверено путей: {checked_paths}")
        print(f"  ├─ С отрицательным спредом: {debug_stats['negative_spread']}")
        print(f"  ├─ Ниже минимального спреда: {debug_stats['below_min_spread']}")
        print(f"  └─ Прошло все фильтры: {debug_stats['passed_filters']}")

        # Показываем примеры расчётов
        if debug_stats['examples']:
            print(f"\n[Analyzer] 🔍 ПРИМЕРЫ РАСЧЁТОВ (первые {len(debug_stats['examples'])}):")
            for i, ex in enumerate(debug_stats['examples'], 1):
                print(f"\n  Пример #{i}: {ex['path']}")
                print(f"    Цена {ex['path'].split(' → ')[0]} на Bybit: ${ex['bybit_price_a']:.8f}")
                print(f"    Цена {ex['path'].split(' → ')[1]} на Bybit: ${ex['bybit_price_b']:.8f}")
                print(
                    f"    Курс BestChange: {ex['bestchange_rate']:.8f} (это {ex['path'].split(' → ')[0]} за 1 {ex['path'].split(' → ')[1]})")
                print(f"    Обменник: {ex['exchanger']}")
                print(f"    Расчёт: {ex['calculation']}")
                print(f"    Спред: {ex['spread']:.4f}% {'✅' if ex['spread'] >= min_spread else '❌ (ниже минимума)'}")

        print(f"\n[Analyzer] Найдено возможностей со спредом >= {min_spread}%: {len(opportunities)}")

        # ═══════════════════════════════════════════════════════════
        # ВЫВОД РЕЗУЛЬТАТОВ
        # ═══════════════════════════════════════════════════════════
        opportunities.sort(key=lambda x: x['spread'], reverse=True)
        top_opportunities = opportunities[:top_count]

        if top_opportunities:
            print("\n" + "=" * 90)
            print(f"🎯 ТОП-{len(top_opportunities)} КРУГОВЫХ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
            print("=" * 90 + "\n")

            for idx, opp in enumerate(top_opportunities, 1):
                print(f"#{idx} | Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                print(f"    Путь: {opp['path']}")
                print(f"    Детали:")
                for step in opp['steps']:
                    print(f"       {step}")

                if 'debug' in opp:
                    reserve = opp['debug'].get('reserve', 0)
                    if reserve > 0:
                        print(f"    💰 Резерв: ${reserve:.2f}")
                print()
        else:
            print(f"\n❌ Арбитражных возможностей со спредом >= {min_spread}% не найдено")
            print(f"\n💡 РЕКОМЕНДАЦИИ:")
            print(f"   1. Уменьшите MIN_SPREAD в configs.py (попробуйте 0.1% или даже 0.01%)")
            print(f"   2. Проверьте примеры расчётов выше - возможно курсы BestChange устарели")
            print(f"   3. Учтите, что в реальности будут комиссии ~0.2-0.5% за операцию")

            # Показываем лучший найденный спред
            all_spreads = [ex['spread'] for ex in debug_stats['examples'] if ex['spread'] >= 0]
            if all_spreads:
                best_spread = max(all_spreads)
                print(f"   4. Лучший найденный спред: {best_spread:.4f}% (но ниже вашего порога {min_spread}%)")

        return top_opportunities