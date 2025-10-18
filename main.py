import asyncio
from datetime import datetime

from configs import (START_AMOUNT, MIN_SPREAD, SHOW_TOP,
                     ENABLE_COIN_FILTER, BLACKLIST_COINS, WHITELIST_COINS)
from bybit_handler import BybitClientAsync
from binance_handler import BinanceClientAsync
from arbitrage_analyzer import ArbitrageAnalyzerAsync
from results_saver import ResultsSaver


async def main():
    print("=" * 100)
    print("🚀 CRYPTO ARBITRAGE BOT v3.0 — DIRECT & TRIANGULAR ARBITRAGE")
    print("=" * 100)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок")
    print(f"\n🔍 Поддерживаемые схемы арбитража:")
    print(f"   1. 🔄 Прямой арбитраж:")
    print(f"      • Bybit → Binance")
    print(f"      • Binance → Bybit")
    print(f"   2. 🔺 Треугольный на одной бирже:")
    print(f"      • Bybit: USDT → CoinA → CoinB → USDT")
    print(f"      • Binance: USDT → CoinA → CoinB → USDT")
    print(f"   3. 🔀 Треугольный кросс-биржевой:")
    print(f"      • Bybit → Binance: USDT → CoinA (Bybit) → CoinB (Binance) → USDT")
    print(f"      • Binance → Bybit: USDT → CoinA (Binance) → CoinB (Bybit) → USDT\n")

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

        print(f"\n[Bybit] ✓ Загружено {len(bybit.usdt_pairs)} торговых пар USDT")
        bybit_preview = ', '.join(sorted(list(bybit.coins)[:15]))
        more_bybit = f" и еще {len(bybit.coins) - 15}" if len(bybit.coins) > 15 else ""
        print(f"[Bybit] ✓ Найденные монеты ({len(bybit.coins)}): {bybit_preview}{more_bybit}")

        print(f"\n[Binance] ✓ Загружено {len(binance.usdt_pairs)} торговых пар USDT")
        binance_preview = ', '.join(sorted(list(binance.coins)[:15]))
        more_binance = f" и еще {len(binance.coins) - 15}" if len(binance.coins) > 15 else ""
        print(f"[Binance] ✓ Найденные монеты ({len(binance.coins)}): {binance_preview}{more_binance}")

        # Пересечение монет между биржами
        common_exchanges = bybit.coins & binance.coins
        print(f"\n[Analysis] ✓ Общих монет между Bybit и Binance: {len(common_exchanges)}")
        if common_exchanges:
            exchanges_preview = ', '.join(sorted(list(common_exchanges)[:20]))
            more_exchanges = f" и еще {len(common_exchanges) - 20}" if len(common_exchanges) > 20 else ""
            print(f"[Analysis]   Примеры: {exchanges_preview}{more_exchanges}")

        # ───────────────────────────────────────────────────────────────
        # ШАГ 2: Поиск арбитражных возможностей
        # ───────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("🔍 ШАГ 2: ПОИСК АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
        print("=" * 100)

        analyzer = ArbitrageAnalyzerAsync(bybit, binance)
        opportunities = await analyzer.find_arbitrage_opportunities(
            start_amount=START_AMOUNT,
            min_spread=MIN_SPREAD,
            top_count=SHOW_TOP
        )

        # ───────────────────────────────────────────────────────────────
        # ШАГ 3: Сохранение результатов
        # ───────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("💾 ШАГ 3: СОХРАНЕНИЕ РЕЗУЛЬТАТОВ АНАЛИЗА")
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

        # ───────────────────────────────────────────────────────────────
        # ШАГ 4: Финальная статистика
        # ───────────────────────────────────────────────────────────────
        if opportunities:
            print("\n" + "=" * 100)
            print("📈 ФИНАЛЬНАЯ СТАТИСТИКА")
            print("=" * 100)

            types_stats = {}
            for opp in opportunities:
                opp_type = opp.get('type', 'unknown')
                if opp_type not in types_stats:
                    types_stats[opp_type] = {'count': 0, 'max_spread': 0, 'total_profit': 0}
                types_stats[opp_type]['count'] += 1
                types_stats[opp_type]['max_spread'] = max(types_stats[opp_type]['max_spread'], opp['spread'])
                types_stats[opp_type]['total_profit'] += opp['profit']

            type_names = {
                'direct': '🔄 Прямой арбитраж',
                'triangular_single': '🔺 Треугольный (одна биржа)',
                'triangular_cross': '🔀 Треугольный (кросс-биржевой)'
            }

            print("\nРаспределение по типам:")
            for opp_type, stats in sorted(types_stats.items(), key=lambda x: x[1]['max_spread'], reverse=True):
                type_name = type_names.get(opp_type, opp_type)
                print(f"\n{type_name}:")
                print(f"  • Найдено: {stats['count']} возможностей")
                print(f"  • Макс. спред: {stats['max_spread']:.4f}%")
                print(f"  • Суммарная прибыль: ${stats['total_profit']:.2f}")

            # Топ-5 самых прибыльных
            print("\n" + "=" * 100)
            print("🏆 ТОП-5 САМЫХ ПРИБЫЛЬНЫХ ВОЗМОЖНОСТЕЙ:")
            print("=" * 100 + "\n")

            for idx, opp in enumerate(opportunities[:5], 1):
                print(f"#{idx} | {opp['scheme']}")
                print(f"     Путь: {opp['path']}")
                print(f"     Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                print()

        print("\n" + "=" * 100)
        print(f"✅ АНАЛИЗ ЗАВЕРШЁН ЗА {elapsed:.2f} СЕКУНД")
        print("=" * 100)

        print("\n⚠️  ВАЖНЫЕ ЗАМЕЧАНИЯ:")
        print("   • Указанные спреды НЕ учитывают комиссии бирж (~0.1-0.2% за сделку)")
        print("   • Переводы между биржами требуют времени и комиссий")
        print("   • Проскальзывание цены может съесть часть прибыли")
        print("   • Треугольный арбитраж требует наличия реальных торговых пар")
        print("   • Всегда проверяйте актуальность данных перед сделкой!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Работа прервана пользователем.")
    except Exception as e:
        print(f"\n✗ Критическая ошибка выполнения: {e}")
        import traceback

        traceback.print_exc()