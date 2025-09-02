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

        # ИСПРАВЛЕНИЕ: Проверяем минимальную сумму сделки
        min_trade_amount = getattr(globals(), 'LIVE_TRADING_MIN_TRADE_USDT', 10.0)
        if opportunity.min_volume_usdt < min_trade_amount:
            logger.debug(f"Сумма сделки слишком мала: {opportunity.min_volume_usdt:.2f} < {min_trade_amount:.2f} USDT")
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
        """Проверяет достаточность баланса для сделки - ИСПРАВЛЕНО для UNIFIED"""
        try:
            # Получаем информацию о балансе для UNIFIED аккаунта
            balances = {}
            if balance_data and 'list' in balance_data:
                for account in balance_data['list']:
                    if account.get('accountType') == 'UNIFIED':
                        for coin in account.get('coin', []):
                            symbol = coin.get('coin')

                            # Безопасное извлечение баланса с обработкой пустых строк
                            def safe_float(value, default=0.0):
                                if value == '' or value is None:
                                    return default
                                try:
                                    return float(value)
                                except (ValueError, TypeError):
                                    return default

                            # Пробуем разные поля для определения доступного баланса
                            available_withdraw = safe_float(coin.get('availableToWithdraw'))
                            wallet_balance = safe_float(coin.get('walletBalance'))
                            equity = safe_float(coin.get('equity'))

                            # Используем наибольший из доступных балансов
                            free_balance = max(available_withdraw, wallet_balance, equity)

                            if free_balance > 0:
                                balances[symbol] = free_balance
                                logger.debug(
                                    f"Баланс {symbol}: {free_balance} (wallet: {wallet_balance}, equity: {equity}, available: {available_withdraw})")

            if not balances:
                logger.error("Не удалось извлечь информацию о балансе из ответа API")
                logger.debug(f"Структура ответа баланса: {balance_data}")
                return False

            # Показываем все доступные балансы для диагностики
            logger.info("💰 Доступные балансы:")
            for currency, balance in balances.items():
                if balance > 0:
                    logger.info(f"   {currency}: {balance}")

            # Проверяем баланс для первой валюты в пути
            first_pair = opportunity.path[0]
            if first_pair.endswith('USDT'):
                base_currency = 'USDT'
                # ИСПРАВЛЕНИЕ: Учитываем минимальную сумму сделки
                min_trade_amount = getattr(globals(), 'LIVE_TRADING_MIN_TRADE_USDT', 10.0)
                required_amount = max(min_trade_amount,
                                    min(LIVE_TRADING_MAX_TRADE_USDT, opportunity.min_volume_usdt))
            else:
                # Определяем базовую валюту из первой пары
                base_currency = None
                for currency in CROSS_CURRENCIES:
                    if first_pair.endswith(currency):
                        base_currency = currency
                        break

                if not base_currency:
                    logger.warning(f"Не удалось определить базовую валюту для {first_pair}")
                    return False

                # ИСПРАВЛЕНИЕ: Учитываем минимальную сумму и для других валют
                min_trade_amount = getattr(globals(), 'LIVE_TRADING_MIN_TRADE_USDT', 10.0)
                required_amount = max(min_trade_amount, opportunity.min_volume_usdt)

            current_balance = balances.get(base_currency, 0)

            if current_balance < required_amount:
                logger.warning(f"❌ Недостаточный баланс {base_currency}: {current_balance:.6f} < {required_amount:.6f}")
                return False

            logger.info(
                f"✅ Баланс достаточен: {base_currency} = {current_balance:.6f} (требуется: {required_amount:.6f})")
            return True

        except Exception as e:
            logger.error(f"Ошибка проверки баланса: {e}")
            logger.error(f"Структура balance_data: {balance_data}")
            return False

    async def _execute_arbitrage_path(self, opportunity: ArbitrageOpportunity) -> bool:
        """Выполняет последовательность сделок для арбитража"""
        try:
            # ИСПРАВЛЕНИЕ: Используем минимальную сумму сделки
            min_trade_amount = getattr(globals(), 'LIVE_TRADING_MIN_TRADE_USDT', 10.0)
            trade_amount = max(min_trade_amount,
                             min(LIVE_TRADING_MAX_TRADE_USDT, opportunity.min_volume_usdt))
            current_amount = trade_amount

            logger.info(f"🚀 Начинаем арбитраж с суммой {trade_amount} USDT")

            for i, (pair, direction, price) in enumerate(zip(
                    opportunity.path, opportunity.directions, opportunity.prices
            )):
                logger.info(f"📊 Шаг {i + 1}/3: {pair} - {direction.value.upper()} по цене {price}")

                # ИСПРАВЛЕНИЕ: Улучшенный расчет количества для ордера
                if direction == TradeDirection.BUY:
                    # При покупке: количество = сумма / цена
                    raw_qty = current_amount / price
                    # Округляем до разумного количества знаков
                    qty = self._format_quantity(raw_qty, pair)
                    current_amount = raw_qty  # Обновляем текущую сумму
                else:  # SELL
                    # При продаже: используем текущее количество
                    qty = self._format_quantity(current_amount, pair)
                    current_amount = current_amount * price  # Обновляем текущую сумму

                # ИСПРАВЛЕНИЕ: Проверяем минимальный размер ордера
                order_value = float(qty) * price
                if order_value < 5.0:  # Bybit требует минимум $5 для большинства пар
                    logger.warning(f"❌ Размер ордера слишком мал: {order_value:.2f} USDT < 5.0 USDT")
                    return False

                logger.info(f"💱 Размещаем ордер: {qty} {pair} (стоимость: ${order_value:.2f})")

                # Размещаем рыночный ордер
                result = await self.api_client.place_order(
                    symbol=pair,
                    side=direction.value,
                    qty=str(qty)
                )

                if not result:
                    logger.error(f"❌ Не удалось разместить ордер для {pair}")
                    return False

                order_id = result.get('orderId', 'N/A')
                logger.info(f"✅ Ордер размещен: {order_id}")

                # Небольшая задержка между ордерами
                await asyncio.sleep(LIVE_TRADING_ORDER_GAP_SEC)

            logger.info(f"🎉 Арбитраж завершен, итоговая сумма: ~{current_amount:.2f} USDT")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения торгового пути: {e}")
            return False

    def _format_quantity(self, quantity: float, pair: str) -> float:
        """ДОБАВЛЕНО: Форматирует количество для ордера с учетом требований биржи"""
        try:
            # Для большинства пар на Bybit используется 6 знаков после запятой
            # Но для некоторых популярных монет может быть меньше
            if any(pair.startswith(prefix) for prefix in ['BTC', 'ETH', 'BNB']):
                return round(quantity, 6)
            else:
                # Для менее популярных токенов может потребоваться больше знаков
                return round(quantity, 8)
        except:
            return round(quantity, 6)

    def _log_trade_details(self, opportunity: ArbitrageOpportunity):
        """Логирует детали сделки"""
        logger.info("=" * 60)
        logger.info("📈 ДЕТАЛИ АРБИТРАЖНОЙ СДЕЛКИ")
        logger.info("=" * 60)
        logger.info(f"🔄 Арбитражный путь: {' → '.join(opportunity.path)}")
        logger.info(f"💰 Ожидаемая прибыль: {opportunity.profit_percent:.4f}%")
        logger.info(f"💵 Минимальный объем: {opportunity.min_volume_usdt:.2f} USDT")
        logger.info(f"⚡ Время расчета: {opportunity.execution_time * 1000:.1f}ms")
        logger.info(f"📊 Стоимость спредов: {opportunity.spread_cost:.4f}%")
        logger.info("🔄 Торговые шаги:")

        for i, (pair, direction, price) in enumerate(zip(
                opportunity.path, opportunity.directions, opportunity.prices
        ), 1):
            action = "ПОКУПКА" if direction == TradeDirection.BUY else "ПРОДАЖА"
            logger.info(f"   {i}. {pair}: {action} по ${price:.8f}")

        logger.info("=" * 60)

    async def get_trading_stats(self) -> Dict:
        """Возвращает статистику торговли"""
        return {
            "total_trades": self.trade_count,
            "last_trade_time": self.last_trade_time,
            "trading_enabled": ENABLE_LIVE_TRADING,
            "dry_run_mode": LIVE_TRADING_DRY_RUN,
            "testnet_mode": API_TESTNET
        }