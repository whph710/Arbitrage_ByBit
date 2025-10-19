import asyncio
from datetime import datetime
from configs import (
    START_AMOUNT, MIN_SPREAD, SHOW_TOP, MAX_REASONABLE_SPREAD,
    BESTCHANGE_API_KEY, WEBSOCKET_ENABLED, MONITORING_MODE,
    MONITORING_INTERVAL, AUTO_ALERT_THRESHOLD
)
from bybit_handler import BybitClientAsync
from bestchange_handler import BestChangeClientAsync
from exchange_arbitrage_analyzer import ExchangeArbitrageAnalyzer
from results_saver import ResultsSaver


class ArbitrageMonitor:
    """Монитор арбитража в реальном времени"""

    def __init__(self, bybit_client, bestchange_client, analyzer):
        self.bybit = bybit_client
        self.bestchange = bestchange_client
        self.analyzer = analyzer
        self.running = False
        self.best_opportunities = []
        self.alert_count = 0

    async def start_monitoring(self):
        """Запускает мониторинг в реальном времени"""
        self.running = True
        print(f"\n{'='*100}")
        print("🔴 РЕЖИМ МОНИТОРИНГА В РЕАЛЬНОМ ВРЕМЕНИ")
        print(f"{'='*100}")
        print(f"⏱️  Интервал проверки: {MONITORING_INTERVAL}с")
        print(f"🔔 Автоуведомления при спреде > {AUTO_ALERT_THRESHOLD}%")
        print(f"⌨️  Нажмите Ctrl+C для остановки\n")

        iteration = 0

        while self.running:
            iteration += 1
            print(f"\n{'─'*100}")
            print(f"🔄 ИТЕРАЦИЯ #{iteration} | {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'─'*100}")

            try:
                # Быстрый поиск возможностей
                opportunities = await self.analyzer.find_opportunities(
                    start_amount=START_AMOUNT,
                    min_spread=MIN_SPREAD,
                    max_spread=MAX_REASONABLE_SPREAD,
                    min_reserve=0,
                    parallel_requests=500
                )

                # Проверяем на алерты
                if opportunities:
                    top_opp = opportunities[0]
                    if top_opp['spread'] >= AUTO_ALERT_THRESHOLD:
                        self.alert_count += 1
                        print(f"\n{'🔔'*50}")
                        print(f"🚨 АЛЕРТ #{self.alert_count}: ВЫСОКИЙ СПРЕД {top_opp['spread']:.4f}% 🚨")
                        print(f"   Путь: {top_opp['path']}")
                        print(f"   Прибыль: ${top_opp['profit']:.4f}")
                        print(f"   Обменник: {top_opp['exchanger']}")
                        print(f"{'🔔'*50}\n")

                    # Обновляем лучшие
                    self.best_opportunities = opportunities[:5]

                # Показываем статистику WebSocket
                if WEBSOCKET_ENABLED:
                    ws_stats = self.bybit.get_ws_statistics()
                    print(f"\n📡 WebSocket: {ws_stats['updates_count']} обновлений | "
                          f"{ws_stats['last_updates']} пар активны")

                # Показываем статистику кэша
                cache_stats = self.analyzer.get_pair_statistics()
                print(f"🔥 Горячих пар: {cache_stats['hot_pairs_cached']} | "
                      f"Всего проверено: {cache_stats['total_pairs_checked']}")

            except Exception as e:
                print(f"❌ Ошибка в итерации: {e}")

            # Ждём до следующей проверки
            print(f"\n⏳ Следующая проверка через {MONITORING_INTERVAL}с...")
            await asyncio.sleep(MONITORING_INTERVAL)

    def stop_monitoring(self):
        """Останавливает мониторинг"""
        self.running = False
        print(f"\n{'='*100}")
        print("⛔ МОНИТОРИНГ ОСТАНОВЛЕН")
        print(f"{'='*100}")
        print(f"Всего алертов: {self.alert_count}")

        if self.best_opportunities:
            print(f"\n🏆 ЛУЧШИЕ ВОЗМОЖНОСТИ ЗА СЕССИЮ:")
            for idx, opp in enumerate(self.best_opportunities, 1):
                print(f"   {idx}. {opp['path']}: {opp['spread']:.4f}% (${opp['profit']:.4f})")


