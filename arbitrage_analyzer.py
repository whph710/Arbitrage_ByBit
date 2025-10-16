from typing import List, Dict, Optional
from datetime import datetime
from configs import Config
from bestchange_handler import BestChangeHandler
from bybit_handler import BybitHandler


class ArbitrageAnalyzer:
    """Анализатор арбитражных возможностей"""

    def __init__(self, bestchange: BestChangeHandler, bybit: BybitHandler):
        self.bestchange = bestchange
        self.bybit = bybit

    def find_opportunities(self) -> List[Dict]:
        """Находит лучшие арбитражные связки"""
        print("\n" + "=" * 80)
        print("🔍 АНАЛИЗ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
        print("=" * 80)

        # Получаем данные
        bybit_prices = self.bybit.get_all_tickers()
        bc_pairs = self.bestchange.get_exchange_pairs()

        if not bybit_prices or not bc_pairs:
            print("✗ Недостаточно данных для анализа")
            return []

        opportunities = []
        checked = 0

        print(f"\n[Анализ] Проверка связок...")

        # Проходим по всем возможным связкам
        for crypto1, price1 in bybit_prices.items():
            for crypto2, price2 in bybit_prices.items():
                if crypto1 == crypto2:
                    continue

                checked += 1

                # Проверяем есть ли пара на BestChange
                if crypto1 in bc_pairs and crypto2 in bc_pairs[crypto1]:
                    for offer in bc_pairs[crypto1][crypto2]:
                        result = self._calculate_profit(
                            crypto1, crypto2,
                            price1, price2,
                            offer
                        )

                        if result and result['profit_percent'] >= Config.MIN_PROFIT_PERCENT:
                            opportunities.append(result)

        print(f"[Анализ] ✓ Проверено {checked} связок")
        print(f"[Анализ] ✓ Найдено {len(opportunities)} возможностей")

        # Сортируем по прибыли
        opportunities.sort(key=lambda x: x['profit_percent'], reverse=True)

        return opportunities[:Config.TOP_OPPORTUNITIES]

    def _calculate_profit(
            self,
            crypto1: str,
            crypto2: str,
            price1: float,
            price2: float,
            bc_offer: Dict
    ) -> Optional[Dict]:
        """
        Рассчитывает прибыль от арбитража

        Схема:
        1. Покупаем crypto1 на Bybit за USDT
        2. Отправляем crypto1 на обменник BestChange
        3. Меняем crypto1 → crypto2 на обменнике
        4. Отправляем crypto2 обратно на Bybit
        5. Продаем crypto2 → USDT на Bybit
        """

        start_usdt = Config.MIN_AMOUNT_USD

        # Шаг 1: Покупаем crypto1 на Bybit
        amount_crypto1 = start_usdt / price1

        # Проверяем резерв обменника
        if bc_offer['reserve'] > 0:
            expected_crypto2 = amount_crypto1 * bc_offer['rate']
            if bc_offer['reserve'] < expected_crypto2:
                return None  # недостаточный резерв

        # Шаг 2: Меняем на обменнике crypto1 → crypto2
        amount_crypto2 = amount_crypto1 * bc_offer['rate']

        # Шаг 3: Продаем crypto2 на Bybit
        final_usdt = amount_crypto2 * price2

        # Рассчитываем комиссии
        bybit_buy_fee = start_usdt * Config.BYBIT_TRADING_FEE
        bybit_sell_fee = final_usdt * Config.BYBIT_TRADING_FEE
        network_fees = Config.WITHDRAWAL_FEE_USD + Config.DEPOSIT_FEE_USD

        total_fees = bybit_buy_fee + bybit_sell_fee + network_fees
        net_profit = final_usdt - start_usdt - total_fees
        profit_percent = (net_profit / start_usdt) * 100

        return {
            'timestamp': datetime.now().isoformat(),
            'crypto1': crypto1,
            'crypto2': crypto2,
            'path': f"USDT → {crypto1} (Bybit) → {crypto2} (BestChange) → USDT (Bybit)",

            # Финансы
            'start_usdt': round(start_usdt, 2),
            'final_usdt': round(final_usdt, 2),
            'net_profit': round(net_profit, 2),
            'profit_percent': round(profit_percent, 2),
            'total_fees': round(total_fees, 2),

            # Детали обмена - Шаг 1: Покупка на Bybit
            'step1_buy_crypto1': {
                'crypto': crypto1,
                'amount': round(amount_crypto1, 8),
                'price_usdt': round(price1, 8),
                'total_usdt': round(start_usdt, 2),
                'fee': round(bybit_buy_fee, 2)
            },

            # Детали обмена - Шаг 2: Обмен на BestChange
            'step2_exchange': {
                'from_crypto': crypto1,
                'from_amount': round(amount_crypto1, 8),
                'to_crypto': crypto2,
                'to_amount': round(amount_crypto2, 8),
                'rate': round(bc_offer['rate'], 8),
                'exchanger_name': bc_offer['exchanger'],
                'exchanger_id': bc_offer['exchanger_id'],
                'reserve': round(bc_offer['reserve'], 2)
            },

            # Детали обмена - Шаг 3: Продажа на Bybit
            'step3_sell_crypto2': {
                'crypto': crypto2,
                'amount': round(amount_crypto2, 8),
                'price_usdt': round(price2, 8),
                'total_usdt': round(final_usdt, 2),
                'fee': round(bybit_sell_fee, 2)
            },

            # Текущие цены для проверки в момент выполнения
            'current_prices': {
                f'{crypto1}_usdt': round(price1, 8),
                f'{crypto2}_usdt': round(price2, 8),
                f'{crypto1}_to_{crypto2}_rate': round(bc_offer['rate'], 8)
            },

            # Дополнительная информация
            'warnings': [
                "Проверьте лимиты обменника перед выполнением",
                "Учтите время подтверждения транзакций в блокчейне",
                "Цены могут измениться за время выполнения операции",
                "Комиссии сети указаны приблизительно"
            ]
        }