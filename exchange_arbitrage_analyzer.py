import asyncio
from typing import List, Dict, Set
from datetime import datetime
from configs import EXCHANGE_REQUEST_DELAY


class ExchangeArbitrageAnalyzer:
    """
    Анализатор арбитражных возможностей через обменники
    Схема: Bybit → Обменник → Bybit
    """

    def __init__(self, bybit_client, exchange_client):
        self.bybit = bybit_client
        self.exchange = exchange_client

    async def find_arbitrage_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.3,
            top_count: int = 20,
            max_pairs_to_check: int = 100
    ) -> List[Dict]:
        """
        Ищет арбитражные связки:
        USDT (Bybit) → CoinA (Bybit) → Обменник → CoinB (Bybit) → USDT (Bybit)
        """

        print(f"\n[Analyzer] 🔍 Начало поиска арбитражных связок через обменники")
        print(f"[Analyzer] Параметры: начальная сумма = ${start_amount}, мин. спред = {min_spread}%")

        opportunities = []

        # Находим общие монеты между Bybit и обменником
        common_coins = self.exchange.get_common_currencies(self.bybit.coins)

        if not common_coins:
            print("[Analyzer] ❌ Нет общих монет между Bybit и обменником")
            return opportunities

        # Ограничиваем количество проверяемых пар для оптимизации
        common_coins_list = sorted(list(common_coins))[:max_pairs_to_check]

        print(f"\n[Analyzer] 📊 Проверка {len(common_coins_list)} монет для арбитража...")

        checked_pairs = 0
        found_pairs = 0

        # Проходим по всем возможным парам монет
        for i, coin_a in enumerate(common_coins_list):
            for coin_b in common_coins_list:
                if coin_a == coin_b:
                    continue

                checked_pairs += 1

                # Показываем прогресс каждые 50 пар
                if checked_pairs % 50 == 0:
                    print(f"[Analyzer] 🔄 Проверено пар: {checked_pairs}, найдено связок: {found_pairs}")

                try:
                    # Шаг 1: USDT → CoinA на Bybit
                    price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
                    if not price_a_usdt or price_a_usdt <= 0:
                        continue

                    amount_coin_a = start_amount / price_a_usdt

                    # Шаг 2: CoinA → CoinB через обменник
                    exchange_result = await self.exchange.get_estimated_amount(
                        from_currency=coin_a,
                        to_currency=coin_b,
                        from_amount=amount_coin_a
                    )

                    if not exchange_result or exchange_result['to_amount'] <= 0:
                        continue

                    amount_coin_b = exchange_result['to_amount']
                    exchange_rate = exchange_result['rate']

                    # Шаг 3: CoinB → USDT на Bybit
                    price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
                    if not price_b_usdt or price_b_usdt <= 0:
                        continue

                    final_usdt = amount_coin_b * price_b_usdt

                    # Рассчитываем спред
                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    if spread >= min_spread:
                        found_pairs += 1

                        opportunities.append({
                            'type': 'exchange_arbitrage',
                            'path': f"USDT → {coin_a} → {coin_b} → USDT",
                            'scheme': "Bybit → Обменник → Bybit",
                            'coins': [coin_a, coin_b],
                            'initial': start_amount,
                            'final': final_usdt,
                            'profit': final_usdt - start_amount,
                            'spread': spread,
                            'steps': [
                                f"1. Купить {amount_coin_a:.8f} {coin_a} за {start_amount:.2f} USDT на Bybit (курс: {price_a_usdt:.8f})",
                                f"2. Обменять {amount_coin_a:.8f} {coin_a} → {amount_coin_b:.8f} {coin_b} через обменник (курс: {exchange_rate:.8f})",
                                f"3. Продать {amount_coin_b:.8f} {coin_b} за {final_usdt:.2f} USDT на Bybit (курс: {price_b_usdt:.8f})",
                                f"✅ Итог: {start_amount:.2f} USDT → {final_usdt:.2f} USDT (+{final_usdt - start_amount:.2f} USDT, {spread:.4f}%)"
                            ],
                            'exchange_rate': exchange_rate,
                            'bybit_rate_a': price_a_usdt,
                            'bybit_rate_b': price_b_usdt
                        })

                except Exception as e:
                    # Игнорируем ошибки для отдельных пар
                    continue

            # Небольшая задержка после каждой монеты
            await asyncio.sleep(0.1)

        print(f"\n[Analyzer] ✓ Проверено пар: {checked_pairs}")
        print(f"[Analyzer] ✓ Найдено связок: {found_pairs}")

        # Сортируем по спреду
        opportunities.sort(key=lambda x: x['spread'], reverse=True)

        # Ограничиваем топ
        if top_count:
            top_opportunities = opportunities[:top_count]
        else:
            top_opportunities = opportunities

        self._print_results(top_opportunities, min_spread, start_amount)

        return top_opportunities

    def _print_results(self, opportunities: List[Dict], min_spread: float, start_amount: float):
        """Выводит результаты анализа"""

        if opportunities:
            print("\n" + "=" * 100)
            print(f"🎯 ТОП-{len(opportunities)} АРБИТРАЖНЫХ СВЯЗОК ЧЕРЕЗ ОБМЕННИКИ")
            print("=" * 100 + "\n")

            for idx, opp in enumerate(opportunities, 1):
                print(f"#{idx} | {opp['path']}")
                print(f"   ➜ Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                print(f"   ➜ Монеты: {' → '.join(opp['coins'])}")
                print()
        else:
            print(f"\n❌ Арбитражных связок со спредом >= {min_spread}% не найдено.")

    async def analyze_specific_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float = 100.0
    ) -> Dict:
        """
        Анализирует конкретную пару монет
        Полезно для детальной проверки
        """
        print(f"\n[Analyzer] 🔬 Детальный анализ пары {coin_a} → {coin_b}")

        try:
            # Шаг 1: USDT → CoinA на Bybit
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            if not price_a_usdt:
                return {'error': f'Цена {coin_a} не найдена на Bybit'}

            amount_coin_a = start_amount / price_a_usdt
            print(f"   1. {start_amount} USDT → {amount_coin_a:.8f} {coin_a} (Bybit: {price_a_usdt:.8f})")

            # Шаг 2: CoinA → CoinB через обменник
            exchange_result = await self.exchange.get_estimated_amount(
                from_currency=coin_a,
                to_currency=coin_b,
                from_amount=amount_coin_a
            )

            if not exchange_result:
                return {'error': f'Не удалось получить курс обмена {coin_a} → {coin_b}'}

            amount_coin_b = exchange_result['to_amount']
            exchange_rate = exchange_result['rate']
            print(f"   2. {amount_coin_a:.8f} {coin_a} → {amount_coin_b:.8f} {coin_b} (Обменник: {exchange_rate:.8f})")

            # Шаг 3: CoinB → USDT на Bybit
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
            if not price_b_usdt:
                return {'error': f'Цена {coin_b} не найдена на Bybit'}

            final_usdt = amount_coin_b * price_b_usdt
            print(f"   3. {amount_coin_b:.8f} {coin_b} → {final_usdt:.2f} USDT (Bybit: {price_b_usdt:.8f})")

            spread = ((final_usdt - start_amount) / start_amount) * 100
            profit = final_usdt - start_amount

            print(f"\n   ✅ Итог: {spread:.4f}% ({'+' if profit >= 0 else ''}{profit:.2f} USDT)")

            return {
                'success': True,
                'spread': spread,
                'profit': profit,
                'final_usdt': final_usdt
            }

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return {'error': str(e)}