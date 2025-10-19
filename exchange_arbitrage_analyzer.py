import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
from configs import ENABLE_CACHE, CACHE_HOT_PAIRS, MIN_PROFIT_USD


class ExchangeArbitrageAnalyzer:
    """
    Оптимизированный анализатор арбитража через обменники (BestChange)
    Схема: Bybit (купить A) → BestChange (обменять A→B) → Bybit (продать B)
    """

    def __init__(self, bybit_client, bestchange_client):
        self.bybit = bybit_client
        self.bestchange = bestchange_client
        self.found_count = 0
        self.checked_pairs = 0

        # Кэширование "горячих" пар
        self.hot_pairs_cache = {}
        self.pair_performance = defaultdict(lambda: {'checks': 0, 'finds': 0, 'avg_spread': 0})

    async def find_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.3,
            max_spread: float = 50.0,
            min_reserve: float = 0,
            parallel_requests: int = 500  # Увеличено для скорости
    ) -> List[Dict]:
        """
        Ищет арбитражные связки через обменники BestChange (ОПТИМИЗИРОВАНО)

        Args:
            start_amount: Начальная сумма в USDT
            min_spread: Минимальный спред для фильтрации
            max_spread: Максимальный спред (защита от аномалий)
            min_reserve: Минимальный резерв обменника
            parallel_requests: Количество параллельных проверок
        """
        print(f"\n[BestChange Arbitrage] 🚀 БЫСТРЫЙ ПОИСК связок...")
        print(f"[BestChange Arbitrage] Параметры: ${start_amount}, спред {min_spread}%-{max_spread}%")
        print(f"[BestChange Arbitrage] ⚡ Параллельных запросов: {parallel_requests}")
        print(f"[BestChange Arbitrage] 💰 Мин. резерв: ${min_reserve}, мин. прибыль: ${MIN_PROFIT_USD}")

        opportunities = []

        # Находим общие монеты
        bybit_coins = set(self.bybit.usdt_pairs.keys())
        bestchange_coins = set(self.bestchange.crypto_currencies.keys())
        common_coins = bybit_coins & bestchange_coins

        if not common_coins:
            print(f"[BestChange Arbitrage] ❌ Нет общих монет между Bybit и BestChange")
            return opportunities

        # Фильтруем только самые ликвидные монеты
        liquid_coins = []
        for coin in common_coins:
            liquidity = self.bybit.get_liquidity_score(coin, 'USDT')
            volume = self.bybit.get_volume_24h(coin, 'USDT')
            if liquidity >= 30:  # Только высоколиквидные
                liquid_coins.append((coin, liquidity, volume))

        # Сортируем по ликвидности
        liquid_coins.sort(key=lambda x: x[1], reverse=True)
        common_coins_list = [coin for coin, _, _ in liquid_coins]

        print(f"[BestChange Arbitrage] ✓ Общих монет: {len(common_coins)}")
        print(f"[BestChange Arbitrage] ✓ Высоколиквидных: {len(common_coins_list)}")

        # Создаём все возможные пары
        all_pairs = []

        # Сначала проверяем кэшированные "горячие" пары
        if ENABLE_CACHE and self.hot_pairs_cache:
            hot_pairs = list(self.hot_pairs_cache.keys())
            print(f"[BestChange Arbitrage] 🔥 Приоритет для {len(hot_pairs)} горячих пар")
            all_pairs.extend(hot_pairs)

        # Добавляем остальные пары
        for coin_a in common_coins_list:
            for coin_b in common_coins_list:
                if coin_a != coin_b:
                    pair = (coin_a, coin_b)
                    if pair not in all_pairs:
                        all_pairs.append(pair)

        total_pairs = len(all_pairs)
        print(f"[BestChange Arbitrage] 📦 Всего пар для проверки: {total_pairs}")
        print(f"[BestChange Arbitrage] 💡 Результаты выводятся в реальном времени...")
        print("=" * 100)

        self.checked_pairs = 0
        self.found_count = 0

        # Массово-параллельная обработка
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

        # Обновляем кэш горячих пар
        if ENABLE_CACHE and opportunities:
            self._update_hot_pairs_cache(opportunities)

        # Сортируем по прибыли
        opportunities.sort(key=lambda x: x['profit'], reverse=True)

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

            # Прогресс каждые 200 пар
            if self.checked_pairs % 200 == 0:
                print(f"[BestChange Arbitrage] 📊 Прогресс: {self.checked_pairs} | Найдено: {self.found_count}")

            result = await self._check_single_pair(coin_a, coin_b, start_amount, min_spread, max_spread, min_reserve)

            if result:
                self.found_count += 1
                self._print_opportunity(result, self.found_count)

                # Обновляем статистику пары
                pair_key = (coin_a, coin_b)
                self.pair_performance[pair_key]['finds'] += 1
                self.pair_performance[pair_key]['avg_spread'] = (
                    self.pair_performance[pair_key]['avg_spread'] + result['spread']
                ) / 2

            # Обновляем счётчик проверок
            pair_key = (coin_a, coin_b)
            self.pair_performance[pair_key]['checks'] += 1

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
        Проверяет одну пару монет (ОПТИМИЗИРОВАНО)
        Схема: USDT → CoinA (Bybit) → CoinB (BestChange) → USDT (Bybit)
        """
        try:
            # Быстрая проверка: есть ли цены?
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)

            if not price_a_usdt or price_a_usdt <= 0:
                return None
            if not price_b_usdt or price_b_usdt <= 0:
                return None

            # Быстрая проверка: есть ли курс на BestChange?
            best_rate = self.bestchange.get_best_rate(coin_a, coin_b, min_reserve)
            if not best_rate:
                return None

            exchange_rate = best_rate.rankrate
            if exchange_rate <= 0:
                return None

            # Расчёт арбитража
            amount_coin_a = start_amount / price_a_usdt
            amount_coin_b = amount_coin_a * exchange_rate
            final_usdt = amount_coin_b * price_b_usdt

            # Проверка лимитов обменника
            if best_rate.give_min > 0 and amount_coin_a < best_rate.give_min:
                return None
            if best_rate.give_max > 0 and amount_coin_a > best_rate.give_max:
                return None

            # Расчёт спреда и прибыли
            spread = ((final_usdt - start_amount) / start_amount) * 100
            profit = final_usdt - start_amount

            # Фильтрация
            if spread < min_spread or spread > max_spread:
                return None
            if abs(spread) > 100:  # Защита от аномалий
                return None
            if profit < MIN_PROFIT_USD:  # Минимальная прибыль в долларах
                return None

            return {
                'type': 'bestchange_arbitrage',
                'path': f"USDT → {coin_a} → {coin_b} → USDT",
                'scheme': f"Bybit → BestChange → Bybit",
                'coins': [coin_a, coin_b],
                'initial': start_amount,
                'final': final_usdt,
                'profit': profit,
                'spread': spread,
                'exchanger': best_rate.exchanger,
                'exchanger_id': best_rate.exchanger_id,
                'reserve': best_rate.reserve,
                'give_min': best_rate.give_min,
                'give_max': best_rate.give_max,
                'liquidity_a': self.bybit.get_liquidity_score(coin_a, 'USDT'),
                'liquidity_b': self.bybit.get_liquidity_score(coin_b, 'USDT'),
                'volume_a': self.bybit.get_volume_24h(coin_a, 'USDT'),
                'volume_b': self.bybit.get_volume_24h(coin_b, 'USDT'),
                'steps': [
                    f"1️⃣  Купить {amount_coin_a:.8f} {coin_a} за {start_amount:.2f} USDT на Bybit (${price_a_usdt:.8f})",
                    f"2️⃣  Перевести {amount_coin_a:.8f} {coin_a} с Bybit на {best_rate.exchanger}",
                    f"3️⃣  Обменять {amount_coin_a:.8f} {coin_a} → {amount_coin_b:.8f} {coin_b} (курс: {exchange_rate:.8f})",
                    f"4️⃣  Перевести {amount_coin_b:.8f} {coin_b} с обменника на Bybit",
                    f"5️⃣  Продать {amount_coin_b:.8f} {coin_b} за {final_usdt:.2f} USDT на Bybit (${price_b_usdt:.8f})",
                    f"✅ ИТОГ: {start_amount:.2f} USDT → {final_usdt:.2f} USDT (+{profit:.2f} USDT, {spread:.4f}%)"
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
        print(f"   💧 Ликвидность: {opp['coins'][0]} ({opp['liquidity_a']:.1f}) → {opp['coins'][1]} ({opp['liquidity_b']:.1f})")
        print("-" * 100)

    def _update_hot_pairs_cache(self, opportunities: List[Dict]):
        """Обновляет кэш горячих пар"""
        # Сортируем по прибыли
        sorted_opps = sorted(opportunities, key=lambda x: x['profit'], reverse=True)

        # Берём топ пар
        self.hot_pairs_cache.clear()
        for opp in sorted_opps[:CACHE_HOT_PAIRS]:
            pair = tuple(opp['coins'])
            self.hot_pairs_cache[pair] = {
                'last_spread': opp['spread'],
                'last_profit': opp['profit'],
                'last_check': datetime.now()
            }

        print(f"\n[Cache] 🔥 Обновлён кэш: {len(self.hot_pairs_cache)} горячих пар")

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

    def get_hot_pairs(self) -> List[tuple]:
        """Возвращает список горячих пар из кэша"""
        return list(self.hot_pairs_cache.keys())

    def get_pair_statistics(self) -> Dict:
        """Возвращает статистику по парам"""
        stats = {
            'total_pairs_checked': len(self.pair_performance),
            'hot_pairs_cached': len(self.hot_pairs_cache),
            'top_performers': []
        }

        # Топ-10 самых успешных пар
        sorted_pairs = sorted(
            self.pair_performance.items(),
            key=lambda x: x[1]['finds'] / max(x[1]['checks'], 1),
            reverse=True
        )[:10]

        for pair, perf in sorted_pairs:
            stats['top_performers'].append({
                'pair': f"{pair[0]} → {pair[1]}",
                'finds': perf['finds'],
                'checks': perf['checks'],
                'success_rate': perf['finds'] / max(perf['checks'], 1) * 100,
                'avg_spread': perf['avg_spread']
            })

        return stats