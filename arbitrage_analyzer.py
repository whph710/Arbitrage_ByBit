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
        bc_pairs = self.bestchange.get_crypto_to_crypto_pairs()

        if not bybit_prices:
            print("✗ Не удалось получить цены с Bybit")
            return []

        if not bc_pairs:
            print("✗ Не удалось получить пары с BestChange")
            return []

        opportunities = []
        checked = 0

        print(f"\n[Анализ] Bybit: {len(bybit_prices)} торговых пар")
        print(f"[Анализ] BestChange: {len(bc_pairs)} криптовалют с обменами")

        # Показываем примеры для отладки
        if bybit_prices:
            bybit_sample = sorted(list(bybit_prices.keys()))[:15]
            print(f"[Анализ] Примеры Bybit: {', '.join(bybit_sample)}")

        if bc_pairs:
            bc_sample = sorted(list(bc_pairs.keys()))[:15]
            print(f"[Анализ] Примеры BestChange: {', '.join(bc_sample)}")

        # Находим общие криптовалюты
        common_cryptos = set(bybit_prices.keys()) & set(bc_pairs.keys())
        print(f"[Анализ] Общих криптовалют: {len(common_cryptos)}")
        if common_cryptos:
            common_sample = sorted(list(common_cryptos))[:10]
            print(f"[Анализ] Примеры общих: {', '.join(common_sample)}")

        print(f"[Анализ] Проверка арбитражных связок...\n")

        # Проходим по всем возможным связкам
        for crypto1 in common_cryptos:
            for crypto2 in common_cryptos:
                if crypto1 == crypto2:
                    continue

                # Получаем цены с Bybit
                price1 = bybit_prices.get(crypto1)
                price2 = bybit_prices.get(crypto2)

                if not price1 or not price2:
                    continue

                # Проверяем есть ли пара на BestChange
                if crypto1 in bc_pairs and crypto2 in bc_pairs[crypto1]:
                    # Берём только лучшее предложение (они уже отсортированы)
                    best_offer = bc_pairs[crypto1][crypto2][0]

                    checked += 1

                    result = self._calculate_profit(
                        crypto1, crypto2,
                        price1, price2,
                        best_offer
                    )

                    if result and result['profit_percent'] >= Config.MIN_PROFIT_PERCENT:
                        opportunities.append(result)
                        print(f"[Найдено] {crypto1}→{crypto2}: +{result['profit_percent']}% (${result['net_profit']})")

        print(f"\n[Анализ] ✓ Проверено {checked} связок")
        print(f"[Анализ] ✓ Найдено {len(opportunities)} прибыльных возможностей")

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

        # ============================================
        # ШАГ 1: Покупаем crypto1 на Bybit
        # ============================================
        bybit_buy_fee = start_usdt * Config.BYBIT_TRADING_FEE
        usdt_after_buy_fee = start_usdt - bybit_buy_fee
        amount_crypto1 = usdt_after_buy_fee / price1

        # ============================================
        # ШАГ 2: Отправляем на BestChange
        # ============================================
        # Здесь нужна комиссия сети для crypto1
        withdrawal_fee_crypto1 = Config.WITHDRAWAL_FEE_USD / price1  # в единицах crypto1
        amount_crypto1_after_withdrawal = amount_crypto1 - withdrawal_fee_crypto1

        if amount_crypto1_after_withdrawal <= 0:
            return None  # комиссия съела всё

        # ============================================
        # ШАГ 3: Меняем crypto1 → crypto2 на обменнике
        # ============================================
        amount_crypto2 = amount_crypto1_after_withdrawal * bc_offer['rate']

        # Проверяем резерв обменника
        if bc_offer['reserve'] > 0 and amount_crypto2 > bc_offer['reserve']:
            return None  # недостаточный резерв

        # ============================================
        # ШАГ 4: Отправляем crypto2 обратно на Bybit
        # ============================================
        deposit_fee_crypto2 = Config.DEPOSIT_FEE_USD / price2  # в единицах crypto2
        amount_crypto2_after_deposit = amount_crypto2 - deposit_fee_crypto2

        if amount_crypto2_after_deposit <= 0:
            return None  # комиссия съела всё

        # ============================================
        # ШАГ 5: Продаем crypto2 на Bybit
        # ============================================
        usdt_from_sell = amount_crypto2_after_deposit * price2
        bybit_sell_fee = usdt_from_sell * Config.BYBIT_TRADING_FEE
        final_usdt = usdt_from_sell - bybit_sell_fee

        # ============================================
        # РАСЧЁТ ПРИБЫЛИ
        # ============================================
        total_fees = bybit_buy_fee + bybit_sell_fee + Config.WITHDRAWAL_FEE_USD + Config.DEPOSIT_FEE_USD
        net_profit = final_usdt - start_usdt
        profit_percent = (net_profit / start_usdt) * 100

        # ============================================
        # СРАВНЕНИЕ С ПРЯМЫМ ОБМЕНОМ НА BYBIT
        # ============================================
        # Если бы мы просто обменяли crypto1 → crypto2 → USDT на Bybit
        direct_crypto2 = amount_crypto1 * (price1 / price2)  # сколько crypto2 получим напрямую
        direct_usdt = direct_crypto2 * price2
        direct_fees = start_usdt * Config.BYBIT_TRADING_FEE * 2  # две сделки
        direct_profit = direct_usdt - start_usdt - direct_fees

        # Арбитраж выгоден только если прибыль через BestChange больше прямого обмена
        advantage_over_direct = net_profit - direct_profit

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

            # Сравнение с прямым обменом
            'direct_exchange_profit': round(direct_profit, 2),
            'advantage_over_direct': round(advantage_over_direct, 2),
            'is_better_than_direct': advantage_over_direct > 0,

            # Детали обмена - Шаг 1: Покупка на Bybit
            'step1_buy_crypto1': {
                'crypto': crypto1,
                'amount_before_withdrawal': round(amount_crypto1, 8),
                'amount_after_withdrawal': round(amount_crypto1_after_withdrawal, 8),
                'price_usdt': round(price1, 8),
                'total_usdt': round(start_usdt, 2),
                'trading_fee': round(bybit_buy_fee, 2),
                'withdrawal_fee_usd': round(Config.WITHDRAWAL_FEE_USD, 2),
                'withdrawal_fee_crypto': round(withdrawal_fee_crypto1, 8)
            },

            # Детали обмена - Шаг 2: Обмен на BestChange
            'step2_exchange': {
                'from_crypto': crypto1,
                'from_amount': round(amount_crypto1_after_withdrawal, 8),
                'to_crypto': crypto2,
                'to_amount': round(amount_crypto2, 8),
                'rate': round(bc_offer['rate'], 8),
                'exchanger_name': bc_offer['exchanger'],
                'exchanger_id': bc_offer['exchanger_id'],
                'reserve': round(bc_offer['reserve'], 2),
                'min_give': round(bc_offer['give'], 8),
                'max_receive': round(bc_offer['receive'], 8)
            },

            # Детали обмена - Шаг 3: Продажа на Bybit
            'step3_sell_crypto2': {
                'crypto': crypto2,
                'amount_before_deposit': round(amount_crypto2, 8),
                'amount_after_deposit': round(amount_crypto2_after_deposit, 8),
                'price_usdt': round(price2, 8),
                'total_usdt': round(final_usdt, 2),
                'trading_fee': round(bybit_sell_fee, 2),
                'deposit_fee_usd': round(Config.DEPOSIT_FEE_USD, 2),
                'deposit_fee_crypto': round(deposit_fee_crypto2, 8)
            },

            # Текущие цены для проверки в момент выполнения
            'current_prices': {
                f'{crypto1}_usdt': round(price1, 8),
                f'{crypto2}_usdt': round(price2, 8),
                f'{crypto1}_to_{crypto2}_rate_bestchange': round(bc_offer['rate'], 8),
                f'{crypto1}_to_{crypto2}_rate_bybit': round(price1 / price2, 8)
            },

            # Дополнительная информация
            'warnings': [
                "⚠️ Проверьте лимиты обменника перед выполнением",
                "⚠️ Учтите время подтверждения транзакций (может быть 10-30 минут)",
                "⚠️ Цены могут измениться за время выполнения операции",
                "⚠️ Комиссии сети указаны приблизительно - проверьте актуальные",
                "⚠️ Убедитесь что резерв обменника достаточен",
                f"{'✅' if advantage_over_direct > 0 else '❌'} Выгоднее чем прямой обмен на Bybit на ${abs(advantage_over_direct):.2f}"
            ]
        }