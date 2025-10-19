import asyncio
from datetime import datetime
from configs import (
    START_AMOUNT, MIN_SPREAD, SHOW_TOP, MAX_REASONABLE_SPREAD,
    CHECK_TRIANGULAR, CHECK_QUADRILATERAL, BESTCHANGE_API_KEY
)
from bybit_handler import BybitClientAsync
from bestchange_handler import BestChangeClientAsync
from exchange_arbitrage_analyzer import ExchangeArbitrageAnalyzer
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
        print(f"\n[Internal Arbitrage] 🔍 Начало поиска внутрибиржевого арбитража на Bybit")
        print(f"[Internal Arbitrage] Параметры: начальная сумма = ${start_amount}, спред = {min_spread}%-{max_spread}%")

        opportunities = []
        self.found_count = 0
        self.checked_count = 0

        # Треугольный арбитраж
        if check_triangular:
            print("\n" + "=" * 100)
            print("[Internal Arbitrage] 🔺 Поиск треугольного арбитража: USDT -> A -> B -> USDT")
            print("=" * 100)

            tri_opps = await self._find_triangular_arbitrage(start_amount, min_spread, max_spread)
            opportunities.extend(tri_opps)

            print("=" * 100)
            print(f"[Internal Arbitrage] ✓ Треугольный: найдено {len(tri_opps)} возможностей\n")

        # Четырехугольный арбитраж
        if check_quadrilateral:
            print("=" * 100)
            print("[Internal Arbitrage] 🔶 Поиск четырехугольного арбитража: USDT -> A -> B -> C -> USDT")
            print("=" * 100)

            quad_opps = await self._find_quadrilateral_arbitrage(start_amount, min_spread, max_spread)
            opportunities.extend(quad_opps)

            print("=" * 100)
            print(f"[Internal Arbitrage] ✓ Четырехугольный: найдено {len(quad_opps)} возможностей\n")

        return opportunities

    def _get_exchange_rate(self, from_coin: str, to_coin: str) -> float:
        """Правильно рассчитывает курс обмена from_coin -> to_coin"""
        # Вариант 1: Прямая пара
        direct_price = self.bybit.get_price(from_coin, to_coin)
        if direct_price is not None and direct_price > 0:
            return direct_price

        # Вариант 2: Через USDT
        if from_coin != 'USDT' and to_coin != 'USDT':
            from_usdt_price = self.bybit.usdt_pairs.get(from_coin)
            to_usdt_price = self.bybit.usdt_pairs.get(to_coin)

            if from_usdt_price and to_usdt_price and from_usdt_price > 0 and to_usdt_price > 0:
                return from_usdt_price / to_usdt_price

        return None

    async def _find_triangular_arbitrage(self, start_amount, min_spread, max_spread):
        """Треугольный арбитраж: USDT -> CoinA -> CoinB -> USDT"""
        opportunities = []
        usdt_coins = list(self.bybit.usdt_pairs.keys())

        print(f"[Triangular] Монет с USDT-парами: {len(usdt_coins)}")

        for i, coin_a in enumerate(usdt_coins):
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

                price_a_to_b = self._get_exchange_rate(coin_a, coin_b)
                if price_a_to_b is None or price_a_to_b <= 0:
                    continue

                amount_b = amount_a * price_a_to_b
                if amount_b <= 0:
                    continue

                price_b_to_usdt = self.bybit.usdt_pairs.get(coin_b)
                if not price_b_to_usdt or price_b_to_usdt <= 0:
                    continue

                final_usdt = amount_b * price_b_to_usdt
                if final_usdt <= 0:
                    continue

                spread = ((final_usdt - start_amount) / start_amount) * 100

                if spread < min_spread or spread > max_spread or abs(spread) > 100:
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
        """Четырехугольный арбитраж: USDT -> CoinA -> CoinB -> CoinC -> USDT"""
        opportunities = []
        usdt_coins = list(self.bybit.usdt_pairs.keys())

        print(f"[Quadrilateral] Монет с USDT-парами: {len(usdt_coins)}")

        top_coins = usdt_coins[:100]
        quad_checked = 0

        for coin_a in top_coins:
            price_usdt_to_a = self.bybit.usdt_pairs.get(coin_a)
            if not price_usdt_to_a or price_usdt_to_a <= 0:
                continue

            amount_a = start_amount / price_usdt_to_a

            for coin_b in top_coins:
                if coin_b == coin_a or coin_b == 'USDT':
                    continue

                price_a_to_b = self._get_exchange_rate(coin_a, coin_b)
                if price_a_to_b is None or price_a_to_b <= 0:
                    continue

                amount_b = amount_a * price_a_to_b
                if amount_b <= 0:
                    continue

                for coin_c in top_coins:
                    if coin_c in [coin_a, coin_b, 'USDT']:
                        continue

                    if coin_c not in self.bybit.usdt_pairs:
                        continue

                    quad_checked += 1

                    if quad_checked % 1000 == 0:
                        print(f"[Quadrilateral] 📊 Проверено: {quad_checked} | Найдено: {self.found_count}")

                    price_b_to_c = self._get_exchange_rate(coin_b, coin_c)
                    if price_b_to_c is None or price_b_to_c <= 0:
                        continue

                    amount_c = amount_b * price_b_to_c
                    if amount_c <= 0:
                        continue

                    price_c_to_usdt = self.bybit.usdt_pairs.get(coin_c)
                    if not price_c_to_usdt or price_c_to_usdt <= 0:
                        continue

                    final_usdt = amount_c * price_c_to_usdt
                    if final_usdt <= 0:
                        continue

                    spread = ((final_usdt - start_amount) / start_amount) * 100

                    if spread < min_spread or spread > max_spread or abs(spread) > 100:
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


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

