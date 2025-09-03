#!/usr/bin/env python3
"""
Арбитражный бот для Bybit - main.py
ИСПРАВЛЕННАЯ И ОПТИМИЗИРОВАННАЯ ВЕРСИЯ
"""
import asyncio
import logging
import signal
import sys
import time
from pathlib import Path
from config import *
from csv_manager import CSVManager
from api_client import BybitAPIClient
from arbitrage_logic import ArbitrageLogic
from utils import setup_logging, print_startup_info, check_dependencies
from trading import TradingManager


class BybitArbitrageBot:
    def __init__(self):
        self.api_client = BybitAPIClient()
        self.csv_manager = CSVManager()
        self.arbitrage_logic = ArbitrageLogic(self.api_client, self.csv_manager)
        self.trading_manager = TradingManager(self.api_client, self.csv_manager)
        self.shutdown_event = asyncio.Event()

        # Статистика и мониторинг
        self.consecutive_errors = 0
        self.max_consecutive_errors = 10
        self.total_scans = 0
        self.total_opportunities_found = 0
        self.scan_times = []
        self.start_time = time.time()

        setup_logging()
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Запускает бота"""
        try:
            await self.api_client.start()
            self.logger.info("🚀 Арбитражный бот успешно запущен")

            # Проверяем подключение к API
            if not await self._test_api_connection():
                self.logger.error("❌ Не удалось подключиться к API Bybit")
                return False

            return True
        except Exception as e:
            self.logger.error(f"Ошибка запуска бота: {e}")
            return False

    async def _test_api_connection(self):
        """Тестирует подключение к API"""
        try:
            self.logger.info("🔍 Тестируем подключение к API...")
            tickers = await self.api_client.get_tickers()
            if tickers and len(tickers) > 0:
                self.logger.info(f"✅ API подключение успешно. Доступно {len(tickers)} торговых пар")
                return True
            else:
                self.logger.error("❌ API вернуло пустой список тикеров")
                return False
        except Exception as e:
            self.logger.error(f"❌ Ошибка тестирования API: {e}")
            return False

    async def _print_final_stats(self):
        """Выводит финальную статистику"""
        uptime = time.time() - self.start_time
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)

        avg_scan_time = sum(self.scan_times) / len(self.scan_times) if self.scan_times else 0

        self.logger.info("=" * 70)
        self.logger.info("📊 ФИНАЛЬНАЯ СТАТИСТИКА СЕССИИ")
        self.logger.info("=" * 70)
        self.logger.info(f"⏱️  Время работы: {int(hours)}ч {int(minutes)}м {int(seconds)}с")
        self.logger.info(f"🔄 Всего сканирований: {self.total_scans}")
        self.logger.info(f"💎 Найдено возможностей: {self.total_opportunities_found}")
        self.logger.info(f"📈 Среднее время сканирования: {avg_scan_time:.2f}с")
        self.logger.info(f"🎯 Сохранено в CSV: {self.csv_manager.get_opportunities_count()}")

        # Статистика торговли
        try:
            trading_stats = await self.trading_manager.get_trading_stats()
            if trading_stats['session_trades'] > 0:
                self.logger.info(f"💰 Выполнено сделок: {trading_stats['session_trades']}")
                self.logger.info(f"💵 Прибыль сессии: ${trading_stats['session_profit']:.2f}")
        except Exception as e:
            self.logger.debug(f"Ошибка получения торговой статистики: {e}")

        self.logger.info("=" * 70)

    async def close(self):
        """Закрывает бота"""
        try:
            self.logger.info("🛑 Останавливаем бота...")
            await self.api_client.close()
            await self._print_final_stats()
            self.logger.info("✅ Арбитражный бот остановлен")
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии бота: {e}")

    async def run(self):
        """Главный цикл работы бота"""
        if not await self.start():
            return

        try:
            # Показываем агрессивные настройки если доступны
            try:
                from config import print_aggressive_mode_warning
                print_aggressive_mode_warning()
            except (ImportError, AttributeError):
                self.logger.debug("Функция агрессивных настроек недоступна")

            while not self.shutdown_event.is_set():
                try:
                    scan_start_time = time.time()

                    # Основное сканирование
                    opportunities = await self.arbitrage_logic.scan_arbitrage_opportunities()

                    scan_duration = time.time() - scan_start_time
                    self.scan_times.append(scan_duration)
                    self.total_scans += 1

                    # Ограничиваем список времен сканирования (последние 100)
                    if len(self.scan_times) > 100:
                        self.scan_times = self.scan_times[-100:]

                    # Сброс счетчика ошибок при успешном сканировании
                    self.consecutive_errors = 0

                    if opportunities:
                        opportunities_count = len(opportunities)
                        self.total_opportunities_found += opportunities_count

                        self.logger.info(
                            f"🎯 Найдено {opportunities_count} арбитражных возможностей! (скан: {scan_duration:.2f}с)")

                        # Показываем найденные возможности
                        displayed_count = 0
                        successful_trades = 0

                        for i, opportunity in enumerate(opportunities, 1):
                            if displayed_count >= MAX_OPPORTUNITIES_DISPLAY:
                                self.logger.info(f"📊 Показано {displayed_count} из {opportunities_count} возможностей")
                                break

                            try:
                                # Показываем возможность
                                self.arbitrage_logic.print_opportunity(opportunity, i)
                                displayed_count += 1

                                # Попытка торговли
                                if ENABLE_LIVE_TRADING:
                                    trade_success = await self.trading_manager.execute_trade(opportunity)
                                    if trade_success:
                                        successful_trades += 1
                                        self.logger.info(f"✅ Сделка #{i} выполнена успешно")
                                    else:
                                        self.logger.debug(f"⏭️  Сделка #{i} пропущена")

                            except Exception as e:
                                self.logger.error(f"Ошибка обработки возможности #{i}: {e}")
                                continue

                        # Сводка по торговле
                        if ENABLE_LIVE_TRADING and successful_trades > 0:
                            self.logger.info(
                                f"💰 Успешных сделок в этом цикле: {successful_trades}/{opportunities_count}")

                    else:
                        # Более информативное сообщение когда нет возможностей
                        if self.total_scans % 20 == 0:  # Каждые 20 сканирований
                            self.logger.info(
                                f"🔍 Сканирование #{self.total_scans}: возможностей не найдено (время: {scan_duration:.2f}с)")
                        else:
                            self.logger.debug(f"Сканирование #{self.total_scans}: нет возможностей")

                    # Пауза перед следующим сканированием
                    try:
                        await asyncio.wait_for(
                            self.shutdown_event.wait(),
                            timeout=SCAN_INTERVAL
                        )
                        # Если дождались события - выходим
                        if self.shutdown_event.is_set():
                            break
                    except asyncio.TimeoutError:
                        # Таймаут - это нормально, продолжаем сканирование
                        pass

                except KeyboardInterrupt:
                    self.logger.info("⌨️  Получен сигнал остановки от пользователя...")
                    break

                except asyncio.CancelledError:
                    self.logger.info("🔄 Задача отменена")
                    break

                except Exception as e:
                    self.consecutive_errors += 1
                    error_msg = f"Ошибка в главном цикле (#{self.consecutive_errors}): {e}"

                    if self.consecutive_errors <= 3:
                        self.logger.error(error_msg)
                    else:
                        self.logger.warning(error_msg)  # Не спамим в логи

                    # Прогрессивное увеличение задержки при ошибках
                    if self.consecutive_errors >= self.max_consecutive_errors:
                        self.logger.warning(f"🚨 Критическое количество ошибок ({self.consecutive_errors})")
                        self.logger.warning("⏸️  Увеличиваем паузу и сбрасываем счетчик...")
                        await asyncio.sleep(ERROR_RETRY_INTERVAL * 10)
                        self.consecutive_errors = 0
                    elif self.consecutive_errors >= 5:
                        await asyncio.sleep(ERROR_RETRY_INTERVAL * 3)
                    else:
                        await asyncio.sleep(ERROR_RETRY_INTERVAL)

        except Exception as e:
            self.logger.error(f"💥 Критическая ошибка в run(): {e}", exc_info=True)
        finally:
            await self.close()


def _setup_signal_handlers(bot: BybitArbitrageBot):
    """Настройка обработчиков сигналов"""

    def signal_handler(signame):
        def handler(sig=None, frame=None):
            logging.info(f"📡 Получен сигнал {signame}, инициализация остановки...")
            bot.shutdown_event.set()

        return handler

    try:
        # Unix системы
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler('SIGTERM'))
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler('SIGINT'))

        # Дополнительные сигналы для Unix
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler('SIGHUP'))

        logging.debug("✅ Обработчики сигналов настроены (Unix)")

    except (NotImplementedError, AttributeError, OSError):
        # Windows compatibility fallback
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler('SIGINT'))
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler('SIGBREAK'))

        logging.debug("✅ Обработчики сигналов настроены (Windows)")


async def main():
    """Главная функция"""
    print("🚀 Запуск арбитражного бота Bybit...")

    # Проверка зависимостей
    if not check_dependencies():
        print("❌ Не все зависимости установлены")
        sys.exit(1)

    # Вывод информации о запуске
    print_startup_info()

    # Проверка агрессивных настроек
    try:
        from config import print_aggressive_mode_warning
        print_aggressive_mode_warning()
    except (ImportError, AttributeError):
        pass  # Функция недоступна

    # Создание бота
    bot = BybitArbitrageBot()

    # Настройка обработчиков сигналов
    _setup_signal_handlers(bot)

    try:
        # Запуск бота
        print("🎯 Начинаем поиск арбитражных возможностей...")
        await bot.run()

    except KeyboardInterrupt:
        bot.logger.info("⌨️  KeyboardInterrupt: завершение работы по требованию пользователя")

    except Exception as e:
        bot.logger.error(f"💥 Критическая ошибка в main(): {e}", exc_info=True)
        print(f"❌ Критическая ошибка: {e}")

    finally:
        # Принудительное закрытие при необходимости
        try:
            if hasattr(bot, 'api_client') and bot.api_client.session and not bot.api_client.session.closed:
                await bot.close()
        except Exception as e:
            logging.error(f"Ошибка финального закрытия: {e}")

        print("👋 Арбитражный бот завершил работу")


if __name__ == "__main__":
    # Настройка политики событийного цикла для Windows
    if sys.platform.startswith('win'):
        try:
            # Python 3.8+
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError:
            # Старые версии Python
            pass

    # Проверка версии Python
    if sys.version_info < (3, 7):
        print("❌ Требуется Python 3.7 или выше")
        sys.exit(1)

    try:
        # Запуск основного цикла
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\n🛑 Программа остановлена пользователем")

    except Exception as e:
        logging.error(f"💥 Критическая ошибка при запуске: {e}", exc_info=True)
        print(f"❌ Критическая ошибка при запуске: {e}")
        sys.exit(1)