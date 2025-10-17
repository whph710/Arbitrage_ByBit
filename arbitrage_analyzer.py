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

                # Проверяем направление обмена CoinA -> CoinB
                if coin_a not in rates or coin_b not in rates.get(coin_a, {}):
                    continue

                exch_list_ab = rates[coin_a][coin_b]
                if not exch_list_ab:
                    continue

                try:
                    checked_paths += 1

                    # ═══════════════════════════════════════════════════════════
                    # Шаг 1: USDT -> CoinA на Bybit (покупаем CoinA)
                    # ═══════════════════════════════════════════════════════════
                    price_a = bybit_prices[coin_a]
                    if price_a <= 0:
                        continue
                    amount_a = start_amount / price_a

                    # ═══════════════════════════════════════════════════════════
                    # Шаг 2: CoinA -> CoinB на BestChange
                    # КРИТИЧНО: В BestChange курс показывает обратную логику!
                    # ═══════════════════════════════════════════════════════════
                    #
                    # Пример из документации:
                    # Если курс LUNA→DOT = 32.42, это значит:
                    # "Нужно 32.42 LUNA, чтобы получить 1 DOT"
                    #
                    # Поэтому правильная формула:
                    # amount_b = amount_a / rate (НЕ amount_a * rate)
                    #
                    # Подтверждение:
                    # - LUNA цена: $0.095
                    # - DOT цена: $2.90
                    # - Реальный курс: 0.095/2.90 ≈ 0.033 DOT за 1 LUNA
                    # - BestChange показывает: 1/0.033 ≈ 30-35 (сколько LUNA за 1 DOT)

                    bestchange_rate = exch_list_ab[0]['rate']

                    # Проверка на разумность: курс должен быть положительным
                    if bestchange_rate <= 0:
                        continue

                    # ИНВЕРТИРУЕМ курс BestChange!
                    # Если BestChange говорит "32 LUNA за 1 DOT",
                    # то реальный курс = 1/32 = 0.03125 DOT за 1 LUNA
                    actual_rate = 1.0 / bestchange_rate

                    # Проверка на адекватность инвертированного курса
                    # Курс обмена не может быть больше 100 (редкий случай)
                    if actual_rate > 100:
                        continue

                    amount_b = amount_a * actual_rate

                    # ═══════════════════════════════════════════════════════════
                    # Шаг 3: CoinB -> USDT на Bybit (продаем CoinB)
                    # ═══════════════════════════════════════════════════════════
                    if coin_b not in bybit_prices:
                        continue
                    price_b = bybit_prices[coin_b]
                    if price_b <= 0:
                        continue

                    final_usdt = amount_b * price_b

                    # Проверка на адекватность результата (фильтр явных ошибок)
                    if final_usdt > start_amount * 10:  # максимум 10x прибыль (уже нереально)
                        continue

                    # Вычисляем спред
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    # Отбрасываем отрицательные спреды (убытки)
                    if spread < min_spread:
                        continue

                    opportunities.append({
                        'path': f"USDT → {coin_a} → {coin_b} → USDT",
                        'coins': [coin_a, coin_b],
                        'initial': start_amount,
                        'final': final_usdt,
                        'profit': final_usdt - start_amount,
                        'spread': spread,
                        'steps': [
                            f"1. Купить {coin_a} за {start_amount:.2f} USDT на Bybit (цена: {price_a:.8f})",
                            f"2. Обменять {amount_a:.8f} {coin_a} на {amount_b:.8f} {coin_b} через {exch_list_ab[0]['exchanger']}",
                            f"   ├─ Курс BestChange: {bestchange_rate:.8f} (это {coin_a} за 1 {coin_b})",
                            f"   └─ Реальный курс: {actual_rate:.8f} ({coin_b} за 1 {coin_a})",
                            f"3. Продать {amount_b:.8f} {coin_b} за {final_usdt:.2f} USDT на Bybit (цена: {price_b:.8f})"
                        ],
                        'debug': {
                            'bybit_price_a': price_a,
                            'bybit_price_b': price_b,
                            'bestchange_rate_original': bestchange_rate,
                            'bestchange_rate_inverted': actual_rate,
                            'exchanger': exch_list_ab[0]['exchanger'],
                            'reserve': exch_list_ab[0].get('reserve', 0),
                            # Проверка адекватности
                            'theoretical_ratio': price_a / price_b if price_b > 0 else 0,
                            'bestchange_ratio': actual_rate
                        }
                    })
                except (KeyError, ZeroDivisionError, TypeError) as e:
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

                # Показываем дополнительную информацию для первых 3 результатов
                if idx <= 3 and 'debug' in opp:
                    reserve = opp['debug'].get('reserve', 0)
                    if reserve > 0:
                        print(f"    💰 Резерв обменника: ${reserve:.2f}")

                    # Показываем проверку адекватности
                    theo_ratio = opp['debug'].get('theoretical_ratio', 0)
                    bc_ratio = opp['debug'].get('bestchange_ratio', 0)
                    if theo_ratio > 0 and bc_ratio > 0:
                        diff_percent = abs(theo_ratio - bc_ratio) / theo_ratio * 100
                        print(
                            f"    📊 Проверка: теор.курс={theo_ratio:.6f}, BC курс={bc_ratio:.6f} (расх. {diff_percent:.1f}%)")
                print()
        else:
            print(f"\n❌ Арбитражных возможностей со спредом >= {min_spread}% не найдено\n")

        return top_opportunities