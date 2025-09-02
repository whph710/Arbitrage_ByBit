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
                    # ИСПРАВЛЕНИЕ: Обернем в try-except для перехвата StopIteration
                    try:
                        opportunities = await self.arbitrage_logic.scan_arbitrage_opportunities()
                    except StopIteration:
                        self.logger.debug("StopIteration перехвачен в scan_arbitrage_opportunities")
                        opportunities = []
                    except RuntimeError as e:
                        if "StopIteration" in str(e):
                            self.logger.debug("RuntimeError со StopIteration перехвачен")
                            opportunities = []
                        else:
                            raise

                    if opportunities:
                        self.logger.info(f"Найдено {len(opportunities)} арбитражных возможностей!")
                        for i, opportunity in enumerate(opportunities[:MAX_OPPORTUNITIES_DISPLAY], 1):
                            try:
                                self.arbitrage_logic.print_opportunity(opportunity, i)
                                if ENABLE_LIVE_TRADING:
                                    await self.trading_manager.execute_trade(opportunity)
                            except (StopIteration, RuntimeError) as e:
                                if "StopIteration" in str(e):
                                    self.logger.debug(f"StopIteration в обработке возможности {i}")
                                    continue
                                else:
                                    raise
                    else:
                        self.logger.debug("Прибыльных арбитражных возможностей не найдено")

                    # Безопасный sleep с проверкой shutdown
                    try:
                        await asyncio.wait_for(
                            asyncio.sleep(SCAN_INTERVAL),
                            timeout=SCAN_INTERVAL + 1
                        )
                    except asyncio.TimeoutError:
                        pass

                except KeyboardInterrupt:
                    self.logger.info("Получен сигнал остановки (KeyboardInterrupt)...")
                    break
                except (StopIteration, RuntimeError) as e:
                    if "StopIteration" in str(e):
                        self.logger.warning(f"StopIteration в главном цикле: {e}")
                        continue
                    else:
                        self.logger.error(f"RuntimeError в главном цикле: {e}")
                        await asyncio.sleep(ERROR_RETRY_INTERVAL)
                except asyncio.CancelledError:
                    self.logger.info("Задача была отменена")
                    break
                except Exception as e:
                    self.logger.error(f"Ошибка в главном цикле: {e}", exc_info=True)
                    await asyncio.sleep(ERROR_RETRY_INTERVAL)
        finally:
            await self.close()


def _setup_signal_handlers(loop, shutdown_event: asyncio.Event):
    """Настройка обработчиков сигналов"""

    def signal_handler(signame):
        def handler():
            logging.info(f"Получен сигнал {signame}, остановка...")
            shutdown_event.set()

        return handler

    try:
        if hasattr(signal, 'SIGTERM'):
            loop.add_signal_handler(signal.SIGTERM, signal_handler('SIGTERM'))
        if hasattr(signal, 'SIGINT'):
            loop.add_signal_handler(signal.SIGINT, signal_handler('SIGINT'))
    except NotImplementedError:
        # Windows compatibility fallback
        def handle_exit(sig, frame):
            logging.info(f"Получен сигнал {sig}, остановка...")
            shutdown_event.set()

        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, handle_exit)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, handle_exit)


async def main():
    """Главная функция"""
    if not check_dependencies():
        sys.exit(1)

    print_startup_info()

    # Создание бота
    bot = BybitArbitrageBot()

    # Настройка обработчиков сигналов
    loop = asyncio.get_running_loop()
    _setup_signal_handlers(loop, bot.shutdown_event)

    try:
        # Запуск бота с обработкой исключений
        await bot.run()
    except KeyboardInterrupt:
        bot.logger.info("Получен KeyboardInterrupt, завершение работы...")
    except Exception as e:
        bot.logger.error(f"Критическая ошибка в main(): {e}", exc_info=True)
    finally:
        # Принудительное закрытие
        try:
            await bot.close()
        except Exception as e:
            logging.error(f"Ошибка при финальном закрытии: {e}")


if __name__ == "__main__":
    # Настройка политики событийного цикла для Windows
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        # Запуск основного цикла
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Программа остановлена пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)