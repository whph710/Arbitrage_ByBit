import asyncio
from datetime import datetime
from configs import START_AMOUNT, MIN_SPREAD, SHOW_TOP
from bybit_handler import BybitClientAsync
from binance_handler import BinanceClientAsync
from arbitrage_analyzer import ArbitrageAnalyzerAsync
from results_saver import ResultsSaver


async def main():
    print("=" * 100)
    print("🚀 CRYPTO ARBITRAGE BOT v5.0 — ПРЯМОЙ И ТРЕУГОЛЬНЫЙ АРБИТРАЖ")
    print("=" * 100)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок")

    print(f"\n🔍 Типы арбитража:")
    print(f"   1️⃣  ПРЯМОЙ: USDT → LTC → USDT (Bybit ↔ Binance)")
    print(f"   2️⃣  ТРЕУГОЛЬНЫЙ: USDT → LTC → BNB → USDT (одна биржа)")
    print(f"   3️⃣  КРОСС-ТРЕУГОЛЬНЫЙ: USDT → LTC → BNB → USDT (Bybit → Binance)\n")

    # ───────────────────────────────────────────────────────────────
    # ШАГ 1: Загрузка данных с бирж
    # ───────────────────────────────────────────────────────────────
    print("=" * 100)
    print("📊 ШАГ 1: ЗАГРУЗКА ДАННЫХ С БИРЖ")
    print("=" * 100)

    async with BybitClientAsync() as bybit, BinanceClientAsync() as binance:
        # Загружаем данные параллельно
        await asyncio.gather(
            bybit.load_usdt_pairs(),
            binance.load_usdt_pairs()
        )

        print(f"\n[Bybit] ✓ Загружено {len(bybit.usdt_pairs)} пар")
        print(f"[Binance] ✓ Загружено {len(binance.usdt_pairs)} пар")

        # Общие монеты
        common_coins = bybit.coins & binance.coins
        print(f"\n✅ Общих монет на обеих биржах: {len(common_coins)}")

        if len(common_coins) > 0:
            preview = ', '.join(sorted(list(common_coins)[:20]))
            more = f" и еще {len(common_coins) - 20}" if len(common_coins) > 20 else ""
            print(f"   Примеры: {preview}{more}")

        # ───────────────────────────────────────────────────────────────
        # ШАГ 2: Анализ арбитража с выводом в реальном времени
        # ───────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("📊 ШАГ 2: ПОИСК АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
        print("=" * 100)
        print("\n💡 Результаты выводятся по мере обнаружения...\n")

        analyzer = ArbitrageAnalyzerAsync(bybit, binance)

        opportunities = await analyzer.find_arbitrage_opportunities(
            start_amount=START_AMOUNT,
            min_spread=MIN_SPREAD,
            top_count=None  # Получаем все, сортировку сделаем в конце
        )

        # ───────────────────────────────────────────────────────────────
        # ШАГ 3: Итоговые результаты (отсортированные по прибыли)
        # ───────────────────────────────────────────────────────────────
        if opportunities:
            # Сортируем по прибыли (не спреду!)
            opportunities.sort(key=lambda x: x['profit'], reverse=True)

            print("\n" + "=" * 100)
            print("📈 ИТОГОВАЯ СТАТИСТИКА (ОТСОРТИРОВАНО ПО ПРИБЫЛИ)")
            print("=" * 100)

            # Статистика
            total_profit = sum(opp['profit'] for opp in opportunities)
            avg_spread = sum(opp['spread'] for opp in opportunities) / len(opportunities)
            max_profit_opp = opportunities[0]

            print(f"\n📊 Общая статистика:")
            print(f"   • Всего связок найдено: {len(opportunities)}")
            print(f"   • Суммарная потенциальная прибыль: ${total_profit:.2f}")
            print(f"   • Средний спред: {avg_spread:.4f}%")
            print(f"   • Максимальная прибыль: ${max_profit_opp['profit']:.2f} ({max_profit_opp['spread']:.4f}%)")

            # Статистика по типам
            types_count = {}
            for opp in opportunities:
                opp_type = opp.get('type', 'unknown')
                types_count[opp_type] = types_count.get(opp_type, 0) + 1

            print(f"\n📋 Распределение по типам:")
            type_names = {
                'direct': '🔄 Прямой арбитраж',
                'triangular_single': '🔺 Треугольный (одна биржа)',
                'triangular_cross': '🔀 Треугольный (кросс-биржевой)'
            }
            for opp_type, count in types_count.items():
                print(f"   • {type_names.get(opp_type, opp_type)}: {count}")

            # Топ лучших по прибыли
            print("\n" + "=" * 100)
            print(f"🏆 ТОП-{min(SHOW_TOP, len(opportunities))} СВЯЗОК ПО ПРИБЫЛИ:")
            print("=" * 100)

            for idx, opp in enumerate(opportunities[:SHOW_TOP], 1):
                print(f"\n{'─' * 100}")
                print(f"#{idx} | {opp['scheme']} | {opp['path']}")
                print(f"{'─' * 100}")
                print(f"💰 Прибыль: ${opp['profit']:.4f} | Спред: {opp['spread']:.4f}%")
                print(f"💵 Начальная сумма: ${opp['initial']:.2f} → Финальная: ${opp['final']:.2f}")
                print(f"\n📝 Пошаговые действия:")
                for step in opp['steps']:
                    print(f"   {step}")

            # ───────────────────────────────────────────────────────────────
            # ШАГ 4: Сохранение результатов
            # ───────────────────────────────────────────────────────────────
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
            print(f"\n❌ Арбитражных связок со спредом >= {MIN_SPREAD}% не найдено")
            print(f"💡 Попробуйте:")
            print(f"   - Уменьшить MIN_SPREAD в configs.py")
            print(f"   - Проверить доступность торговых пар")

    # ───────────────────────────────────────────────────────────────
    # ИТОГИ
    # ───────────────────────────────────────────────────────────────
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("\n" + "=" * 100)
    print(f"✅ АНАЛИЗ ЗАВЕРШЁН ЗА {elapsed:.2f} СЕКУНД")
    print("=" * 100)

    print("\n⚠️  ВАЖНЫЕ ЗАМЕЧАНИЯ:")
    print("   • Указанные спреды НЕ учитывают:")
    print("     - Комиссии бирж за покупку/продажу (~0.1-0.2%)")
    print("     - Комиссии сети за переводы (0.0001-0.01 монеты)")
    print("     - Проскальзывание цены при больших объёмах")
    print("   • Время выполнения связки:")
    print("     - Прямой арбитраж: 10-30 минут (время перевода)")
    print("     - Треугольный: мгновенно (на одной бирже)")
    print("     - Кросс-треугольный: 10-30 минут")
    print("   • Цены постоянно меняются - проверяйте актуальность перед сделкой!")
    print("   • Всегда делайте тестовые сделки с минимальной суммой!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Работа прервана пользователем.")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()