import asyncio
from datetime import datetime

from configs import START_AMOUNT, MIN_SPREAD, SHOW_TOP
from bybit_handler import BybitClientAsync
from bestchange_handler import BestChangeClientAsync
from arbitrage_analyzer import ArbitrageAnalyzerAsync


async def main():
    print("=" * 90)
    print("🚀 CRYPTO ARBITRAGE BOT (ASYNC VERSION) — CIRCULAR MODE")
    print("=" * 90)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок\n")

    # ───────────────────────────────────────────────────────────────
    # ШАГ 1: Загрузка данных Bybit
    # ───────────────────────────────────────────────────────────────
    print("=" * 90)
    print("📊 ШАГ 1: ЗАГРУЗКА ДАННЫХ С BYBIT")
    print("=" * 90)

    async with BybitClientAsync() as bb:
        await bb.load_usdt_pairs()
        print(f"[Bybit] ✓ Загружено {len(bb.usdt_pairs)} торговых пар USDT")

        # Показываем первые 20 монет для примера
        coins_preview = ', '.join(sorted(list(bb.coins)[:20]))
        more_coins = f" и еще {len(bb.coins) - 20}" if len(bb.coins) > 20 else ""
        print(f"[Bybit] ✓ Найденные монеты ({len(bb.coins)}): {coins_preview}{more_coins}")

        # ───────────────────────────────────────────────────────────────
        # ШАГ 2: Инициализация BestChange
        # ───────────────────────────────────────────────────────────────
        print("\n" + "=" * 90)
        print("📊 ШАГ 2: ИНИЦИАЛИЗАЦИЯ BESTCHANGE API v2.0")
        print("=" * 90)

        async with BestChangeClientAsync() as bc:
            print("[BestChange] Загрузка валют...")
            await bc.load_currencies()
            print(f"[BestChange] ✓ Всего валют: {len(bc.currencies)}")
            print(f"[BestChange] ✓ Криптовалют: {len(bc.crypto_currencies)}")

            # Показываем примеры криптовалют
            crypto_preview = ', '.join(sorted(list(bc.crypto_currencies.keys())[:20]))
            more_crypto = f" и еще {len(bc.crypto_currencies) - 20}" if len(bc.crypto_currencies) > 20 else ""
            print(f"[BestChange]   Примеры: {crypto_preview}{more_crypto}")

            print("[BestChange] Загрузка обменников...")
            await bc.load_exchangers()
            print(f"[BestChange] ✓ Активных обменников: {len(bc.changers)}")

            # Пересечение монет между Bybit и BestChange
            common_tickers = list(bb.coins & set(bc.crypto_currencies.keys()))
            print(f"\n[Analysis] ✓ Найдено общих монет: {len(common_tickers)}")

            if common_tickers:
                common_preview = ', '.join(sorted(common_tickers[:20]))
                more_common = f" и еще {len(common_tickers) - 20}" if len(common_tickers) > 20 else ""
                print(f"[Analysis]   Общие монеты: {common_preview}{more_common}")

            if not common_tickers:
                print("\n❌ Нет общих монет между Bybit и BestChange. Проверьте данные.")
                return

            # ───────────────────────────────────────────────────────────────
            # ШАГ 3: Загрузка курсов BestChange
            # ───────────────────────────────────────────────────────────────
            print("\n" + "=" * 90)
            print("📊 ШАГ 3: ЗАГРУЗКА КУРСОВ BESTCHANGE (BATCH MODE)")
            print("=" * 90)
            print(f"[BestChange] Загрузка курсов для {len(common_tickers)} монет...")
            print("[BestChange] Используется пакетная загрузка (до 100 пар за запрос)")

            await bc.load_rates(common_tickers)

            # Подсчитываем статистику
            total_directions = sum(len(pairs) for pairs in bc.rates.values())
            print(f"[BestChange] ✓ Загружено направлений обмена: {total_directions}")
            print(f"[BestChange] ✓ Валют с доступными курсами: {len(bc.rates)}")

            # ───────────────────────────────────────────────────────────────
            # ШАГ 4: Поиск арбитражных возможностей
            # ───────────────────────────────────────────────────────────────
            print("\n" + "=" * 90)
            print("🔍 ШАГ 4: ПОИСК КРУГОВЫХ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
            print("=" * 90 + "\n")

            analyzer = ArbitrageAnalyzerAsync(bb, bc)
            opportunities = await analyzer.find_circular_opportunities(
                start_amount=START_AMOUNT,
                min_spread=MIN_SPREAD,
                top_count=SHOW_TOP
            )

    # ───────────────────────────────────────────────────────────────
    # Завершение работы
    # ───────────────────────────────────────────────────────────────
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("\n" + "=" * 90)
    print(f"✅ Работа завершена — {end_time.strftime('%H:%M:%S')}")
    print(f"⏱️  Время выполнения: {elapsed:.2f} сек.")
    print("=" * 90)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Работа прервана пользователем.")
    except Exception as e:
        print(f"\n✗ Критическая ошибка выполнения: {e}")
        import traceback

        traceback.print_exc()