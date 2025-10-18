import asyncio
from datetime import datetime

from configs import (
    START_AMOUNT, MIN_SPREAD, SHOW_TOP,
    CHANGENOW_API_KEY, SWAPZONE_API_KEY,
    MAX_PAIRS_TO_CHECK, PARALLEL_EXCHANGE_REQUESTS
)
from bybit_handler import BybitClientAsync
from changenow_handler import ChangeNowClientAsync
from swapzone_handler import SwapzoneClientAsync
from exchange_arbitrage_analyzer import SimpleExchangeAnalyzer
from results_saver import ResultsSaver


async def main():
    print("=" * 100)
    print("🚀 CRYPTO ARBITRAGE BOT v4.0 — ПРОСТОЙ АРБИТРАЖ ЧЕРЕЗ ОБМЕННИКИ")
    print("=" * 100)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок")
    print(f"🔢 Максимум пар для проверки: {MAX_PAIRS_TO_CHECK}")
    print(f"⚡ Параллельных запросов: {PARALLEL_EXCHANGE_REQUESTS}")
    print(f"\n🔍 Схема арбитража:")
    print(f"   1️⃣ Купить CoinA за USDT на Bybit")
    print(f"   2️⃣ Отправить CoinA на обменник")
    print(f"   3️⃣ Обменять CoinA → CoinB на обменнике")
    print(f"   4️⃣ Продать CoinB за USDT на Bybit")
    print(f"   5️⃣ Получить прибыль!\n")

    # ───────────────────────────────────────────────────────────────
    # ШАГ 1: Загрузка данных с Bybit
    # ───────────────────────────────────────────────────────────────
    print("=" * 100)
    print("📊 ШАГ 1: ЗАГРУЗКА ДАННЫХ С BYBIT")
    print("=" * 100)

    async with BybitClientAsync() as bybit:
        await bybit.load_usdt_pairs()

        print(f"\n[Bybit] ✓ Загружено {len(bybit.usdt_pairs)} торговых пар USDT")
        bybit_preview = ', '.join(sorted(list(bybit.coins)[:20]))
        more_bybit = f" и еще {len(bybit.coins) - 20}" if len(bybit.coins) > 20 else ""
        print(f"[Bybit] ✓ Найденные монеты ({len(bybit.coins)}): {bybit_preview}{more_bybit}")

        all_opportunities = []

        # ───────────────────────────────────────────────────────────────
        # ШАГ 2: Проверка SWAPZONE (приоритет #1)
        # ───────────────────────────────────────────────────────────────
        if SWAPZONE_API_KEY:
            print("\n" + "=" * 100)
            print("📊 ШАГ 2: АНАЛИЗ SWAPZONE (ПРИОРИТЕТ #1)")
            print("=" * 100)

            try:
                swapzone = SwapzoneClientAsync(api_key=SWAPZONE_API_KEY)
                await swapzone.create_session()
                await swapzone.load_available_currencies()

                if len(swapzone.available_currencies) > 0:
                    analyzer = SimpleExchangeAnalyzer(bybit, swapzone, "Swapzone")

                    swapzone_opps = await analyzer.find_opportunities(
                        start_amount=START_AMOUNT,
                        min_spread=MIN_SPREAD,
                        max_pairs=MAX_PAIRS_TO_CHECK,
                        parallel_requests=PARALLEL_EXCHANGE_REQUESTS
                    )

                    all_opportunities.extend(swapzone_opps)

                    print(f"\n[Swapzone] ✅ Найдено {len(swapzone_opps)} связок")
                else:
                    print(f"\n[Swapzone] ⚠️ Нет доступных валют, пропускаем")

                await swapzone.close()

            except Exception as e:
                print(f"\n[Swapzone] ❌ Ошибка: {e}")
        else:
            print("\n[!] SWAPZONE_API_KEY не задан, пропускаем Swapzone")

        # ───────────────────────────────────────────────────────────────
        # ШАГ 3: Проверка CHANGENOW (приоритет #2)
        # ───────────────────────────────────────────────────────────────
        if CHANGENOW_API_KEY or True:  # ChangeNOW работает и без ключа
            print("\n" + "=" * 100)
            print("📊 ШАГ 3: АНАЛИЗ CHANGENOW (ПРИОРИТЕТ #2)")
            print("=" * 100)

            try:
                changenow = ChangeNowClientAsync(api_key=CHANGENOW_API_KEY if CHANGENOW_API_KEY else None)
                await changenow.create_session()
                await changenow.load_available_currencies()

                if len(changenow.available_currencies) > 0:
                    analyzer = SimpleExchangeAnalyzer(bybit, changenow, "ChangeNOW")

                    changenow_opps = await analyzer.find_opportunities(
                        start_amount=START_AMOUNT,
                        min_spread=MIN_SPREAD,
                        max_pairs=MAX_PAIRS_TO_CHECK,
                        parallel_requests=PARALLEL_EXCHANGE_REQUESTS
                    )

                    all_opportunities.extend(changenow_opps)

                    print(f"\n[ChangeNOW] ✅ Найдено {len(changenow_opps)} связок")
                else:
                    print(f"\n[ChangeNOW] ⚠️ Нет доступных валют, пропускаем")

                await changenow.close()

            except Exception as e:
                print(f"\n[ChangeNOW] ❌ Ошибка: {e}")

        # ───────────────────────────────────────────────────────────────
        # ШАГ 4: Сводная статистика и сохранение
        # ───────────────────────────────────────────────────────────────
        if all_opportunities:
            print("\n" + "=" * 100)
            print("📈 ИТОГОВАЯ СТАТИСТИКА")
            print("=" * 100)

            # Сортируем по спреду
            all_opportunities.sort(key=lambda x: x['spread'], reverse=True)

            # Статистика по обменникам
            exchange_stats = {}
            for opp in all_opportunities:
                exchange = opp.get('exchange_used', 'Unknown')
                if exchange not in exchange_stats:
                    exchange_stats[exchange] = {'count': 0, 'total_profit': 0, 'max_spread': 0}
                exchange_stats[exchange]['count'] += 1
                exchange_stats[exchange]['total_profit'] += opp['profit']
                exchange_stats[exchange]['max_spread'] = max(exchange_stats[exchange]['max_spread'], opp['spread'])

            print(f"\n📊 Статистика по обменникам:")
            for exchange, stats in sorted(exchange_stats.items(), key=lambda x: x[1]['count'], reverse=True):
                print(f"\n   🔹 {exchange}:")
                print(f"      • Найдено связок: {stats['count']}")
                print(f"      • Макс. спред: {stats['max_spread']:.4f}%")
                print(f"      • Суммарная прибыль: ${stats['total_profit']:.2f}")

            print(f"\n📊 Общая статистика:")
            print(f"   • Всего связок: {len(all_opportunities)}")
            print(f"   • Общая потенциальная прибыль: ${sum(opp['profit'] for opp in all_opportunities):.2f}")
            print(
                f"   • Средний спред: {sum(opp['spread'] for opp in all_opportunities) / len(all_opportunities):.4f}%")
            print(f"   • Максимальный спред: {all_opportunities[0]['spread']:.4f}%")

            # Топ-10 лучших
            print("\n" + "=" * 100)
            print(f"🏆 ТОП-{min(SHOW_TOP, len(all_opportunities))} ЛУЧШИХ СВЯЗОК:")
            print("=" * 100 + "\n")

            for idx, opp in enumerate(all_opportunities[:SHOW_TOP], 1):
                print(f"#{idx} | {opp['path']} | через {opp['exchange_used']}")
                print(f"     💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                print(f"     📊 Детали:")
                for step in opp['steps']:
                    print(f"        {step}")
                print()

            # Сохранение результатов
            print("=" * 100)
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
            print(f"\n❌ Арбитражных связок со спредом >= {MIN_SPREAD}% не найдено")
            print(f"💡 Попробуйте:")
            print(f"   - Уменьшить MIN_SPREAD в configs.py")
            print(f"   - Увеличить MAX_PAIRS_TO_CHECK")
            print(f"   - Проверить API ключи обменников")

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("\n" + "=" * 100)
    print(f"✅ АНАЛИЗ ЗАВЕРШЁН ЗА {elapsed:.2f} СЕКУНД")
    print("=" * 100)

    print("\n⚠️  ВАЖНЫЕ ЗАМЕЧАНИЯ:")
    print("   • Указанные спреды НЕ учитывают:")
    print("     - Комиссии Bybit за покупку/продажу (~0.1%)")
    print("     - Комиссии обменника за обмен (обычно 0.5-2%)")
    print("     - Комиссии сети за переводы")
    print("     - Проскальзывание цены при больших объёмах")
    print("   • Время выполнения связки:")
    print("     - Покупка на Bybit: мгновенно")
    print("     - Перевод на обменник: 10-30 минут")
    print("     - Обмен на обменнике: 5-30 минут")
    print("     - Продажа на Bybit: мгновенно")
    print("   • За 40-60 минут цены могут сильно измениться!")
    print("   • Всегда делайте тестовый обмен с минимальной суммой!")


async def test_specific_exchange():
    """Тестирование конкретного обменника"""
    print("=" * 100)
    print("🔬 ТЕСТ ОБМЕННИКА")
    print("=" * 100)

    async with BybitClientAsync() as bybit:
        await bybit.load_usdt_pairs()

        # Тест Swapzone
        if SWAPZONE_API_KEY:
            print("\n📊 Тестирование Swapzone...")
            swapzone = SwapzoneClientAsync(api_key=SWAPZONE_API_KEY)
            await swapzone.create_session()
            await swapzone.load_available_currencies()

            # Пробуем получить курс BTC → ETH
            test_result = await swapzone.get_estimated_amount('BTC', 'ETH', 0.01)
            print(f"\n🧪 Тест: 0.01 BTC → ETH")
            print(f"Результат: {test_result}")

            await swapzone.close()


if __name__ == "__main__":
    try:
        # Основной режим
        asyncio.run(main())

        # Режим тестирования (раскомментируй если нужно)
        # asyncio.run(test_specific_exchange())

    except KeyboardInterrupt:
        print("\n⛔ Работа прервана пользователем.")
    except Exception as e:
        print(f"\n✗ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()