async def main():
    """Главная функция с оптимизированным алгоритмом"""
    print("=" * 100)
    print("🚀 CRYPTO ARBITRAGE BOT v8.0 — ОПТИМИЗИРОВАННЫЙ АНАЛИЗ")
    print("=" * 100)

    start_time = datetime.now()
    print(f"⏰ Время запуска: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"🎯 Показывать топ: {SHOW_TOP} связок")

    print(f"\n🔍 Тип арбитража:")
    print(f"   🔀 ЧЕРЕЗ ОБМЕННИКИ: Bybit → BestChange → Bybit (5 шагов)")
    print(f"\n⚡ ОПТИМИЗАЦИИ:")
    print(f"   ✓ WebSocket для обновления цен в реальном времени")
    print(f"   ✓ Массивная параллелизация (до 500 запросов)")
    print(f"   ✓ Кэширование горячих пар")
    print(f"   ✓ Фильтрация по ликвидности\n")

    all_opportunities = []

    # ========================================================================
    # ШАГ 1: ЗАГРУЗКА ДАННЫХ С BYBIT
    # ========================================================================
    print("=" * 100)
    print("📊 ШАГ 1: ЗАГРУЗКА ДАННЫХ С BYBIT")
    print("=" * 100)

    async with BybitClientAsync() as bybit:
        # Загружаем пары
        await bybit.load_usdt_pairs()

        if len(bybit.usdt_pairs) == 0:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: Не загружены торговые пары!")
            return

        # Запускаем WebSocket если включено
        ws_task = None
        if WEBSOCKET_ENABLED:
            print(f"\n{'='*100}")
            print("📡 ЗАПУСК WEBSOCKET ДЛЯ РЕАЛЬНОГО ВРЕМЕНИ")
            print(f"{'='*100}")
            ws_task = asyncio.create_task(bybit.start_websocket())
            await asyncio.sleep(2)  # Даём время на подключение

        # ====================================================================
        # ШАГ 2: ЗАГРУЗКА ДАННЫХ С BESTCHANGE
        # ====================================================================
        if not BESTCHANGE_API_KEY:
            print("\n" + "=" * 100)
            print("⚠️  BESTCHANGE API KEY НЕ ЗАДАН")
            print("=" * 100)
            print("Для включения анализа:")
            print("1. Получите API ключ на https://www.bestchange.com/wiki/api.html")
            print("2. Добавьте в .env файл: BESTCHANGE_API_KEY=ваш_ключ")
            return

        print("\n" + "=" * 100)
        print("📊 ШАГ 2: ЗАГРУЗКА ДАННЫХ С BESTCHANGE")
        print("=" * 100)

        try:
            async with BestChangeClientAsync() as bestchange:
                # Загрузка валют и обменников
                await bestchange.load_currencies()
                await bestchange.load_exchangers()

                # Находим общие монеты
                common_coins = set(bybit.usdt_pairs.keys()) & set(bestchange.crypto_currencies.keys())
                print(f"\n[BestChange] ✓ Общих монет с Bybit: {len(common_coins)}")

                if len(common_coins) == 0:
                    print(f"\n[BestChange] ❌ Нет общих монет для арбитража")
                    return

                # Загружаем курсы
                await bestchange.load_rates(list(common_coins), use_rankrate=True)

                # ============================================================
                # ШАГ 3: ПОИСК АРБИТРАЖА
                # ============================================================
                print("\n" + "=" * 100)
                print("📊 ШАГ 3: ПОИСК АРБИТРАЖА ЧЕРЕЗ ОБМЕННИКИ")
                print("=" * 100)

                exchange_analyzer = ExchangeArbitrageAnalyzer(bybit, bestchange)

                # Режим мониторинга или одноразовый анализ
                if MONITORING_MODE:
                    monitor = ArbitrageMonitor(bybit, bestchange, exchange_analyzer)
                    try:
                        await monitor.start_monitoring()
                    except KeyboardInterrupt:
                        monitor.stop_monitoring()
                else:
                    # Одноразовый анализ
                    exchange_opps = await exchange_analyzer.find_opportunities(
                        start_amount=START_AMOUNT,
                        min_spread=MIN_SPREAD,
                        max_spread=MAX_REASONABLE_SPREAD,
                        min_reserve=0,
                        parallel_requests=500
                    )

                    all_opportunities.extend(exchange_opps)
                    print(f"\n[BestChange Arbitrage] ✅ Найдено {len(exchange_opps)} связок")

                    # ========================================================
                    # ИТОГОВЫЕ РЕЗУЛЬТАТЫ
                    # ========================================================
                    if all_opportunities:
                        all_opportunities.sort(key=lambda x: x['profit'], reverse=True)

                        print("\n" + "=" * 100)
                        print("📈 ИТОГОВАЯ СТАТИСТИКА")
                        print("=" * 100)

                        print(f"\n📊 Всего найдено: {len(all_opportunities)} связок")

                        # Статистика по обменникам
                        exchangers_stats = {}
                        for opp in all_opportunities:
                            ex = opp.get('exchanger', 'Unknown')
                            if ex not in exchangers_stats:
                                exchangers_stats[ex] = {'count': 0, 'total_profit': 0, 'max_spread': 0}
                            exchangers_stats[ex]['count'] += 1
                            exchangers_stats[ex]['total_profit'] += opp['profit']
                            exchangers_stats[ex]['max_spread'] = max(exchangers_stats[ex]['max_spread'], opp['spread'])

                        print(f"\n📊 Топ-5 обменников:")
                        sorted_ex = sorted(exchangers_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
                        for ex, stats in sorted_ex:
                            print(f"   {ex}: {stats['count']} связок, макс. спред {stats['max_spread']:.4f}%")

                        print(f"\n🏆 ТОП-{min(SHOW_TOP, len(all_opportunities))} ЛУЧШИХ:")
                        print("=" * 100)

                        for idx, opp in enumerate(all_opportunities[:SHOW_TOP], 1):
                            print(f"\n#{idx} 🔀 | {opp['path']}")
                            print(f"   💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
                            print(f"   💵 ${opp['initial']:.2f} → ${opp['final']:.2f}")
                            print(f"   🏦 Обменник: {opp.get('exchanger', 'N/A')} (резерв: ${opp.get('reserve', 0):,.0f})")
                            print(f"   💧 Ликвидность: {opp['coins'][0]} ({opp['liquidity_a']:.1f}) → {opp['coins'][1]} ({opp['liquidity_b']:.1f})")

                        # ============================================
                        # СОХРАНЕНИЕ РЕЗУЛЬТАТОВ
                        # ============================================
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

                        # Статистика кэша
                        cache_stats = exchange_analyzer.get_pair_statistics()
                        if cache_stats['hot_pairs_cached'] > 0:
                            print(f"\n🔥 СТАТИСТИКА КЭША:")
                            print(f"   Горячих пар: {cache_stats['hot_pairs_cached']}")
                            print(f"   Топ-3 перформеры:")
                            for perf in cache_stats['top_performers'][:3]:
                                print(f"      • {perf['pair']}: {perf['success_rate']:.1f}% успех, "
                                      f"ср. спред {perf['avg_spread']:.4f}%")

                    else:
                        print(f"\n❌ Арбитражных связок не найдено")

        except Exception as e:
            print(f"\n[BestChange] ❌ Ошибка при работе с BestChange: {e}")
            print(f"[BestChange] ⚠️  Продолжаем без анализа обменников")
            import traceback
            traceback.print_exc()

        # Останавливаем WebSocket
        if ws_task:
            print(f"\n{'='*100}")
            print("🔌 ОСТАНОВКА WEBSOCKET")
            print(f"{'='*100}")
            await bybit.close()
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass

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