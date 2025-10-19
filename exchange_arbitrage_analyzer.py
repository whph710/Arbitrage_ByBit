import asyncio
from typing import List, Dict, Optional
from datetime import datetime


class ExchangeArbitrageAnalyzer:
    """
    Анализатор арбитража через обменники (BestChange)
    Схема: Bybit (купить A) → BestChange (обменять A→B) → Bybit (продать B)
    """

    def __init__(self, bybit_client, bestchange_client):
        self.bybit = bybit_client
        self.bestchange = bestchange_client
        self.found_count = 0
        self.checked_pairs = 0

    async def find_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.3,
            max_spread: float = 50.0,
            min_reserve: float = 0,
            parallel_requests: int = 50
    ) -> List[Dict]:
        """
        Ищет арбитражные связки через обменники BestChange

        Args:
            start_amount: Начальная сумма в USDT
            min_spread: Минимальный спред для фильтрации
            max_spread: Максимальный спред (защита от аномалий)
            min_reserve: Минимальный резерв обменника
            parallel_requests: Количество параллельных проверок
        """
        print(f"\n[BestChange Arbitrage] 🔍 Начало поиска связок...")
        print(f"[BestChange Arbitrage] Параметры: ${start_amount}, спред {min_spread}%-{max_spread}%")
        print(f"[BestChange Arbitrage] ⚡ Параллельных запросов: {parallel_requests}")
        print(f"[BestChange Arbitrage] 💰 Мин. резерв обменника: ${min_reserve}")

        opportunities = []

        # Находим общие монеты между Bybit и BestChange
        bybit_coins = set(self.bybit.usdt_pairs.keys())
        bestchange_coins = set(self.bestchange.crypto_currencies.keys())
        common_coins = bybit_coins & bestchange_coins

        if not common_coins:
            print(f"[BestChange Arbitrage] ❌ Нет общих монет между Bybit и BestChange")
            return opportunities

        common_coins_list = sorted(list(common_coins))
        print(f"[BestChange Arbitrage] ✓ Общих монет: {len(common_coins_list)}")

        # Создаём все возможные пары для проверки
        all_pairs = []
        for coin_a in common_coins_list:
            for coin_b in common_coins_list:
                if coin_a != coin_b:
                    all_pairs.append((coin_a, coin_b))

        total_pairs = len(all_pairs)
        print(f"[BestChange Arbitrage] 📦 Всего пар для проверки: {total_pairs}")
        print(f"[BestChange Arbitrage] 💡 Результаты выводятся по мере обнаружения...")
        print("=" * 100)

        self.checked_pairs = 0
        self.found_count = 0

        # Обрабатываем пары пакетами (параллельно)
        semaphore = asyncio.Semaphore(parallel_requests)
        tasks = []

        for coin_a, coin_b in all_pairs:
            task = self._check_pair_with_semaphore(
                semaphore, coin_a, coin_b, start_amount, min_spread, max_spread, min_reserve
            )
            tasks.append(task)

        # Запускаем все задачи параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Собираем результаты
        for result in results:
            if isinstance(result, dict) and 'spread' in result:
                opportunities.append(result)

        print("=" * 100)
        print(f"\n[BestChange Arbitrage] ✅ Проверка завершена!")
        print(f"[BestChange Arbitrage] 📊 Проверено пар: {self.checked_pairs}")
        print(f"[BestChange Arbitrage] 🎯 Найдено связок: {len(opportunities)}")

        # Сортируем по спреду
        opportunities.sort(key=lambda x: x['spread'], reverse=True)

        return opportunities

    async def _check_pair_with_semaphore(
            self,
            semaphore: asyncio.Semaphore,
            coin_a: str,
            coin_b: str,
            start_amount: float,
            min_spread: float,
            max_spread: float,
            min_reserve: float
    ):
        """Проверяет одну пару с ограничением параллелизма"""
        async with semaphore:
            self.checked_pairs += 1

            # Показываем прогресс каждые 100 пар
            if self.checked_pairs % 100 == 0:
                print(f"[BestChange Arbitrage] 📊 Прогресс: {self.checked_pairs} | Найдено: {self.found_count}")

            result = await self._check_single_pair(coin_a, coin_b, start_amount, min_spread, max_spread, min_reserve)

            if result:
                self.found_count += 1
                self._print_opportunity(result, self.found_count)

            return result

    async def _check_single_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float,
            min_spread: float,
            max_spread: float,
            min_reserve: float
    ) -> Optional[Dict]:
        """
        Проверяет одну пару монет
        Схема: USDT → CoinA (Bybit) → CoinB (BestChange) → USDT (Bybit)
        """
        try:
            # Шаг 1: USDT → CoinA на Bybit
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            if not price_a_usdt or price_a_usdt <= 0:
                return None

            amount_coin_a = start_amount / price_a_usdt

            # Шаг 2: CoinA → CoinB на BestChange (получаем лучший курс)
            best_rate = self.bestchange.get_best_rate(coin_a, coin_b, min_reserve)

            if not best_rate:
                return None

            # Используем rankrate (учитывает комиссии)
            exchange_rate = best_rate.rankrate
            if exchange_rate <= 0:
                return None

            amount_coin_b = amount_coin_a * exchange_rate

            # Проверяем лимиты обменника
            if best_rate.give_min > 0 and amount_coin_a < best_rate.give_min:
                return None
            if best_rate.give_max > 0 and amount_coin_a > best_rate.give_max:
                return None

            # Шаг 3: CoinB → USDT на Bybit
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
            if not price_b_usdt or price_b_usdt <= 0:
                return None

            final_usdt = amount_coin_b * price_b_usdt

            # Рассчитываем спред
            spread = ((final_usdt - start_amount) / start_amount) * 100

            # Фильтруем по спреду
            if spread < min_spread or spread > max_spread:
                return None

            # Дополнительная валидация (защита от аномалий)
            if abs(spread) > 100:
                return None

            return {
                'type': 'bestchange_arbitrage',
                'path': f"USDT → {coin_a} → {coin_b} → USDT",
                'scheme': f"Bybit → BestChange → Bybit",
                'coins': [coin_a, coin_b],
                'initial': start_amount,
                'final': final_usdt,
                'profit': final_usdt - start_amount,
                'spread': spread,
                'exchanger': best_rate.exchanger,
                'exchanger_id': best_rate.exchanger_id,
                'reserve': best_rate.reserve,
                'give_min': best_rate.give_min,
                'give_max': best_rate.give_max,
                'steps': [
                    f"1️⃣  Купить {amount_coin_a:.8f} {coin_a} за {start_amount:.2f} USDT на Bybit (курс: ${price_a_usdt:.8f})",
                    f"2️⃣  Перевести {amount_coin_a:.8f} {coin_a} с Bybit на обменник {best_rate.exchanger}",
                    f"3️⃣  Обменять {amount_coin_a:.8f} {coin_a} → {amount_coin_b:.8f} {coin_b} на {best_rate.exchanger} (курс: {exchange_rate:.8f})",
                    f"4️⃣  Перевести {amount_coin_b:.8f} {coin_b} с обменника на Bybit",
                    f"5️⃣  Продать {amount_coin_b:.8f} {coin_b} за {final_usdt:.2f} USDT на Bybit (курс: ${price_b_usdt:.8f})",
                    f"✅ ИТОГ: {start_amount:.2f} USDT → {final_usdt:.2f} USDT (+{final_usdt - start_amount:.2f} USDT, {spread:.4f}%)"
                ],
                'exchange_rate': exchange_rate,
                'bybit_rate_a': price_a_usdt,
                'bybit_rate_b': price_b_usdt,
                'timestamp': datetime.now().isoformat()
            }

        except Exception:
            return None

    def _print_opportunity(self, opp: Dict, rank: int):
        """Выводит найденную возможность сразу в консоль"""
        print(f"\n🎯 НАЙДЕНА СВЯЗКА #{rank} через BestChange")
        print(f"   📍 Путь: {opp['path']}")
        print(f"   💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
        print(f"   🏦 Обменник: {opp['exchanger']} (резерв: ${opp['reserve']:,.0f})")
        print(f"   📊 Детальный расчёт:")
        print(f"      1️⃣  {opp['initial']:.2f} USDT → {opp['initial'] / opp['bybit_rate_a']:.8f} {opp['coins'][0]}")
        print(f"         (Bybit: 1 {opp['coins'][0]} = ${opp['bybit_rate_a']:.8f})")
        print(
            f"      2️⃣  {opp['initial'] / opp['bybit_rate_a']:.8f} {opp['coins'][0]} → {(opp['initial'] / opp['bybit_rate_a']) * opp['exchange_rate']:.8f} {opp['coins'][1]}")
        print(f"         ({opp['exchanger']}: 1 {opp['coins'][0]} = {opp['exchange_rate']:.8f} {opp['coins'][1]})")
        print(
            f"      3️⃣  {(opp['initial'] / opp['bybit_rate_a']) * opp['exchange_rate']:.8f} {opp['coins'][1]} → {opp['final']:.2f} USDT")
        print(f"         (Bybit: 1 {opp['coins'][1]} = ${opp['bybit_rate_b']:.8f})")
        print(f"   ✅ Итог: ${opp['initial']:.2f} → ${opp['final']:.2f} (+${opp['profit']:.4f})")
        print("-" * 100)

    async def analyze_specific_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float = 100.0,
            min_reserve: float = 0
    ) -> Dict:
        """Анализирует конкретную пару монет"""
        print(f"\n[BestChange Arbitrage] 🔬 Детальный анализ пары {coin_a} → {coin_b}")

        try:
            # Шаг 1: USDT → CoinA на Bybit
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            if not price_a_usdt:
                return {'error': f'Цена {coin_a} не найдена на Bybit'}

            amount_coin_a = start_amount / price_a_usdt
            print(f"   1. {start_amount} USDT → {amount_coin_a:.8f} {coin_a} (Bybit: ${price_a_usdt:.8f})")

            # Шаг 2: CoinA → CoinB на BestChange
            print(f"   2. Запрос курса {coin_a} → {coin_b} на BestChange...")

            # Получаем топ-5 обменников
            top_rates = self.bestchange.get_top_rates(coin_a, coin_b, top_n=5, min_reserve=min_reserve)

            if not top_rates:
                return {'error': f'BestChange не поддерживает {coin_a} → {coin_b}'}

            print(f"   ✓ Найдено {len(top_rates)} обменников:")
            for idx, rate in enumerate(top_rates, 1):
                amount_b = amount_coin_a * rate.rankrate
                print(
                    f"      {idx}. {rate.exchanger}: курс {rate.rankrate:.8f} → {amount_b:.8f} {coin_b} (резерв: ${rate.reserve:,.0f})")

            # Используем лучший курс
            best_rate = top_rates[0]
            amount_coin_b = amount_coin_a * best_rate.rankrate

            # Шаг 3: CoinB → USDT на Bybit
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
            if not price_b_usdt:
                return {'error': f'Цена {coin_b} не найдена на Bybit'}

            final_usdt = amount_coin_b * price_b_usdt
            print(f"   3. {amount_coin_b:.8f} {coin_b} → {final_usdt:.2f} USDT (Bybit: ${price_b_usdt:.8f})")

            spread = ((final_usdt - start_amount) / start_amount) * 100
            profit = final_usdt - start_amount

            print(f"\n   ✅ Итог: {spread:.4f}% ({'+' if profit >= 0 else ''}{profit:.2f} USDT)")
            print(f"   🏦 Лучший обменник: {best_rate.exchanger}")

            return {
                'success': True,
                'spread': spread,
                'profit': profit,
                'final_usdt': final_usdt,
                'exchanger': best_rate.exchanger,
                'top_exchangers': [
                    {
                        'name': r.exchanger,
                        'rate': r.rankrate,
                        'reserve': r.reserve
                    } for r in top_rates
                ]
            }

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return {'error': str(e)}