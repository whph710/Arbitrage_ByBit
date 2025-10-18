import asyncio
from datetime import datetime

from configs import START_AMOUNT, MIN_SPREAD, SHOW_TOP
from bybit_handler import BybitClientAsync
from binance_handler import BinanceClientAsync
from bestchange_handler import BestChangeClientAsync
from arbitrage_analyzer import ArbitrageAnalyzerAsync
from results_saver import ResultsSaver


async def main():
    print("=" * 100)
    print("🚀 CRYPTO ARBITRAGE BOT v2.0 — MULTI-EXCHANGE MODE")
    print("=" * 100)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок")
    print(f"\n🔍 Поддерживаемые схемы арбитража:")
    print(f"   1. Bybit → BestChange → Bybit")
    print(f"   2. Binance → BestChange → Binance")
    print(f"   3. Bybit → BestChange → Binance")
    print(f"   4. Binance → BestChange → Bybit")
    print(f"   5. Bybit ↔ Binance (прямой арбитраж)\n")

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
        # ШАГ 2: Инициализация BestChange
        # ───────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("📊 ШАГ 2: ИНИЦИАЛИЗАЦИЯ BESTCHANGE API v2.0")
        print("=" * 100)

        async with BestChangeClientAsync() as bc:
            print("[BestChange] Загрузка валют...")
            await bc.load_currencies()
            print(f"[BestChange] ✓ Всего валют: {len(bc.currencies)}")
            print(f"[BestChange] ✓ Криптовалют: {len(bc.crypto_currencies)}")

            # Показываем примеры криптовалют
            crypto_preview = ', '.join(sorted(list(bc.crypto_currencies.keys())[:20]))
            more_crypto = f" и еще {len(bc.crypto_currencies) - 20}" if len(bc.crypto_currencies) > 20 else ""
            print(f"[BestChange]   Примеры: {crypto_preview}{more_crypto}")

            print("\n[BestChange] Загрузка обменников...")
            await bc.load_exchangers()
            print(f"[BestChange] ✓ Активных обменников: {len(bc.changers)}")

            # Пересечение монет: (Bybit ∪ Binance) ∩ BestChange
            all_exchange_coins = bybit.coins | binance.coins
            common_with_bestchange = list(all_exchange_coins & set(bc.crypto_currencies.keys()))

            print(f"\n[Analysis] ✓ Монет доступных на биржах: {len(all_exchange_coins)}")
            print(f"[Analysis] ✓ Общих монет с BestChange: {len(common_with_bestchange)}")

            if common_with_bestchange:
                common_bc_preview = ', '.join(sorted(common_with_bestchange[:20]))
                more_bc = f" и еще {len(common_with_bestchange) - 20}" if len(common_with_bestchange) > 20 else ""
                print(f"[Analysis]   Общие монеты: {common_bc_preview}{more_bc}")

            if not common_with_bestchange:
                print("\n❌ Нет общих монет между биржами и BestChange. Проверьте данные.")
                return

            # ───────────────────────────────────────────────────────────────
            # ШАГ 3: Загрузка курсов BestChange
            # ───────────────────────────────────────────────────────────────
            print("\n" + "=" * 100)
            print("📊 ШАГ 3: ЗАГРУЗКА КУРСОВ BESTCHANGE (BATCH MODE)")
            print("=" * 100)
            print(f"[BestChange] Загрузка курсов для {len(common_with_bestchange)} монет...")
            print("[BestChange] Используется пакетная загрузка с оптимизированными задержками")

            await bc.load_rates(common_with_bestchange)

            # Подсчитываем статистику
            total_directions = sum(len(pairs) for pairs in bc.rates.values())
            print(f"\n[BestChange] ✓ Загружено направлений обмена: {total_directions}")
            print(f"[BestChange] ✓ Валют с доступными курсами: {len(bc.rates)}")

            # Статистика по схемам
            bybit_bc_coins = list(bybit.coins & set(bc.crypto_currencies.keys()))
            binance_bc_coins = list(binance.coins & set(bc.crypto_currencies.keys()))

            print(f"\n[Analysis] 📊 СТАТИСТИКА ПО ДОСТУПНЫМ СХЕМАМ:")
            print(f"   ├─ Bybit + BestChange: {len(bybit_bc_coins)} монет")
            print(f"   ├─ Binance + BestChange: {len(binance_bc_coins)} монет")
            print(f"   ├─ Bybit ↔ Binance: {len(common_exchanges)} монет")
            print(
                f"   └─ Все три источника: {len(bybit.coins & binance.coins & set(bc.crypto_currencies.keys()))} монет")

            # ───────────────────────────────────────────────────────────────
            # ШАГ 4: Поиск арбитражных возможностей
            # ───────────────────────────────────────────────────────────────
            print("\n" + "=" * 100)
            print("🔍 ШАГ 4: ПОИСК АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ (МУЛЬТИ-СХЕМА)")
            print("=" * 100)

            analyzer = ArbitrageAnalyzerAsync(bybit, binance, bc)
            opportunities = await analyzer.find_circular_opportunities(
                start_amount=START_AMOUNT,
                min_spread=MIN_SPREAD,
                top_count=None
            )

            # ───────────────────────────────────────────────────────────────
            # ШАГ 5: Сохранение результатов
            # ───────────────────────────────────────────────────────────────
            print("\n" + "=" * 100)
            print("💾 ШАГ 5: СОХРАНЕНИЕ РЕЗУЛЬТАТОВ АНАЛИЗА")
            print("=" * 100)

            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()

            saver = ResultsSaver()
            saved_files = saver.save_opportunities(
                opportunities=opportunities,
                start_amount=START_AMOUNT,
                min_spread=MIN_SPREAD,
                execution_time=elapsed,
                save_formats=['json', 'txt', 'csv', 'html']  # можешь убрать ненужные форматы
            )

            print("\n📂 Файлы сохранены:")
            for fmt, path in saved_files.items():
                print(f"   • {fmt.upper()} → {path}")

            # ───────────────────────────────────────────────────────────────
            # ШАГ 6: Статистика по схемам
            # ───────────────────────────────────────────────────────────────
            if opportunities:
                print("\n" + "=" * 100)
                print("📈 СТАТИСТИКА ПО НАЙДЕННЫМ ВОЗМОЖНОСТЯМ")
                print("=" * 100)

                schemes_stats = {}
                for opp in opportunities:
                    scheme = opp['scheme']
                    if scheme not in schemes_stats:
                        schemes_stats[scheme] = {'count': 0, 'max_spread': 0, 'total_profit': 0}
                    schemes_stats[scheme]['count'] += 1
                    schemes_stats[scheme]['max_spread'] = max(schemes_stats[scheme]['max_spread'], opp['spread'])
                    schemes_stats[scheme]['total_profit'] += opp['profit']

                print("\nРаспределение по схемам:")
                for scheme, stats in sorted(schemes_stats.items(), key=lambda x: x[1]['max_spread'], reverse=True):
                    print(f"   • {scheme}")
                    print(f"     Найдено: {stats['count']} возможностей")
                    print(f"     Макс. спред: {stats['max_spread']:.4f}%")
                    print(f"     Общая потенциальная прибыль: ${stats['total_profit']:.2f}")
                    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Работа прервана пользователем.")
    except Exception as e:
        print(f"\n✗ Критическая ошибка выполнения: {e}")
        import traceback

        traceback.print_exc()