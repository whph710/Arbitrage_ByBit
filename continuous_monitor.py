"""
Модуль непрерывного мониторинга арбитражных возможностей
Работает бесконечно, постоянно ищет связки и выводит их в консоль
"""

import asyncio
import signal
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from collections import deque
import traceback

from configs_continuous import (
    START_AMOUNT, MIN_SPREAD, MAX_REASONABLE_SPREAD,
    MONITORING_INTERVAL, MIN_PROFIT_USD
)
from bybit_handler import BybitClientAsync
from bestchange_handler import BestChangeClientAsync
from exchange_arbitrage_analyzer import ExchangeArbitrageAnalyzer
from opportunity_logger import OpportunityLogger


class ContinuousArbitrageMonitor:
    """
    Непрерывный монитор арбитражных возможностей
    Работает 24/7, автоматически восстанавливается после ошибок
    """

    def __init__(self):
        self.running = False
        self.bybit: Optional[BybitClientAsync] = None
        self.bestchange: Optional[BestChangeClientAsync] = None
        self.analyzer: Optional[ExchangeArbitrageAnalyzer] = None
        self.logger = OpportunityLogger()

        # Статистика
        self.total_iterations = 0
        self.total_opportunities_found = 0
        self.best_spread_ever = 0
        self.best_opportunity_ever = None
        self.start_time = None
        self.last_data_reload = None

        # История последних находок (для избежания дублирования)
        self.recent_opportunities = deque(maxlen=100)

        # Настройки
        self.data_reload_interval = timedelta(hours=1)  # Перезагружать данные каждый час
        self.min_time_between_same_opportunity = 60  # Не показывать одну и ту же связку чаще чем раз в 60 сек

        # Обработка сигналов для корректного завершения
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        print("\n\n🛑 Получен сигнал завершения. Останавливаем мониторинг...")
        self.running = False

    async def initialize(self):
        """Инициализация клиентов и загрузка данных"""
        print("=" * 100)
        print("🚀 ИНИЦИАЛИЗАЦИЯ НЕПРЕРЫВНОГО МОНИТОРИНГА АРБИТРАЖА")
        print("=" * 100)

        try:
            # Создаем клиенты
            self.bybit = BybitClientAsync()
            await self.bybit.create_session()

            self.bestchange = BestChangeClientAsync()
            await self.bestchange.create_session()

            # Загружаем данные Bybit
            print("\n[Init] 📥 Загрузка данных Bybit...")
            await self.bybit.load_usdt_pairs()

            if len(self.bybit.usdt_pairs) == 0:
                raise Exception("Не удалось загрузить торговые пары Bybit")

            print(f"[Init] ✅ Bybit: загружено {len(self.bybit.usdt_pairs)} USDT-пар")

            # Загружаем данные BestChange
            print("\n[Init] 📥 Загрузка данных BestChange...")
            await self.bestchange.load_currencies()
            await self.bestchange.load_exchangers()

            # Находим общие монеты
            common_coins = set(self.bybit.usdt_pairs.keys()) & set(self.bestchange.crypto_currencies.keys())
            print(f"[Init] ✅ Общих монет: {len(common_coins)}")

            if len(common_coins) == 0:
                raise Exception("Нет общих монет между Bybit и BestChange")

            # Загружаем курсы BestChange
            print("\n[Init] 📥 Загрузка курсов BestChange (может занять время)...")
            await self.bestchange.load_rates(list(common_coins), use_rankrate=True)

            # Создаем анализатор
            self.analyzer = ExchangeArbitrageAnalyzer(self.bybit, self.bestchange)

            self.last_data_reload = datetime.now()

            print("\n[Init] ✅ ИНИЦИАЛИЗАЦИЯ ЗАВЕРШЕНА")
            print("=" * 100)

            return True

        except Exception as e:
            print(f"\n[Init] ❌ ОШИБКА ИНИЦИАЛИЗАЦИИ: {e}")
            traceback.print_exc()
            return False

    async def reload_data_if_needed(self):
        """Перезагружает данные если прошло достаточно времени"""
        if not self.last_data_reload:
            return

        time_since_reload = datetime.now() - self.last_data_reload

        if time_since_reload >= self.data_reload_interval:
            print(f"\n{'=' * 100}")
            print(f"🔄 ПЕРЕЗАГРУЗКА ДАННЫХ (прошло {time_since_reload.seconds // 60} минут)")
            print(f"{'=' * 100}")

            try:
                # Перезагружаем Bybit
                print("[Reload] 📥 Обновление данных Bybit...")
                await self.bybit.load_usdt_pairs()

                # Перезагружаем BestChange
                print("[Reload] 📥 Обновление курсов BestChange...")
                common_coins = set(self.bybit.usdt_pairs.keys()) & set(self.bestchange.crypto_currencies.keys())
                await self.bestchange.load_rates(list(common_coins), use_rankrate=True)

                self.last_data_reload = datetime.now()
                print("[Reload] ✅ Данные обновлены")

            except Exception as e:
                print(f"[Reload] ⚠️  Ошибка перезагрузки данных: {e}")
                # Продолжаем работу со старыми данными

    def _is_duplicate_opportunity(self, opp: Dict) -> bool:
        """Проверяет, не является ли возможность дубликатом недавней"""
        path = opp['path']
        spread = opp['spread']

        current_time = datetime.now()

        for recent_opp, timestamp in self.recent_opportunities:
            # Если та же связка и прошло мало времени
            if recent_opp['path'] == path:
                time_diff = (current_time - timestamp).total_seconds()
                if time_diff < self.min_time_between_same_opportunity:
                    # Но если спред значительно изменился (>20%), то показываем
                    spread_diff = abs(spread - recent_opp['spread'])
                    if spread_diff < recent_opp['spread'] * 0.2:  # Изменение менее 20%
                        return True

        return False

    def _print_opportunity_instant(self, opp: Dict, rank: int):
        """Мгновенный вывод найденной возможности"""
        timestamp = datetime.now().strftime('%H:%M:%S')

        print(f"\n{'🎯' * 50}")
        print(f"⏰ {timestamp} | НАЙДЕНА СВЯЗКА #{self.total_opportunities_found}")
        print(f"{'─' * 100}")
        print(f"📍 Путь: {opp['path']}")
        print(f"💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
        print(f"💵 ${opp['initial']:.2f} → ${opp['final']:.2f}")
        print(f"🏦 Обменник: {opp['exchanger']} (резерв: ${opp['reserve']:,.0f})")

        coins = opp['coins']
        if len(coins) >= 2:
            liq_a = opp.get('liquidity_a', 0)
            liq_b = opp.get('liquidity_b', 0)
            print(f"💧 Ликвидность: {coins[0]} ({liq_a:.1f}) → {coins[1]} ({liq_b:.1f})")

        # Показываем курс обмена
        if 'exchange_rate' in opp:
            print(f"📊 Курс: 1 {coins[0]} = {opp['exchange_rate']:.8f} {coins[1]}")

        print(f"\n📋 ДЕТАЛИ ОПЕРАЦИЙ:")
        for step in opp['steps']:
            print(f"   {step}")

        print(f"{'🎯' * 50}\n")

        # Логируем в файл
        self.logger.log_opportunity(opp)

        # Обновляем лучшую находку
        if opp['spread'] > self.best_spread_ever:
            self.best_spread_ever = opp['spread']
            self.best_opportunity_ever = opp
            print(f"🏆 НОВЫЙ РЕКОРД! Лучший спред за всё время: {self.best_spread_ever:.4f}%\n")
            self.logger.log_text(f"🏆 НОВЫЙ РЕКОРД: {self.best_spread_ever:.4f}% - {opp['path']}")

    async def run_single_iteration(self):
        """Выполняет одну итерацию поиска"""
        try:
            # Перезагружаем данные если нужно
            await self.reload_data_if_needed()

            # Быстрый поиск возможностей
            opportunities = await self.analyzer.find_opportunities(
                start_amount=START_AMOUNT,
                min_spread=MIN_SPREAD,
                max_spread=MAX_REASONABLE_SPREAD,
                min_reserve=0,
                parallel_requests=500
            )

            # Обрабатываем найденные возможности
            new_opportunities = 0

            for opp in opportunities:
                # Пропускаем дубликаты
                if self._is_duplicate_opportunity(opp):
                    continue

                # Добавляем в историю
                self.recent_opportunities.append((opp, datetime.now()))

                # Выводим сразу
                self.total_opportunities_found += 1
                new_opportunities += 1
                self._print_opportunity_instant(opp, self.total_opportunities_found)

            # Краткая статистика итерации
            if new_opportunities == 0:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] 🔍 Итерация #{self.total_iterations}: новых связок не найдено")

            return len(opportunities)

        except Exception as e:
            print(f"\n❌ Ошибка в итерации: {e}")
            traceback.print_exc()
            return 0

    def _print_session_statistics(self):
        """Выводит статистику сессии"""
        if not self.start_time:
            return

        # Используем статистику из логгера
        self.logger.print_session_summary()

    async def start_monitoring(self):
        """Запускает непрерывный мониторинг"""
        self.running = True
        self.start_time = datetime.now()

        print(f"\n{'=' * 100}")
        print(f"🔴 ЗАПУСК НЕПРЕРЫВНОГО МОНИТОРИНГА")
        print(f"{'=' * 100}")
        print(f"⏰ Старт: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  Интервал проверки: {MONITORING_INTERVAL}с")
        print(f"💰 Начальная сумма: ${START_AMOUNT}")
        print(f"📊 Минимальный спред: {MIN_SPREAD}%")
        print(f"💵 Минимальная прибыль: ${MIN_PROFIT_USD}")
        print(f"🔄 Перезагрузка данных: каждые {self.data_reload_interval.seconds // 3600}ч")
        print(f"⌨️  Нажмите Ctrl+C для остановки")
        print(f"{'=' * 100}\n")

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            self.total_iterations += 1

            try:
                print(f"\n{'─' * 100}")
                print(f"🔄 ИТЕРАЦИЯ #{self.total_iterations} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'─' * 100}")

                # Выполняем поиск
                await self.run_single_iteration()

                # Сбрасываем счетчик ошибок при успехе
                consecutive_errors = 0

                # Показываем статистику каждые 10 итераций
                if self.total_iterations % 10 == 0:
                    self._print_session_statistics()

                # Ждем до следующей итерации
                if self.running:
                    print(f"\n⏳ Следующая проверка через {MONITORING_INTERVAL}с...")
                    await asyncio.sleep(MONITORING_INTERVAL)

            except Exception as e:
                consecutive_errors += 1
                print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА В ИТЕРАЦИИ #{self.total_iterations}: {e}")
                traceback.print_exc()

                if consecutive_errors >= max_consecutive_errors:
                    print(f"\n⛔ СЛИШКОМ МНОГО ПОСЛЕДОВАТЕЛЬНЫХ ОШИБОК ({consecutive_errors})")
                    print(f"⚠️  Пытаемся переинициализировать систему...")

                    # Закрываем старые соединения
                    try:
                        if self.bybit:
                            await self.bybit.close()
                        if self.bestchange:
                            await self.bestchange.close()
                    except:
                        pass

                    # Пытаемся переинициализировать
                    if await self.initialize():
                        consecutive_errors = 0
                        print("✅ Переинициализация успешна")
                    else:
                        print("❌ Переинициализация не удалась. Останавливаем мониторинг.")
                        self.running = False
                        break
                else:
                    print(f"⏳ Ждем 30 секунд перед следующей попыткой...")
                    await asyncio.sleep(30)

    async def stop_monitoring(self):
        """Останавливает мониторинг и закрывает соединения"""
        self.running = False

        print(f"\n{'=' * 100}")
        print(f"⛔ ОСТАНОВКА МОНИТОРИНГА")
        print(f"{'=' * 100}")

        # Финальная статистика
        self._print_session_statistics()

        # Сохраняем дневную статистику
        self.logger.save_daily_summary()

        # Закрываем соединения
        try:
            if self.bybit:
                await self.bybit.close()
            if self.bestchange:
                await self.bestchange.close()
            print("\n✅ Все соединения закрыты")
        except Exception as e:
            print(f"\n⚠️  Ошибка при закрытии соединений: {e}")


async def main():
    """Главная функция для запуска непрерывного мониторинга"""
    monitor = ContinuousArbitrageMonitor()

    try:
        # Инициализация
        if not await monitor.initialize():
            print("\n❌ Не удалось инициализировать мониторинг")
            return

        # Запуск мониторинга
        await monitor.start_monitoring()

    except KeyboardInterrupt:
        print("\n\n⌨️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        traceback.print_exc()
    finally:
        # Корректное завершение
        await monitor.stop_monitoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Программа завершена")