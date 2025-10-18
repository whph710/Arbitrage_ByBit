import asyncio
from typing import List, Dict, Set, Optional
from datetime import datetime
from configs import EXCHANGE_REQUEST_DELAY


class MultiExchangeArbitrageAnalyzer:
    """
    МУЛЬТИ-ОБМЕННИК анализатор арбитражных возможностей
    Поддерживает: Swapzone, ChangeNOW и другие
    """

    def __init__(self, bybit_client, exchange_clients: List):
        """
        Args:
            bybit_client: Клиент Bybit
            exchange_clients: Список клиентов обменников [swapzone, changenow, ...]
        """
        self.bybit = bybit_client
        self.exchange_clients = exchange_clients
        self.found_count = 0
        self.checked_pairs = 0

    async def find_arbitrage_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.3,
            top_count: int = 20,
            max_pairs_to_check: int = 100,
            parallel_requests: int = 10
    ) -> List[Dict]:
        """
        Ищет арбитражные связки через ВСЕ подключенные обменники
        Приоритет: первый обменник в списке имеет приоритет
        """

        print(f"\n[Analyzer] 🔍 Начало поиска через {len(self.exchange_clients)} обменников")
        print(f"[Analyzer] Параметры: начальная сумма = ${start_amount}, мин. спред = {min_spread}%")
        print(f"[Analyzer] ⚡ Параллельных запросов: {parallel_requests}")

        opportunities = []

        # Находим общие монеты для ВСЕХ обменников
        common_coins_all = set(self.bybit.coins)

        print(f"\n[Analyzer] 🔄 Проверка доступных монет на обменниках...")
        for exchange in self.exchange_clients:
            exchange_name = exchange.__class__.__name__.replace('ClientAsync', '')
            exchange_coins = exchange.get_common_currencies(self.bybit.coins)
            common_coins_all &= exchange_coins

        if not common_coins_all:
            print("[Analyzer] ❌ Нет общих монет между Bybit и всеми обменниками")
            return opportunities

        common_coins_list = sorted(list(common_coins_all))[:max_pairs_to_check]

        print(f"\n[Analyzer] 📊 Общих монет на ВСЕХ обменниках: {len(common_coins_list)}")
        print(f"[Analyzer] 💡 Результаты будут выводиться по мере обнаружения...\n")
        print("=" * 100)

        self.checked_pairs = 0
        self.found_count = 0

        # Создаём все возможные пары
        all_pairs = []
        for coin_a in common_coins_list:
            for coin_b in common_coins_list:
                if coin_a != coin_b:
                    all_pairs.append((coin_a, coin_b))

        print(f"[Analyzer] 📦 Всего пар для проверки: {len(all_pairs)}")
        print(f"[Analyzer] 🎯 Порядок проверки обменников:")
        for i, exchange in enumerate(self.exchange_clients, 1):
            exchange_name = exchange.__class__.__name__.replace('ClientAsync', '')
            print(f"   {i}. {exchange_name} (приоритет)")

        # Обрабатываем пары пакетами (параллельно)
        semaphore = asyncio.Semaphore(parallel_requests)
        tasks = []

        for coin_a, coin_b in all_pairs:
            task = self._check_pair_with_semaphore(
                semaphore, coin_a, coin_b, start_amount, min_spread
            )
            tasks.append(task)

        # Запускаем все задачи параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Собираем результаты
        for result in results:
            if isinstance(result, dict) and 'spread' in result:
                opportunities.append(result)
                self.found_count += 1
                self._print_opportunity(result, self.found_count)

        print("=" * 100)
        print(f"\n[Analyzer] ✅ Проверка завершена!")
        print(f"[Analyzer] 📊 Проверено пар: {self.checked_pairs}")
        print(f"[Analyzer] 🎯 Найдено связок: {self.found_count}")

        # Статистика по обменникам
        print(f"\n[Analyzer] 📈 Статистика по обменникам:")
        for exchange in self.exchange_clients:
            exchange_name = exchange.__class__.__name__.replace('ClientAsync', '')
            failed = exchange.get_failed_pairs_count()
            print(f"   • {exchange_name}: {failed} недоступных пар")

        # Сортируем по спреду
        opportunities.sort(key=lambda x: x['spread'], reverse=True)

        # Ограничиваем топ
        if top_count:
            top_opportunities = opportunities[:top_count]
        else:
            top_opportunities = opportunities

        if top_opportunities and len(opportunities) > top_count:
            print(f"\n[Analyzer] 📋 Показаны топ-{top_count} лучших из {len(opportunities)} найденных связок")

        return top_opportunities

    async def _check_pair_with_semaphore(
            self,
            semaphore: asyncio.Semaphore,
            coin_a: str,
            coin_b: str,
            start_amount: float,
            min_spread: float
    ):
        """Проверяет одну пару с ограничением параллелизма"""
        async with semaphore:
            self.checked_pairs += 1

            # Показываем прогресс каждые 100 пар
            if self.checked_pairs % 100 == 0:
                print(f"[Analyzer] 🔄 Проверено пар: {self.checked_pairs}, найдено связок: {self.found_count}")

            return await self._check_single_pair(coin_a, coin_b, start_amount, min_spread)

    async def _check_single_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float,
            min_spread: float
    ) -> Optional[Dict]:
        """Проверяет одну пару монет через ВСЕ обменники (по приоритету)"""
        try:
            # Шаг 1: USDT → CoinA на Bybit
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            if not price_a_usdt or price_a_usdt <= 0:
                return None

            amount_coin_a = start_amount / price_a_usdt

            # Шаг 2: Пробуем обменники по порядку (первый = приоритет)
            best_result = None
            best_exchange_name = None

            for exchange in self.exchange_clients:
                # Быстрая проверка в кэше неудачных пар
                pair_key = f"{coin_a}_{coin_b}"
                if pair_key in exchange.failed_pairs:
                    continue

                # Пробуем получить курс
                exchange_result = await exchange.get_estimated_amount(
                    from_currency=coin_a,
                    to_currency=coin_b,
                    from_amount=amount_coin_a
                )

                if exchange_result and exchange_result['to_amount'] > 0:
                    # Нашли рабочий обменник!
                    best_result = exchange_result
                    best_exchange_name = exchange.__class__.__name__.replace('ClientAsync', '')
                    break  # Используем первый рабочий (по приоритету)

            if not best_result:
                return None

            amount_coin_b = best_result['to_amount']
            exchange_rate = amount_coin_b / amount_coin_a if amount_coin_a > 0 else 0

            if exchange_rate <= 0:
                return None

            # Шаг 3: CoinB → USDT на Bybit
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
            if not price_b_usdt or price_b_usdt <= 0:
                return None

            final_usdt = amount_coin_b * price_b_usdt

            # Рассчитываем спред
            spread = ((final_usdt - start_amount) / start_amount) * 100

            # Фильтруем нереалистичные спреды
            if spread > 50.0 or spread < -50.0:
                return None

            # Дополнительная валидация
            expected_price_b = price_a_usdt / exchange_rate
            price_deviation = abs(expected_price_b - price_b_usdt) / price_b_usdt * 100

            if price_deviation > 100:
                return None

            if spread >= min_spread:
                return {
                    'type': 'exchange_arbitrage',
                    'path': f"USDT → {coin_a} → {coin_b} → USDT",
                    'scheme': f"Bybit → {best_exchange_name} → Bybit",
                    'coins': [coin_a, coin_b],
                    'exchange_used': best_exchange_name,
                    'initial': start_amount,
                    'final': final_usdt,
                    'profit': final_usdt - start_amount,
                    'spread': spread,
                    'steps': [
                        f"1. Купить {amount_coin_a:.8f} {coin_a} за {start_amount:.2f} USDT на Bybit (курс: {price_a_usdt:.8f})",
                        f"2. Обменять {amount_coin_a:.8f} {coin_a} → {amount_coin_b:.8f} {coin_b} через {best_exchange_name} (курс: {exchange_rate:.8f})",
                        f"3. Продать {amount_coin_b:.8f} {coin_b} за {final_usdt:.2f} USDT на Bybit (курс: {price_b_usdt:.8f})",
                        f"✅ Итог: {start_amount:.2f} USDT → {final_usdt:.2f} USDT (+{final_usdt - start_amount:.2f} USDT, {spread:.4f}%)"
                    ],
                    'exchange_rate': exchange_rate,
                    'bybit_rate_a': price_a_usdt,
                    'bybit_rate_b': price_b_usdt,
                    'timestamp': datetime.now().isoformat()
                }

            return None

        except Exception as e:
            return None

    def _print_opportunity(self, opp: Dict, rank: int):
        """Выводит найденную возможность сразу в консоль"""
        print(f"\n🎯 НАЙДЕНА СВЯЗКА #{rank} через {opp['exchange_used']}")
        print(f"   Путь: {opp['path']}")
        print(f"   💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
        print(f"   🔄 Обменник: {opp['exchange_used']}")
        print(f"   📊 Детальный расчёт:")
        print(f"      1️⃣  {opp['initial']:.2f} USDT → {opp['initial'] / opp['bybit_rate_a']:.8f} {opp['coins'][0]}")
        print(f"         (Bybit: 1 {opp['coins'][0]} = ${opp['bybit_rate_a']:.8f})")
        print(
            f"      2️⃣  {opp['initial'] / opp['bybit_rate_a']:.8f} {opp['coins'][0]} → {(opp['initial'] / opp['bybit_rate_a']) * opp['exchange_rate']:.8f} {opp['coins'][1]}")
        print(f"         ({opp['exchange_used']}: 1 {opp['coins'][0]} = {opp['exchange_rate']:.8f} {opp['coins'][1]})")
        print(
            f"      3️⃣  {(opp['initial'] / opp['bybit_rate_a']) * opp['exchange_rate']:.8f} {opp['coins'][1]} → {opp['final']:.2f} USDT")
        print(f"         (Bybit: 1 {opp['coins'][1]} = ${opp['bybit_rate_b']:.8f})")
        print(f"   ✅ Итог: ${opp['initial']:.2f} → ${opp['final']:.2f} (+ ${opp['profit']:.4f})")
        print("-" * 100)

    async def analyze_specific_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float = 100.0
    ) -> Dict:
        """Анализирует конкретную пару монет через все обменники"""
        print(f"\n[Analyzer] 🔬 Детальный анализ пары {coin_a} → {coin_b}")

        try:
            # Шаг 1: USDT → CoinA на Bybit
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            if not price_a_usdt:
                return {'error': f'Цена {coin_a} не найдена на Bybit'}

            amount_coin_a = start_amount / price_a_usdt
            print(f"   1. {start_amount} USDT → {amount_coin_a:.8f} {coin_a} (Bybit: {price_a_usdt:.8f})")

            # Шаг 2: Проверяем все обменники
            print(f"\n   🔄 Проверка обменников:")
            best_result = None
            best_exchange = None

            for exchange in self.exchange_clients:
                exchange_name = exchange.__class__.__name__.replace('ClientAsync', '')
                print(f"      • {exchange_name}...", end=" ")

                exchange_result = await exchange.get_estimated_amount(
                    from_currency=coin_a,
                    to_currency=coin_b,
                    from_amount=amount_coin_a
                )

                if exchange_result and exchange_result['to_amount'] > 0:
                    amount_coin_b = exchange_result['to_amount']
                    exchange_rate = amount_coin_b / amount_coin_a
                    print(f"✓ {amount_coin_b:.8f} {coin_b} (курс: {exchange_rate:.8f})")

                    if best_result is None or amount_coin_b > best_result['to_amount']:
                        best_result = exchange_result
                        best_exchange = exchange_name
                else:
                    print("✗ недоступно")

            if not best_result:
                return {'error': f'Ни один обменник не поддерживает {coin_a} → {coin_b}'}

            amount_coin_b = best_result['to_amount']
            exchange_rate = amount_coin_b / amount_coin_a
            print(f"\n   ⭐ Лучший: {best_exchange} → {amount_coin_b:.8f} {coin_b}")

            # Шаг 3: CoinB → USDT на Bybit
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
            if not price_b_usdt:
                return {'error': f'Цена {coin_b} не найдена на Bybit'}

            final_usdt = amount_coin_b * price_b_usdt
            print(f"   3. {amount_coin_b:.8f} {coin_b} → {final_usdt:.2f} USDT (Bybit: {price_b_usdt:.8f})")

            spread = ((final_usdt - start_amount) / start_amount) * 100
            profit = final_usdt - start_amount

            print(f"\n   ✅ Итог: {spread:.4f}% ({'+' if profit >= 0 else ''}{profit:.2f} USDT)")
            print(f"   🏆 Лучший обменник: {best_exchange}")

            return {
                'success': True,
                'spread': spread,
                'profit': profit,
                'final_usdt': final_usdt,
                'best_exchange': best_exchange
            }

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return {'error': str(e)}