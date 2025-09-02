import logging
from models import ArbitrageOpportunity
from api_client import BybitAPIClient
from csv_manager import CSVManager
from config import *

logger = logging.getLogger(__name__)

class TradingManager:
    def __init__(self, api_client: BybitAPIClient, csv_manager: CSVManager):
        self.api_client = api_client
        self.csv_manager = csv_manager

    async def execute_trade(self, opportunity: ArbitrageOpportunity):
        if not ENABLE_LIVE_TRADING:
            logger.info("Режим реальной торговли отключен. Сделка не выполнена.")
            return False

        if LIVE_TRADING_DRY_RUN:
            logger.info("Dry run: Сделка не выполнена. Параметры:")
            self._log_trade_details(opportunity)
            return False

        try:
            # Здесь должна быть логика выполнения сделки
            # Для примера просто запишем сделку в файл
            self.csv_manager.save_executed_trade(opportunity)
            logger.info("Сделка выполнена успешно.")
            self._log_trade_details(opportunity)
            return True
        except Exception as e:
            logger.error(f"Ошибка выполнения сделки: {e}")
            return False

    def _log_trade_details(self, opportunity: ArbitrageOpportunity):
        logger.info(f"Сделка: {opportunity.path}")
        logger.info(f"Прибыль: {opportunity.profit_percent:.3f}%")
        logger.info(f"Мин. объем: {opportunity.min_volume_usdt:.2f} USDT")
        logger.info(f"Время выполнения: {opportunity.execution_time:.2f} сек")
