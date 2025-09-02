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
        await self.api_client.close()
        self.logger.info("Арбитражный бот остановлен")

    async def run(self):
        await self.start()
        try:
            while not self.shutdown_event.is_set():
                try:
                    opportunities = await self.arbitrage_logic.scan_arbitrage_opportunities()
                    if opportunities:
                        self.logger.info(f"Найдено {len(opportunities)} арбитражных возможностей!")
                        for i, opportunity in enumerate(opportunities[:MAX_OPPORTUNITIES_DISPLAY], 1):
                            self.arbitrage_logic.print_opportunity(opportunity, i)
                            if ENABLE_LIVE_TRADING:
                                await self.trading_manager.execute_trade(opportunity)
                    else:
                        self.logger.debug("Прибыльных арбитражных возможностей не найдено")
                    await asyncio.sleep(SCAN_INTERVAL)
                except KeyboardInterrupt:
                    self.logger.info("Получен сигнал остановки (KeyboardInterrupt)...")
                    break
                except Exception as e:
                    self.logger.error(f"Ошибка в главном цикле: {e}")
                    await asyncio.sleep(ERROR_RETRY_INTERVAL)
        finally:
            await self.close()

def _setup_signal_handlers(loop, shutdown_event: asyncio.Event):
    try:
        loop.add_signal_handler(signal.SIGTERM, shutdown_event.set)
        loop.add_signal_handler(signal.SIGINT, shutdown_event.set)
    except NotImplementedError:
        # Windows compatibility fallback
        signal.signal(signal.SIGINT, lambda s, f: shutdown_event.set())

async def main():
    if not check_dependencies():
        sys.exit(1)
    print_startup_info()
    bot = BybitArbitrageBot()

    # Обработка сигналов завершения
    def handle_exit(signame):
        bot.shutdown_event.set()
        sys.exit(0)

    for signame in ('SIGINT', 'SIGTERM'):
        try:
            signal.signal(getattr(signal, signame), handle_exit)
        except AttributeError:
            pass  # Signal not available on this platform

    await bot.run()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
