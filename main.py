#!/usr/bin/env python3
"""
Арбитражный бот для Bybit - main.py
"""
import asyncio
import logging
import signal
import sys
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
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        setup_logging()
        self.logger = logging.getLogger(__name__)

    async def start(self):
        await self.api_client.start()
        self.logger.info("Арбитражный бот запущен")

    async def close(self):
        try:
            await self.api_client.close()
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии API клиента: {e}")
        self.logger.info("Арбитражный бот остановлен")

    async def run(self):
        await self.start()
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Основной цикл сканирования
                    opportunities = await self.arbitrage_logic.scan_arbitrage_opportunities()

                    # Сброс счетчика ошибок при успешном выполнении
                    self.consecutive_errors = 0

                    if opportunities:
                        self.logger.info(f"Найдено {len(opportunities)} арбитражных возможностей!")

                        displayed_count = 0
                        for i, opportunity in enumerate(opportunities, 1):
                            if displayed_count >= MAX_OPPORTUNITIES_DISPLAY:
                                self.logger.info(
                                    f"Показано {displayed_count} из {len(opportunities)} возможностей (лимит достигнут)")
                                break

                            try:
                                self.arbitrage_logic.print_opportunity(opportunity, i)
                                displayed_count += 1

                                # Попытка выполнить сделку
                                if ENABLE_LIVE_TRADING:
                                    success = await self.trading_manager.execute_trade(opportunity)
                                    if success:
                                        self.logger.info(f"✅ Сделка #{i} выполнена успешно")
                                    else:
                                        self.logger.debug(f"❌ Сделка #{i} не выполнена")

                            except Exception as e:
                                self.logger.error(f"Ошибка обработки возможности #{i}: {e}")
                                continue
                    else:
                        self.logger.debug("Прибыльных арбитражных возможностей не найдено")

                    # Ожидание перед следующим сканированием
                    try:
                        await asyncio.wait_for(
                            asyncio.sleep(SCAN_INTERVAL),
                            timeout=SCAN_INTERVAL + 5
                        )
                    except asyncio.TimeoutError:
                        self.logger.debug("Timeout в sleep, продолжаем")
                        pass

                except KeyboardInterrupt:
                    self.logger.info("Получен сигнал остановки (KeyboardInterrupt)...")
                    break

                except asyncio.CancelledError:
                    self.logger.info("Задача была отменена")
                    break

                except Exception as e:
                    self.consecutive_errors += 1
                    self.logger.error(f"Ошибка в главном цикле (#{self.consecutive_errors}): {e}")

                    # Если слишком много подряд идущих ошибок - делаем паузу подольше
                    if self.consecutive_errors >= self.max_consecutive_errors:
                        self.logger.warning(f"Много ошибок подряд ({self.consecutive_errors}), увеличиваем паузу")
                        await asyncio.sleep(ERROR_RETRY_INTERVAL * 5)
                        self.consecutive_errors = 0  # Сбрасываем счетчик
                    else:
                        await asyncio.sleep(ERROR_RETRY_INTERVAL)

        except Exception as e:
            self.logger.error(f"Критическая ошибка в run(): {e}", exc_info=True)
        finally:
            await self.close()


def _setup_signal_handlers(bot: BybitArbitrageBot):
    """Настройка обработчиков сигналов"""

    def signal_handler(signame):
        def handler(sig=None, frame=None):
            logging.info(f"Получен сигнал {signame}, остановка...")
            bot.shutdown_event.set()

        return handler

    try:
        # Пытаемся использовать loop.add_signal_handler (Unix)
        loop = asyncio.get_running_loop()
        if hasattr(signal, 'SIGTERM'):
            loop.add_signal_handler(signal.SIGTERM, signal_handler('SIGTERM'))
        if hasattr(signal, 'SIGINT'):
            loop.add_signal_handler(signal.SIGINT, signal_handler('SIGINT'))
    except (NotImplementedError, RuntimeError):
        # Windows compatibility fallback
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler('SIGINT'))
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler('SIGTERM'))


async def main():
    """Главная функция"""
    # Проверка зависимостей
    if not check_dependencies():
        sys.exit(1)

    # Вывод информации о запуске
    print_startup_info()

    # Создание бота
    bot = BybitArbitrageBot()

    # Настройка обработчиков сигналов
    _setup_signal_handlers(bot)

    try:
        # Запуск бота
        await bot.run()

    except KeyboardInterrupt:
        bot.logger.info("Получен KeyboardInterrupt, завершение работы...")

    except Exception as e:
        bot.logger.error(f"Критическая ошибка в main(): {e}", exc_info=True)

    finally:
        # Принудительное закрытие
        try:
            if not bot.api_client.session.closed:
                await bot.close()
        except Exception as e:
            logging.error(f"Ошибка при финальном закрытии: {e}")


if __name__ == "__main__":
    # Настройка политики событийного цикла для Windows
    if sys.platform.startswith('win'):
        try:
            # Python 3.8+
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError:
            # Старые версии Python
            pass

    try:
        # Запуск основного цикла
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\n🛑 Программа остановлена пользователем")

    except Exception as e:
        logging.error(f"Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)