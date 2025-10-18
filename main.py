import asyncio
from datetime import datetime

from configs import (START_AMOUNT, MIN_SPREAD, SHOW_TOP, CHANGENOW_API_KEY)
from bybit_handler import BybitClientAsync
from changenow_handler import ChangeNowClientAsync
from exchange_arbitrage_analyzer import ExchangeArbitrageAnalyzer
from results_saver import ResultsSaver


async def main():
    print("=" * 100)
    print("🚀 CRYPTO ARBITRAGE BOT v4.0 — ОБМЕННИКИ")
    print("=" * 100)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок")
    print(f"\n🔍 Схема арбитража:")
    print(f"   USDT (Bybit) → CoinA (Bybit) → Обменник → CoinB (Bybit) → USDT (Bybit)\n")

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

        # ───────────────────────────────────────────────────────────────
        # ШАГ 2: Загрузка данных с обменника
        # ───────────────────────────────────────────────────────────────
        print("\n" + "=" * 100)
        print("📊 ШАГ 2: ЗАГРУЗКА ДАННЫХ С CHANGENOW")
        print("=" * 100)

        async with ChangeNowClientAsync(api_key=CHANGENOW_API_KEY) as changenow:
            await changenow.load_available_currencies()

            print(f"\n[ChangeNOW] ✓ Загружено {len(changenow.available_currencies)} валют")

            # Находим общие монеты
            common_coins = changenow.get_common_currencies(bybit.coins)

            if not common_coins:
                print("\n❌ Нет общих монет между Bybit и ChangeNOW. Анализ невозможен.")
                return

            # ───────────────────────────────────────────────────────────────
            # ШАГ 3: Поиск арбитражных связок (результаты выводятся сразу!)
            # ───────────────────────────────────────────────────────────────
            print("\n" + "=" * 100)
            print("🔍 ШАГ 3: ПОИСК АРБИТРАЖНЫХ СВЯЗОК")
            print("=" * 100)

            analyzer = ExchangeArbitrageAnalyzer(bybit, changenow)

            # Поиск с мгновенным выводом результатов
            opportunities = await analyzer.find_arbitrage_opportunities(
                start_amount=START_AMOUNT,
                min_spread=MIN_SPREAD,
                top_count=SHOW_TOP,
                max_pairs_to_check=100  # Можно увеличить до 200-500
            )

            # ───────────────────────────────────────────────────────────────
            # ШАГ 4: Сохранение результатов
            # ───────────────────────────────────────────────────────────────
            if opportunities:
                print("\n" + "=" * 100)
                print("💾 ШАГ 4: СОХРАНЕНИЕ РЕЗУЛЬТАТОВ АНАЛИЗА")
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
                # ШАГ 5: Финальная статистика
                # ───────────────────────────────────────────────────────────────
                print("\n" + "=" * 100)
                print("📈 ФИНАЛЬНАЯ СТАТИСТИКА")
                print("=" * 100)

                # Статистика по монетам
                coin_stats = {}
                for opp in opportunities:
                    for coin in opp['coins']:
                        if coin not in coin_stats:
                            coin_stats[coin] = {'count': 0, 'max_spread': 0, 'total_profit': 0}
                        coin_stats[coin]['count'] += 1
                        coin_stats[coin]['max_spread'] = max(coin_stats[coin]['max_spread'], opp['spread'])
                        coin_stats[coin]['total_profit'] += opp['profit']

                print(f"\n📊 Всего связок найдено: {len(opportunities)}")
                print(f"💰 Общая потенциальная прибыль: ${sum(opp['profit'] for opp in opportunities):.2f}")
                print(f"📈 Средний спред: {sum(opp['spread'] for opp in opportunities) / len(opportunities):.4f}%")
                print(f"🏆 Максимальный спред: {opportunities[0]['spread']:.4f}%")

                # Топ-5 самых популярных монет
                if coin_stats:
                    print("\n🔥 ТОП-5 самых популярных монет в связках:")
                    sorted_coins = sorted(coin_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
                    for idx, (coin, stats) in enumerate(sorted_coins, 1):
                        print(f"   {idx}. {coin}: {stats['count']} связок, макс. спред {stats['max_spread']:.4f}%")

                # Топ-5 самых прибыльных
                print("\n" + "=" * 100)
                print("🏆 ТОП-5 САМЫХ ПРИБЫЛЬНЫХ СВЯЗОК:")
                print("=" * 100 + "\n")

                for idx, opp in enumerate(opportunities[:5], 1):
                    print(f"#{idx} | {opp['path']}")
                    print(f"     Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                    print(f"     Монеты: {' → '.join(opp['coins'])}")
                    print(f"     Курсы:")
                    print(f"       • Bybit {opp['coins'][0]}/USDT: {opp['bybit_rate_a']:.8f}")
                    print(f"       • Обменник {opp['coins'][0]}/{opp['coins'][1]}: {opp['exchange_rate']:.8f}")
                    print(f"       • Bybit {opp['coins'][1]}/USDT: {opp['bybit_rate_b']:.8f}")
                    print()

            # Статистика по неудачным запросам
            failed_count = changenow.get_failed_pairs_count()
            if failed_count > 0:
                print(f"\n📊 Статистика обменника:")
                print(f"   • Недоступных пар: {failed_count} (добавлены в кэш, больше не запрашиваются)")

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
        print("     - Обмен на обменнике: 5-30 минут")
        print("     - Продажа на Bybit: мгновенно")
        print("   • Цены могут измениться за время выполнения связки!")
        print("   • Проверяйте минимальные суммы обмена на обменнике")
        print("   • Всегда делайте тестовый обмен с минимальной суммой!")


async def test_specific_pair():
    """
    Функция для тестирования конкретной пары монет
    Раскомментируй и используй для детальной проверки
    """
    print("=" * 100)
    print("🔬 ТЕСТ КОНКРЕТНОЙ ПАРЫ")
    print("=" * 100)

    async with BybitClientAsync() as bybit:
        await bybit.load_usdt_pairs()

        async with ChangeNowClientAsync(api_key=CHANGENOW_API_KEY) as changenow:
            await changenow.load_available_currencies()

            analyzer = ExchangeArbitrageAnalyzer(bybit, changenow)

            # Пример: проверка связки LTC → BNB
            result = await analyzer.analyze_specific_pair(
                coin_a='LTC',
                coin_b='BNB',
                start_amount=100.0
            )

            print(f"\n📊 Результат: {result}")


if __name__ == "__main__":
    try:
        # Основной режим - поиск всех связок
        asyncio.run(main())

        # Режим тестирования конкретной пары (раскомментируй если нужно)
        # asyncio.run(test_specific_pair())

    except KeyboardInterrupt:
        print("\n⛔ Работа прервана пользователем.")
    except Exception as e:
        print(f"\n✗ Критическая ошибка выполнения: {e}")
        import traceback
        traceback.print_exc()