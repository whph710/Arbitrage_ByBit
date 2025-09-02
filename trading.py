import logging
import asyncio
from typing import Dict, Optional
from models import ArbitrageOpportunity, TradeDirection
from api_client import BybitAPIClient
from csv_manager import CSVManager
from config import *

logger = logging.getLogger(__name__)


class TradingManager:
    def __init__(self, api_client: BybitAPIClient, csv_manager: CSVManager):
        self.api_client = api_client
        self.csv_manager = csv_manager
        self.trade_count = 0
        self.last_trade_time = 0

    async def execute_trade(self, opportunity: ArbitrageOpportunity):
        """Выполняет арбитражную сделку"""
        if not ENABLE_LIVE_TRADING:
            logger.debug("Режим реальной торговли отключен")
            return False

        # Проверка частоты сделок
        if not self._check_trade_limits():
            logger.warning("Превышен лимит частоты сделок")
            return False

        if LIVE_TRADING_DRY_RUN:
            logger.info("🔴 DRY RUN: Симуляция сделки")
            self._log_trade_details(opportunity)
            self.csv_manager.save_executed_trade(opportunity)
            return True

        # Реальная торговля
        try:
            # Проверка баланса перед торговлей
            if REQUIRE_BALANCE_CHECK_BEFORE_LIVE:
                balance = await self.api_client.get_account_balance()
                if not balance:
                    logger.error("Не удалось получить баланс аккаунта")
                    return False

                if not self._check_sufficient_balance(balance, opportunity):
                    logger.warning("Недостаточный баланс для выполнения сделки")
                    return False

            # Выполнение торгового пути
            success = await self._execute_arbitrage_path(opportunity)

            if success:
                self.csv_manager.save_executed_trade(opportunity)
                logger.info("✅ Арбитражная сделка выполнена успешно")
                self._log_trade_details(opportunity)
                self.trade_count += 1
                return True
            else:
                logger.error("❌ Ошибка выполнения арбитражной сделки")
                return False

        except Exception as e:
            logger.error(f"Исключение при выполнении сделки: {e}")
            return False

    def _check_trade_limits(self) -> bool:
        """Проверяет лимиты на частоту сделок"""
        import time
        current_time = time.time()

        # Проверка минимального интервала между сделками
        if current_time - self.last_trade_time < LIVE_TRADING_ORDER_GAP_SEC:
            return False

        self.last_trade_time = current_time
        return True

    def _check_sufficient_balance(self, balance_data: Dict, opportunity: ArbitrageOpportunity) -> bool:
        """Проверяет достаточность баланса для сделки"""
        try:
            # Получаем информацию о балансе
            balances = {}
            if balance_data and 'list' in balance_data:
                for account in balance_data['list']:
                    if account.get('accountType') == 'SPOT':
                        for coin in account.get('coin', []):
                            symbol = coin.get('coin')
                            free_balance = float(coin.get('free', 0))
                            balances[symbol] = free_balance

            # Проверяем баланс для первой валюты в пути
            first_pair = opportunity.path[0]
            if first_pair.endswith('USDT'):
                base_currency = 'USDT'
                required_amount = min(LIVE_TRADING_MAX_TRADE_USDT, opportunity.min_volume_usdt)
            else:
                # Определяем базовую валюту из первой пары
                for currency in CROSS_CURRENCIES:
                    if first_pair.endswith(currency):
                        base_currency = currency
                        break
                else:
                    logger.warning(f"Не удалось определить базовую валюту для {first_pair}")
                    return False
                required_amount = opportunity.min_volume_usdt

            current_balance = balances.get(base_currency, 0)

            if current_balance < required_amount:
                logger.warning(f"Недостаточный баланс {base_currency}: {current_balance} < {required_amount}")
                return False

            logger.info(f"Баланс достаточен: {base_currency} = {current_balance}")
            return True

        except Exception as e:
            logger.error(f"Ошибка проверки баланса: {e}")
            return False

    async def _execute_arbitrage_path(self, opportunity: ArbitrageOpportunity) -> bool:
        """Выполняет последовательность сделок для арбитража"""
        try:
            trade_amount = min(LIVE_TRADING_MAX_TRADE_USDT, opportunity.min_volume_usdt)
            current_amount = trade_amount

            logger.info(f"Начинаем арбитраж с суммой {trade_amount} USDT")

            for i, (pair, direction, price) in enumerate(zip(
                    opportunity.path, opportunity.directions, opportunity.prices
            )):
                logger.info(f"Шаг {i + 1}/3: {pair} - {direction.value.upper()} по цене {price}")

                # Рассчитываем количество для ордера
                if direction == TradeDirection.BUY:
                    qty = str(round(current_amount / price, 6))
                    current_amount = current_amount / price
                else:  # SELL
                    qty = str(round(current_amount, 6))
                    current_amount = current_amount * price

                # Размещаем рыночный ордер
                result = await self.api_client.place_order(
                    symbol=pair,
                    side=direction.value,
                    qty=qty
                )

                if not result:
                    logger.error(f"Не удалось разместить ордер для {pair}")
                    return False

                logger.info(f"Ордер размещен: {result.get('orderId', 'N/A')}")

                # Небольшая задержка между ордерами
                await asyncio.sleep(LIVE_TRADING_ORDER_GAP_SEC)

            logger.info(f"Арбитраж завершен, итоговая сумма: ~{current_amount:.2f} USDT")
            return True

        except Exception as e:
            logger.error(f"Ошибка выполнения торгового пути: {e}")
            return False

    def _log_trade_details(self, opportunity: ArbitrageOpportunity):
        """Логирует детали сделки"""
        logger.info(f"📈 Арбитражный путь: {' → '.join(opportunity.path)}")
        logger.info(f"💰 Ожидаемая прибыль: {opportunity.profit_percent:.4f}%")
        logger.info(f"💵 Минимальный объем: {opportunity.min_volume_usdt:.2f} USDT")
        logger.info(f"⚡ Время расчета: {opportunity.execution_time * 1000:.1f}ms")
        logger.info(f"📊 Стоимость спредов: {opportunity.spread_cost:.4f}%")

        for i, (pair, direction, price) in enumerate(zip(
                opportunity.path, opportunity.directions, opportunity.prices
        ), 1):
            action = "ПОКУПКА" if direction == TradeDirection.BUY else "ПРОДАЖА"
            logger.info(f"   {i}. {pair}: {action} по ${price:.8f}")

    async def get_trading_stats(self) -> Dict:
        """Возвращает статистику торговли"""
        return {
            "total_trades": self.trade_count,
            "last_trade_time": self.last_trade_time,
            "trading_enabled": ENABLE_LIVE_TRADING,
            "dry_run_mode": LIVE_TRADING_DRY_RUN,
            "testnet_mode": API_TESTNET
        }