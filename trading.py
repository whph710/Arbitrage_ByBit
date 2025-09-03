import logging
import asyncio
import time
from typing import Dict, Optional, Tuple
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
        self.session_profit = 0.0
        self.session_trades = 0

    async def execute_trade(self, opportunity: ArbitrageOpportunity) -> bool:
        """Выполняет арбитражную сделку - ИСПРАВЛЕНО"""
        if not ENABLE_LIVE_TRADING:
            logger.debug("Режим реальной торговли отключен")
            return False

        # Проверяем минимальную сумму сделки
        if opportunity.min_volume_usdt < LIVE_TRADING_MIN_TRADE_USDT:
            logger.debug(
                f"Сумма сделки слишком мала: {opportunity.min_volume_usdt:.2f} < {LIVE_TRADING_MIN_TRADE_USDT} USDT")
            return False

        # Проверяем максимальную сумму сделки
        if opportunity.min_volume_usdt > LIVE_TRADING_MAX_TRADE_USDT:
            logger.debug(
                f"Сумма сделки слишком велика: {opportunity.min_volume_usdt:.2f} > {LIVE_TRADING_MAX_TRADE_USDT} USDT")
            return False

        # Проверка частоты сделок
        if not self._check_trade_limits():
            logger.debug("Превышен лимит частоты сделок")
            return False

        # DRY RUN режим (симуляция)
        if LIVE_TRADING_DRY_RUN:
            logger.info("🔴 DRY RUN: Симуляция арбитражной сделки")
            self._log_trade_details(opportunity)

            # Симулируем успешность (90% успеха для реалистичности)
            import random
            success = random.random() > 0.1

            if success:
                self.csv_manager.save_executed_trade(opportunity)
                self.trade_count += 1
                self.session_trades += 1

                # Симулируем прибыль
                simulated_profit = INITIAL_AMOUNT * opportunity.profit_percent / 100
                self.session_profit += simulated_profit

                logger.info(f"✅ Симуляция успешна. Прибыль: ${simulated_profit:.2f}")
                return True
            else:
                logger.info("❌ Симуляция неудачна (рыночные условия)")
                return False

        # Реальная торговля
        try:
            # Проверка баланса перед торговлей
            if REQUIRE_BALANCE_CHECK_BEFORE_LIVE:
                balance = await self.api_client.get_account_balance()
                if not balance:
                    logger.error("Не удалось получить баланс аккаунта")
                    return False

                sufficient_balance, trade_amount = self._check_sufficient_balance(balance, opportunity)
                if not sufficient_balance:
                    logger.warning("Недостаточный баланс для выполнения сделки")
                    return False
            else:
                trade_amount = min(LIVE_TRADING_MAX_TRADE_USDT, opportunity.min_volume_usdt)

            # Выполнение торгового пути
            success, actual_profit = await self._execute_arbitrage_path(opportunity, trade_amount)

            if success:
                self.csv_manager.save_executed_trade(opportunity)
                self.trade_count += 1
                self.session_trades += 1
                self.session_profit += actual_profit

                logger.info(f"✅ Арбитражная сделка выполнена успешно! Прибыль: ${actual_profit:.2f}")
                self._log_trade_details(opportunity)
                return True
            else:
                logger.error("❌ Ошибка выполнения арбитражной сделки")
                return False

        except Exception as e:
            logger.error(f"Исключение при выполнении сделки: {e}")
            return False

    def _check_trade_limits(self) -> bool:
        """Проверяет лимиты на частоту сделок - УЛУЧШЕНО"""
        current_time = time.time()

        # Проверка минимального интервала между сделками
        if current_time - self.last_trade_time < LIVE_TRADING_ORDER_GAP_SEC:
            return False

        # Проверка количества сделок в минуту (упрощенная)
        # В реальном проекте здесь должна быть очередь с временными метками

        self.last_trade_time = current_time
        return True

    def _check_sufficient_balance(self, balance_data: Dict, opportunity: ArbitrageOpportunity) -> Tuple[bool, float]:
        """Проверяет достаточность баланса и возвращает рекомендуемую сумму сделки - ИСПРАВЛЕНО"""
        try:
            balances = {}

            # Извлекаем балансы из ответа API
            if balance_data and 'list' in balance_data:
                for account in balance_data['list']:
                    if account.get('accountType') == 'UNIFIED':
                        for coin in account.get('coin', []):
                            symbol = coin.get('coin')

                            # Безопасное извлечение числовых значений
                            def safe_float(value, default=0.0):
                                if value == '' or value is None:
                                    return default
                                try:
                                    return float(value)
                                except (ValueError, TypeError):
                                    return default

                            # Используем наиболее подходящее поле для свободного баланса
                            available_balance = safe_float(coin.get('availableToWithdraw'))
                            wallet_balance = safe_float(coin.get('walletBalance'))

                            # Берем минимум из доступного и кошелькового баланса
                            free_balance = min(available_balance,
                                               wallet_balance) if available_balance > 0 else wallet_balance

                            if free_balance > 0:
                                balances[symbol] = free_balance

            if not balances:
                logger.error("Не удалось извлечь информацию о балансе")
                return False, 0.0

            # Определяем базовую валюту из первой пары в пути
            first_pair = opportunity.path[0]
            base_currency = None

            # Ищем базовую валюту
            for currency in ['USDT', 'USDC', 'BUSD', 'BTC', 'ETH']:
                if first_pair.endswith(currency):
                    base_currency = currency
                    break

            if not base_currency:
                logger.warning(f"Не удалось определить базовую валюту для {first_pair}")
                return False, 0.0

            current_balance = balances.get(base_currency, 0.0)

            # Рассчитываем оптимальную сумму сделки
            max_possible_trade = min(
                current_balance * 0.95,  # Оставляем 5% баланса на комиссии и безопасность
                LIVE_TRADING_MAX_TRADE_USDT,
                opportunity.min_volume_usdt * 2  # Не превышаем двойную ликвидность
            )

            recommended_trade = max(LIVE_TRADING_MIN_TRADE_USDT, max_possible_trade)

            if current_balance < LIVE_TRADING_MIN_TRADE_USDT:
                logger.warning(
                    f"❌ Недостаточный баланс {base_currency}: {current_balance:.2f} < {LIVE_TRADING_MIN_TRADE_USDT}")
                return False, 0.0

            logger.info(
                f"✅ Баланс {base_currency}: {current_balance:.2f}, рекомендуемая сумма сделки: ${recommended_trade:.2f}")
            return True, recommended_trade

        except Exception as e:
            logger.error(f"Ошибка проверки баланса: {e}")
            return False, 0.0

    async def _execute_arbitrage_path(self, opportunity: ArbitrageOpportunity, trade_amount: float) -> Tuple[
        bool, float]:
        """Выполняет последовательность сделок для арбитража - ИСПРАВЛЕНО"""
        try:
            logger.info(f"🚀 Начинаем арбитраж с суммой ${trade_amount:.2f}")

            current_amount = trade_amount
            step_results = []

            for i, (pair, direction, expected_price) in enumerate(zip(
                    opportunity.path, opportunity.directions, opportunity.prices
            ), 1):

                logger.info(f"📊 Шаг {i}/3: {pair} - {direction.value.upper()}")

                # Рассчитываем количество для ордера
                if direction == TradeDirection.BUY:
                    # При покупке: количество = сумма / цена
                    raw_qty = current_amount / expected_price
                    qty = self._format_quantity(raw_qty, pair)
                else:  # SELL
                    # При продаже: продаем имеющееся количество
                    qty = self._format_quantity(current_amount, pair)

                # Проверяем минимальный размер ордера
                order_value = float(qty) * expected_price
                if order_value < 5.0:  # Bybit минимум
                    logger.warning(f"❌ Ордер слишком мал: ${order_value:.2f}")
                    return False, 0.0

                logger.info(f"💱 Ордер: {qty} {pair} (~${order_value:.2f})")

                # Размещаем рыночный ордер
                result = await self.api_client.place_order(
                    symbol=pair,
                    side=direction.value,
                    qty=str(qty)
                )

                if not result:
                    logger.error(f"❌ Не удалось разместить ордер для {pair}")
                    return False, 0.0

                order_id = result.get('orderId', 'N/A')
                logger.info(f"✅ Ордер размещен: {order_id}")

                # Обновляем текущую сумму (упрощенно, в реальности нужно получать фактическую цену исполнения)
                if direction == TradeDirection.BUY:
                    current_amount = float(qty)  # Получили количество купленной валюты
                else:
                    current_amount = float(qty) * expected_price  # Получили базовую валюту

                step_results.append({
                    'pair': pair,
                    'direction': direction.value,
                    'quantity': qty,
                    'expected_price': expected_price,
                    'order_id': order_id
                })

                # Пауза между ордерами
                await asyncio.sleep(LIVE_TRADING_ORDER_GAP_SEC)

            # Рассчитываем фактическую прибыль (упрощенно)
            actual_profit = current_amount - trade_amount
            profit_percent = (actual_profit / trade_amount) * 100

            logger.info(f"🎉 Арбитраж завершен!")
            logger.info(f"💰 Начальная сумма: ${trade_amount:.2f}")
            logger.info(f"💰 Итоговая сумма: ${current_amount:.2f}")
            logger.info(f"📈 Прибыль: ${actual_profit:.2f} ({profit_percent:.3f}%)")

            return True, actual_profit

        except Exception as e:
            logger.error(f"❌ Ошибка выполнения торгового пути: {e}")
            return False, 0.0

    def _format_quantity(self, quantity: float, pair: str) -> float:
        """Форматирует количество с учетом требований биржи - УЛУЧШЕНО"""
        try:
            # Специальные правила для популярных пар
            if any(pair.startswith(prefix) for prefix in ['BTC', 'ETH']):
                return round(quantity, 6)
            elif any(pair.startswith(prefix) for prefix in ['USDT', 'USDC', 'BUSD']):
                return round(quantity, 4)
            elif any(pair.endswith(suffix) for suffix in ['USDT', 'USDC', 'BUSD']):
                return round(quantity, 2)  # Для пар типа XXX/USDT
            else:
                return round(quantity, 8)  # Универсальное значение

        except Exception as e:
            logger.debug(f"Ошибка форматирования количества: {e}")
            return round(quantity, 6)

    def _log_trade_details(self, opportunity: ArbitrageOpportunity):
        """Логирует детали сделки - УЛУЧШЕНО"""
        logger.info("=" * 70)
        logger.info("📈 ДЕТАЛИ АРБИТРАЖНОЙ СДЕЛКИ")
        logger.info("=" * 70)

        # Извлекаем валюты для понимания маршрута
        path_description = self._get_path_description(opportunity.path)

        logger.info(f"🔄 Маршрут: {path_description}")
        logger.info(f"💰 Ожидаемая прибыль: {opportunity.profit_percent:.4f}%")
        logger.info(f"💵 Объем операции: ${opportunity.min_volume_usdt:.2f}")
        logger.info(f"⚡ Время расчета: {opportunity.execution_time * 1000:.1f}ms")
        logger.info(f"📊 Совокупный спред: {opportunity.spread_cost:.3f}%")

        logger.info("🔄 Торговые операции:")
        for i, (pair, direction, price) in enumerate(zip(
                opportunity.path, opportunity.directions, opportunity.prices
        ), 1):
            action = "ПОКУПКА" if direction == TradeDirection.BUY else "ПРОДАЖА"
            logger.info(f"   {i}. {pair}: {action} по ${price:.8f}")

        # Статистика сессии
        if self.session_trades > 0:
            logger.info(f"📊 Статистика сессии:")
            logger.info(f"   Сделок выполнено: {self.session_trades}")
            logger.info(f"   Общая прибыль: ${self.session_profit:.2f}")
            logger.info(f"   Средняя прибыль: ${self.session_profit / self.session_trades:.2f}")

        logger.info("=" * 70)

    def _get_path_description(self, path: list[str]) -> str:
        """Возвращает человекочитаемое описание торгового пути"""
        try:
            # Определяем валюты из пути
            base_currency = "USDT"  # Предполагаемая базовая валюта

            # Находим базовую валюту из первой пары
            for currency in CROSS_CURRENCIES:
                if path[0].endswith(currency):
                    base_currency = currency
                    break

            currency_a = path[0].replace(base_currency, '')

            # Определяем вторую валюту
            currency_b = None
            pair2 = path[1]
            if pair2.startswith(currency_a):
                currency_b = pair2[len(currency_a):]
            elif pair2.endswith(currency_a):
                currency_b = pair2[:-len(currency_a)]

            if currency_b:
                return f"{base_currency} → {currency_a} → {currency_b} → {base_currency}"
            else:
                return f"{' → '.join(path)}"

        except Exception as e:
            logger.debug(f"Ошибка формирования описания пути: {e}")
            return f"{' → '.join(path)}"

    async def get_trading_stats(self) -> Dict:
        """Возвращает статистику торговли - РАСШИРЕНО"""
        return {
            "total_trades": self.trade_count,
            "session_trades": self.session_trades,
            "session_profit": self.session_profit,
            "last_trade_time": self.last_trade_time,
            "trading_enabled": ENABLE_LIVE_TRADING,
            "dry_run_mode": LIVE_TRADING_DRY_RUN,
            "testnet_mode": API_TESTNET,
            "average_profit_per_trade": self.session_profit / max(1, self.session_trades),
            "min_trade_amount": LIVE_TRADING_MIN_TRADE_USDT,
            "max_trade_amount": LIVE_TRADING_MAX_TRADE_USDT
        }

    def reset_session_stats(self):
        """Сбрасывает статистику сессии"""
        self.session_trades = 0
        self.session_profit = 0.0
        logger.info("📊 Статистика сессии сброшена")