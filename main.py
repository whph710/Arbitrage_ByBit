import asyncio
import time
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
    print("📦 Инициализация клиентов...\n")

    # ───────────────────────────────────────────────────────────────
    # ШАГ 1: Загрузка данных Bybit
    # ───────────────────────────────────────────────────────────────
    print("=" * 90)
    print("📊 ШАГ 1: ЗАГРУЗКА ДАННЫХ С BYBIT")
    print("=" * 90)

    async with BybitClientAsync() as bb:
        await bb.load_usdt_pairs()
        print(f"[Bybit] ✓ Загружено {len(bb.usdt_pairs)} разрешенных торговых пар USDT")
        print(f"[Bybit] ✓ Найденные монеты: {', '.join(sorted(bb.coins))}")
        print(f"✓ Получено {len(bb.usdt_pairs)} торговых пар USDT\n")

        # ───────────────────────────────────────────────────────────────
        # ШАГ 2: Инициализация BestChange
        # ───────────────────────────────────────────────────────────────
        print("=" * 90)
        print("📊 ШАГ 2: ИНИЦИАЛИЗАЦИЯ BESTCHANGE")
        print("=" * 90)

        async with BestChangeClientAsync() as bc:
            print("[BestChange] Загрузка данных через API v2.0...")
            await bc.load_currencies()
            await bc.load_exchangers()
            print(f"[BestChange] ✓ Валют загружено: {len(bc.currencies)}")
            print(f"[BestChange] ✓ Активных обменников: {len(bc.exchangers)}")

            # пересечение монет между Bybit и BestChange
            bestchange_tickers = {c["ticker"].upper() for c in bc.currencies.values() if "ticker" in c}
            common_tickers = list(set(bb.coins) & bestchange_tickers)
            print(f"✓ Найдено общих монет (пересечение): {len(common_tickers)}")

            # ───────────────────────────────────────────────────────────────
            # ШАГ 3: Загрузка курсов BestChange
            # ───────────────────────────────────────────────────────────────
            print("\n" + "=" * 90)
            print("📊 ШАГ 3: ЗАГРУЗКА КУРСОВ BESTCHANGE ДЛЯ ОБЩИХ МОНЕТ")
            print("=" * 90 + "\n")

            await bc.load_rates(common_tickers)
            print(f"[BestChange] ✓ Загружено направлений: {len(bc.rates)}\n")

            # ───────────────────────────────────────────────────────────────
            # ШАГ 4: Поиск арбитражных возможностей
            # ───────────────────────────────────────────────────────────────
            print("=" * 90)
            print("🔍 ШАГ 4: ПОИСК КРУГОВЫХ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
            print("=" * 90)

            analyzer = ArbitrageAnalyzerAsync(bb, bc)
            await analyzer.find_circular_opportunities(start_amount=START_AMOUNT, min_spread=MIN_SPREAD)

    # ───────────────────────────────────────────────────────────────
    # Завершение работы
    # ───────────────────────────────────────────────────────────────
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    print(f"\nРабота завершена — {end_time.strftime('%H:%M:%S')} (время выполнения: {elapsed:.2f} сек.)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Работа прервана пользователем.")
    except Exception as e:
        print(f"\n✗ Ошибка выполнения: {e}")