async def main():
    print("=" * 100)
    print("🚀 CRYPTO ARBITRAGE BOT v7.0 — ПОЛНЫЙ АНАЛИЗ АРБИТРАЖА")
    print("=" * 100)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок")

    print(f"\n🔍 Типы арбитража:")
    print(f"   1️⃣  ВНУТРИБИРЖЕВОЙ ТРЕУГОЛЬНЫЙ: USDT → A → B → USDT (3 сделки на Bybit)")
    print(f"   2️⃣  ВНУТРИБИРЖЕВОЙ ЧЕТЫРЕХУГОЛЬНЫЙ: USDT → A → B → C → USDT (4 сделки на Bybit)")
    print(f"   3️⃣  ЧЕРЕЗ ОБМЕННИКИ: Bybit → BestChange → Bybit (5 шагов)\n")

    all_opportunities = []

    # ========================================================================
    # ШАГ 1: ЗАГРУЗКА ДАННЫХ С BYBIT
    # ========================================================================
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

        # ====================================================================
        # ШАГ 2: ВНУТРИБИРЖЕВОЙ АРБИТРАЖ
        # ====================================================================
        print("\n" + "=" * 100)
        print("📊 ШАГ 2: ВНУТРИБИРЖЕВОЙ АРБИТРАЖ НА BYBIT")
        print("=" * 100)

        internal_analyzer = InternalArbitrageAnalyzer(bybit)
        internal_opps = await internal_analyzer.find_arbitrage_opportunities(
            start_amount=START_AMOUNT,
            min_spread=MIN_SPREAD,
            max_spread=MAX_REASONABLE_SPREAD,
            check_triangular=CHECK_TRIANGULAR,
            check_quadrilateral=CHECK_QUADRILATERAL
        )

        all_opportunities.extend(internal_opps)
        print(f"\n[Internal Arbitrage] ✅ Найдено {len(internal_opps)} внутрибиржевых связок")

        # ====================================================================
        # ШАГ 3: АРБИТРАЖ ЧЕРЕЗ ОБМЕННИКИ (BESTCHANGE)
        # ====================================================================
        if BESTCHANGE_API_KEY:
            print("\n" + "=" * 100)
            print("📊 ШАГ 3: ЗАГРУЗКА ДАННЫХ С BESTCHANGE")
            print("=" * 100)

            try:
                async with BestChangeClientAsync() as bestchange:
                    # Загрузка валют и обменников
                    await bestchange.load_currencies()
                    await bestchange.load_exchangers()

                    # Находим общие монеты
                    common_coins = set(bybit.usdt_pairs.keys()) & set(bestchange.crypto_currencies.keys())
                    print(f"\n[BestChange] ✓ Общих монет с Bybit: {len(common_coins)}")

                    if len(common_coins) > 0:
                        # Загружаем курсы для общих монет
                        await bestchange.load_rates(list(common_coins), use_rankrate=True)

                        print("\n" + "=" * 100)
                        print("📊 ШАГ 4: ПОИСК АРБИТРАЖА ЧЕРЕЗ ОБМЕННИКИ")
                        print("=" * 100)

                        exchange_analyzer = ExchangeArbitrageAnalyzer(bybit, bestchange)
                        exchange_opps = await exchange_analyzer.find_opportunities(
                            start_amount=START_AMOUNT,
                            min_spread=MIN_SPREAD,
                            max_spread=MAX_REASONABLE_SPREAD,
                            min_reserve=0,
                            parallel_requests=50
                        )

                        all_opportunities.extend(exchange_opps)
                        print(f"\n[BestChange Arbitrage] ✅ Найдено {len(exchange_opps)} связок через обменники")

                    else:
                        print(f"\n[BestChange] ⚠️  Нет общих монет для арбитража")

            except Exception as e:
                print(f"\n[BestChange] ❌ Ошибка при работе с BestChange: {e}")
                print(f"[BestChange] ⚠️  Продолжаем без анализа обменников")

        else:
            print("\n" + "=" * 100)
            print("⚠️  BESTCHANGE API KEY НЕ ЗАДАН - ПРОПУСКАЕМ АНАЛИЗ ОБМЕННИКОВ")
            print("=" * 100)
            print("Для включения анализа обменников:")
            print("1. Получите API ключ на https://www.bestchange.com/wiki/api.html")
            print("2. Добавьте в .env файл: BESTCHANGE_API_KEY=ваш_ключ")

        # ====================================================================
        # ИТОГОВЫЕ РЕЗУЛЬТАТЫ
        # ====================================================================
        if all_opportunities:
            all_opportunities.sort(key=lambda x: x['profit'], reverse=True)

            print("\n" + "=" * 100)
            print("📈 ИТОГОВАЯ СТАТИСТИКА")
            print("=" * 100)

            # Статистика по типам
            types_count = {}
            for opp in all_opportunities:
                opp_type = opp.get('type', 'unknown')
                types_count[opp_type] = types_count.get(opp_type, 0) + 1

            print(f"\n📊 Всего найдено: {len(all_opportunities)} связок")
            print(f"\n📊 По типам:")
            type_names = {
                'triangular': '🔺 Треугольный (Bybit)',
                'quadrilateral': '🔶 Четырехугольный (Bybit)',
                'bestchange_arbitrage': '🔀 Через BestChange'
            }
            for opp_type, count in types_count.items():
                type_name = type_names.get(opp_type, opp_type)
                print(f"   {type_name}: {count}")

            print(f"\n🏆 ТОП-{min(SHOW_TOP, len(all_opportunities))} ЛУЧШИХ:")
            print("=" * 100)

            for idx, opp in enumerate(all_opportunities[:SHOW_TOP], 1):
                type_icons = {
                    'triangular': '🔺',
                    'quadrilateral': '🔶',
                    'bestchange_arbitrage': '🔀'
                }
                icon = type_icons.get(opp.get('type'), '📊')

                print(f"\n#{idx} {icon} | {opp['path']}")
                print(f"   💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                print(f"   💵 ${opp['initial']:.2f} → ${opp['final']:.2f}")
                print(f"   📍 Схема: {opp['scheme']}")

                if opp.get('type') == 'bestchange_arbitrage':
                    print(f"   🏦 Обменник: {opp.get('exchanger', 'N/A')}")

            # ================================================================
            # СОХРАНЕНИЕ РЕЗУЛЬТАТОВ
            # ================================================================
            print("\n" + "=" * 100)
            print("💾 СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
            print("=" * 100)

            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()

            saver = ResultsSaver()
            saved_files = saver.save_opportunities(
                opportunities=all_opportunities,
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