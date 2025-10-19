import asyncio
from datetime import datetime
from configs import START_AMOUNT, MIN_SPREAD, SHOW_TOP, MAX_REASONABLE_SPREAD
from logs.bybit_handler import BybitClientAsync
from results_saver import ResultsSaver


class InternalArbitrageAnalyzer:
    """Анализатор внутрибиржевого арбитража на Bybit"""

    def __init__(self, bybit_client):
        self.bybit = bybit_client
        self.found_count = 0
        self.checked_count = 0

    async def find_arbitrage_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.3,
            max_spread: float = 50.0,
            check_triangular: bool = True,
            check_quadrilateral: bool = True
    ):
        """Ищет внутрибиржевые арбитражные возможности"""
        print(f"\n[Analyzer] 🔍 Начало поиска внутрибиржевого арбитража на Bybit")
        print(f"[Analyzer] Параметры: начальная сумма = ${start_amount}, спред = {min_spread}%-{max_spread}%")

        opportunities = []
        self.found_count = 0
        self.checked_count = 0

        # Треугольный арбитраж
        if check_triangular:
            print("\n" + "=" * 100)
            print("[Analyzer] 🔺 Поиск треугольного арбитража: USDT -> A -> B -> USDT")
            print("=" * 100)

            tri_opps = await self._find_triangular_arbitrage(start_amount, min_spread, max_spread)
            opportunities.extend(tri_opps)

            print("=" * 100)
            print(f"[Analyzer] ✓ Треугольный: найдено {len(tri_opps)} возможностей\n")

        # Четырехугольный арбитраж
        if check_quadrilateral:
            print("=" * 100)
            print("[Analyzer] 🔶 Поиск четырехугольного арбитража: USDT -> A -> B -> C -> USDT")
            print("=" * 100)

            quad_opps = await self._find_quadrilateral_arbitrage(start_amount, min_spread, max_spread)
            opportunities.extend(quad_opps)

            print("=" * 100)
            print(f"[Analyzer] ✓ Четырехугольный: найдено {len(quad_opps)} возможностей\n")

        return opportunities

    def _get_exchange_rate(self, from_coin: str, to_coin: str) -> float:
        """
        КРИТИЧНО: Правильно рассчитывает курс обмена from_coin -> to_coin

        Пытается найти:
        1. Прямую пару from_coin/to_coin
        2. Обратную пару to_coin/from_coin (и берёт 1/price)
        3. Через USDT: from_coin/USDT и to_coin/USDT
        """
        # Вариант 1: Прямая пара
        direct_price = self.bybit.get_price(from_coin, to_coin)
        if direct_price is not None and direct_price > 0:
            return direct_price

        # Вариант 2: Через USDT (если обе монеты имеют USDT пары)
        if from_coin != 'USDT' and to_coin != 'USDT':
            from_usdt_price = self.bybit.usdt_pairs.get(from_coin)
            to_usdt_price = self.bybit.usdt_pairs.get(to_coin)

            if from_usdt_price and to_usdt_price and from_usdt_price > 0 and to_usdt_price > 0:
                # Курс: from_coin -> USDT -> to_coin
                return from_usdt_price / to_usdt_price

        return None

    async def _find_triangular_arbitrage(self, start_amount, min_spread, max_spread):
        """
        Треугольный арбитраж: USDT -> CoinA -> CoinB -> USDT

        ИСПРАВЛЕНО:
        - Правильный расчёт кросс-курсов
        - Проверка существования пар
        - Валидация промежуточных значений
        """
        opportunities = []
        usdt_coins = list(self.bybit.usdt_pairs.keys())

        print(f"[Triangular] Монет с USDT-парами: {len(usdt_coins)}")

        for i, coin_a in enumerate(usdt_coins):
            # Шаг 1: USDT -> CoinA
            price_usdt_to_a = self.bybit.usdt_pairs.get(coin_a)
            if not price_usdt_to_a or price_usdt_to_a <= 0:
                continue

            amount_a = start_amount / price_usdt_to_a

            for coin_b in usdt_coins[i + 1:]:
                if coin_a == coin_b:
                    continue

                self.checked_count += 1

                if self.checked_count % 500 == 0:
                    print(f"[Triangular] 📊 Проверено: {self.checked_count} | Найдено: {self.found_count}")

                # Шаг 2: CoinA -> CoinB (ИСПРАВЛЕНО)
                price_a_to_b = self._get_exchange_rate(coin_a, coin_b)
                if price_a_to_b is None or price_a_to_b <= 0:
                    continue

                amount_b = amount_a * price_a_to_b

                # Валидация промежуточного результата
                if amount_b <= 0:
                    continue

                # Шаг 3: CoinB -> USDT
                price_b_to_usdt = self.bybit.usdt_pairs.get(coin_b)
                if not price_b_to_usdt or price_b_to_usdt <= 0:
                    continue

                final_usdt = amount_b * price_b_to_usdt

                # Валидация финального результата
                if final_usdt <= 0:
                    continue

                spread = ((final_usdt - start_amount) / start_amount) * 100

                # Фильтрация
                if spread < min_spread or spread > max_spread:
                    continue

                # Дополнительная проверка на адекватность (защита от ошибок данных)
                if abs(spread) > 100:
                    continue

                opp = {
                    'type': 'triangular',
                    'path': f"USDT → {coin_a} → {coin_b} → USDT",
                    'scheme': 'Bybit Internal',
                    'coins': [coin_a, coin_b],
                    'initial': start_amount,
                    'final': final_usdt,
                    'profit': final_usdt - start_amount,
                    'spread': spread,
                    'steps': [
                        f"1️⃣  Купить {amount_a:.8f} {coin_a} за {start_amount:.2f} USDT (курс: 1 {coin_a} = {price_usdt_to_a:.8f} USDT)",
                        f"2️⃣  Обменять {amount_a:.8f} {coin_a} на {amount_b:.8f} {coin_b} (курс: 1 {coin_a} = {price_a_to_b:.8f} {coin_b})",
                        f"3️⃣  Продать {amount_b:.8f} {coin_b} за {final_usdt:.2f} USDT (курс: 1 {coin_b} = {price_b_to_usdt:.8f} USDT)"
                    ],
                    'timestamp': datetime.now().isoformat()
                }

                opportunities.append(opp)
                self.found_count += 1
                self._print_opportunity(opp, self.found_count)

        return opportunities

    async def _find_quadrilateral_arbitrage(self, start_amount, min_spread, max_spread):
        """
        Четырехугольный арбитраж: USDT -> CoinA -> CoinB -> CoinC -> USDT

        ИСПРАВЛЕНО:
        - Правильный расчёт всех кросс-курсов
        - Проверка существования всех пар
        - Валидация на каждом шаге
        """
        opportunities = []
        usdt_coins = list(self.bybit.usdt_pairs.keys())

        print(f"[Quadrilateral] Монет с USDT-парами: {len(usdt_coins)}")

        # Ограничиваем топ-100 для производительности
        top_coins = usdt_coins[:100]
        quad_checked = 0

        for coin_a in top_coins:
            # Шаг 1: USDT -> CoinA
            price_usdt_to_a = self.bybit.usdt_pairs.get(coin_a)
            if not price_usdt_to_a or price_usdt_to_a <= 0:
                continue

            amount_a = start_amount / price_usdt_to_a

            # Находим монеты, с которыми coin_a может торговаться
            for coin_b in top_coins:
                if coin_b == coin_a or coin_b == 'USDT':
                    continue

                # Шаг 2: CoinA -> CoinB (ИСПРАВЛЕНО)
                price_a_to_b = self._get_exchange_rate(coin_a, coin_b)
                if price_a_to_b is None or price_a_to_b <= 0:
                    continue

                amount_b = amount_a * price_a_to_b
                if amount_b <= 0:
                    continue

                for coin_c in top_coins:
                    if coin_c in [coin_a, coin_b, 'USDT']:
                        continue

                    # Проверяем, что CoinC имеет USDT пару
                    if coin_c not in self.bybit.usdt_pairs:
                        continue

                    quad_checked += 1

                    if quad_checked % 1000 == 0:
                        print(f"[Quadrilateral] 📊 Проверено: {quad_checked} | Найдено: {self.found_count}")

                    # Шаг 3: CoinB -> CoinC (ИСПРАВЛЕНО)
                    price_b_to_c = self._get_exchange_rate(coin_b, coin_c)
                    if price_b_to_c is None or price_b_to_c <= 0:
                        continue

                    amount_c = amount_b * price_b_to_c
                    if amount_c <= 0:
                        continue

                    # Шаг 4: CoinC -> USDT
                    price_c_to_usdt = self.bybit.usdt_pairs.get(coin_c)
                    if not price_c_to_usdt or price_c_to_usdt <= 0:
                        continue

                    final_usdt = amount_c * price_c_to_usdt
                    if final_usdt <= 0:
                        continue

                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    # Фильтрация
                    if spread < min_spread or spread > max_spread:
                        continue

                    # Защита от аномалий
                    if abs(spread) > 100:
                        continue

                    opp = {
                        'type': 'quadrilateral',
                        'path': f"USDT → {coin_a} → {coin_b} → {coin_c} → USDT",
                        'scheme': 'Bybit Internal (4-way)',
                        'coins': [coin_a, coin_b, coin_c],
                        'initial': start_amount,
                        'final': final_usdt,
                        'profit': final_usdt - start_amount,
                        'spread': spread,
                        'steps': [
                            f"1️⃣  Купить {amount_a:.8f} {coin_a} за {start_amount:.2f} USDT",
                            f"2️⃣  Обменять {amount_a:.8f} {coin_a} на {amount_b:.8f} {coin_b}",
                            f"3️⃣  Обменять {amount_b:.8f} {coin_b} на {amount_c:.8f} {coin_c}",
                            f"4️⃣  Продать {amount_c:.8f} {coin_c} за {final_usdt:.2f} USDT"
                        ],
                        'timestamp': datetime.now().isoformat()
                    }

                    opportunities.append(opp)
                    self.found_count += 1
                    self._print_opportunity(opp, self.found_count)

        return opportunities

    def _print_opportunity(self, opp, rank):
        """Выводит найденную возможность в консоль"""
        icon = "🔺" if opp['type'] == 'triangular' else "🔶"
        print(f"\n{icon} НАЙДЕНА СВЯЗКА #{rank} ({opp['type'].upper()})")
        print(f"{'─' * 100}")
        print(f"   📍 Путь: {opp['path']}")
        print(f"   💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
        print(f"   💵 ${opp['initial']:.2f} → ${opp['final']:.2f}")
        print(f"{'─' * 100}")

    async def analyze_specific_path(self, path, start_amount=100.0):
        """
        Анализирует конкретный путь

        ИСПРАВЛЕНО: использует _get_exchange_rate для правильного расчёта
        """
        print(f"\n[Analyzer] 🔬 Детальный анализ пути: {' → '.join(path)}")

        if len(path) < 3:
            return {'error': 'Путь должен содержать минимум 3 монеты'}

        if path[0] != 'USDT' or path[-1] != 'USDT':
            return {'error': 'Путь должен начинаться и заканчиваться на USDT'}

        try:
            current_amount = start_amount
            steps = []

            for i in range(len(path) - 1):
                from_coin = path[i]
                to_coin = path[i + 1]

                # ИСПРАВЛЕНО: используем правильный метод получения курса
                price = self._get_exchange_rate(from_coin, to_coin)

                if price is None:
                    return {'error': f'Пара {from_coin}/{to_coin} не найдена или не может быть рассчитана'}

                new_amount = current_amount * price
                step_info = f"{i + 1}. {current_amount:.8f} {from_coin} → {new_amount:.8f} {to_coin} (курс: {price:.8f})"
                steps.append(step_info)
                print(f"   {step_info}")

                current_amount = new_amount

            final_usdt = current_amount
            spread = ((final_usdt - start_amount) / start_amount) * 100
            profit = final_usdt - start_amount

            print(f"\n   ✅ Итог: {spread:.4f}% ({'+' if profit >= 0 else ''}{profit:.4f} USDT)")

            return {
                'success': True,
                'path': ' → '.join(path),
                'spread': spread,
                'profit': profit,
                'final': final_usdt
            }

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return {'error': str(e)}


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

async def main():
    print("=" * 100)
    print("🚀 CRYPTO ARBITRAGE BOT v6.0 — ВНУТРИБИРЖЕВОЙ АРБИТРАЖ НА BYBIT")
    print("=" * 100)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок")

    print(f"\n🔍 Типы арбитража:")
    print(f"   1️⃣  ТРЕУГОЛЬНЫЙ: USDT → LTC → BNB → USDT (3 сделки)")
    print(f"   2️⃣  ЧЕТЫРЕХУГОЛЬНЫЙ: USDT → BTC → ETH → BNB → USDT (4 сделки)\n")

    print("=" * 100)
    print("📊 ШАГ 1: ЗАГРУЗКА ДАННЫХ С BYBIT")
    print("=" * 100)

    async with BybitClientAsync() as bybit:
        await bybit.load_usdt_pairs()

        print(f"\n[Bybit] ✓ Загружено {len(bybit.usdt_pairs)} USDT-пар")
        print(f"[Bybit] ✓ Всего уникальных монет: {len(bybit.coins)}")
        print(f"[Bybit] ✓ Всего торговых пар: {len(bybit.trading_pairs)}")

        if len(bybit.trading_pairs) == 0:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: Не загружены торговые пары!")
            return

        print("\n" + "=" * 100)
        print("📊 ШАГ 2: ТЕСТОВЫЙ АНАЛИЗ ПРИМЕРОВ")
        print("=" * 100)

        analyzer = InternalArbitrageAnalyzer(bybit)

        print("\n🔬 Пример 1: Треугольный арбитраж")
        await analyzer.analyze_specific_path(['USDT', 'BTC', 'ETH', 'USDT'], START_AMOUNT)

        print("\n🔬 Пример 2: Четырехугольный арбитраж")
        await analyzer.analyze_specific_path(['USDT', 'BTC', 'ETH', 'BNB', 'USDT'], START_AMOUNT)

        print("\n" + "=" * 100)
        print("📊 ШАГ 3: ПОИСК ВСЕХ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
        print("=" * 100)
        print("\n💡 Результаты выводятся по мере обнаружения...\n")

        opportunities = await analyzer.find_arbitrage_opportunities(
            start_amount=START_AMOUNT,
            min_spread=MIN_SPREAD,
            max_spread=MAX_REASONABLE_SPREAD,
            check_triangular=True,
            check_quadrilateral=True
        )

        if opportunities:
            opportunities.sort(key=lambda x: x['profit'], reverse=True)

            print("\n" + "=" * 100)
            print("📈 ИТОГОВАЯ СТАТИСТИКА")
            print("=" * 100)

            print(f"\n📊 Всего найдено: {len(opportunities)} связок")
            print(f"\n🏆 ТОП-{min(SHOW_TOP, len(opportunities))} ЛУЧШИХ:")
            print("=" * 100)

            for idx, opp in enumerate(opportunities[:SHOW_TOP], 1):
                icon = "🔺" if opp['type'] == 'triangular' else "🔶"
                print(f"\n#{idx} {icon} | {opp['path']}")
                print(f"   💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                print(f"   💵 ${opp['initial']:.2f} → ${opp['final']:.2f}")

            print("\n" + "=" * 100)
            print("💾 СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
            print("=" * 100)

            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()

            saver = ResultsSaver()
            saved_files = saver.save_opportunities(
                opportunities=opportunities,
                start_amount=START_AMOUNT,
                min_spread=MIN_SPREAD,
                execution_time=elapsed,
                save_formats=['json', 'txt', 'csv', 'html']
            )

            print("\n📂 Файлы сохранены:")
            for fmt, path in saved_files.items():
                print(f"   • {fmt.upper()} → {path}")

        else:
            print(f"\n❌ Арбитражных связок не найдено")

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("\n" + "=" * 100)
    print(f"✅ АНАЛИЗ ЗАВЕРШЁН ЗА {elapsed:.2f} СЕКУНД")
    print("=" * 100)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Работа прервана пользователем.")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()