# arbitrage_analyzer.py
from typing import List, Dict, Optional
from datetime import datetime
from configs import Config
from bestchange_handler import BestChangeHandler
from bybit_handler import BybitHandler


class ArbitrageAnalyzer:
    """Анализатор арбитражных возможностей (без учёта комиссий)"""

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

        print(f"\n[Анализ] Проверка арбитражных связок...\n")

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
                    offers = bc_pairs[crypto1][crypto2]

                    # Проверяем каждое предложение (уже отсортированы по курсу)
                    for offer in offers[:5]:  # Берём топ-5 предложений
                        checked += 1

                        result = self._calculate_profit(
                            crypto1, crypto2,
                            price1, price2,
                            offer
                        )

                        if result and result['spread_percent'] >= Config.MIN_PROFIT_PERCENT:
                            opportunities.append(result)
                            print(
                                f"[Найдено] {crypto1}→{crypto2}: +{result['spread_percent']}% (${result['potential_profit']}) через {offer['exchanger']}")

        print(f"\n[Анализ] ✓ Проверено {checked} связок")
        print(f"[Анализ] ✓ Найдено {len(opportunities)} прибыльных возможностей")

        # Сортируем по спреду
        opportunities.sort(key=lambda x: x['spread_percent'], reverse=True)

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
        Рассчитывает разницу цен (спред) между Bybit и BestChange

        Схема без комиссий:
        1. Покупаем crypto1 на Bybit за USDT
        2. Меняем crypto1 → crypto2 на обменнике BestChange
        3. Продаем crypto2 → USDT на Bybit
        """

        start_usdt = Config.MIN_AMOUNT_USD

        # ============================================
        # ШАГ 1: Покупаем crypto1 на Bybit
        # ============================================
        amount_crypto1 = start_usdt / price1

        # Проверяем минимальную сумму обменника
        if amount_crypto1 < bc_offer.get('give', 0):
            return None

        # ============================================
        # ШАГ 2: Меняем crypto1 → crypto2 на обменнике
        # ============================================
        amount_crypto2 = amount_crypto1 * bc_offer['rate']

        # Проверяем резерв обменника
        reserve = bc_offer.get('reserve', 0)
        if reserve > 0 and amount_crypto2 > reserve:
            return None

        # ============================================
        # ШАГ 3: Продаем crypto2 на Bybit
        # ============================================
        final_usdt = amount_crypto2 * price2

        # ============================================
        # РАСЧЁТ СПРЕДА
        # ============================================
        spread_usdt = final_usdt - start_usdt
        spread_percent = (spread_usdt / start_usdt) * 100

        # ============================================
        # СРАВНЕНИЕ С ПРЯМЫМ ОБМЕНОМ НА BYBIT
        # ============================================
        direct_rate_bybit = price1 / price2
        bestchange_rate = bc_offer['rate']
        rate_difference_percent = ((bestchange_rate - direct_rate_bybit) / direct_rate_bybit) * 100

        return {
            'timestamp': datetime.now().isoformat(),
            'crypto1': crypto1,
            'crypto2': crypto2,
            'path': f"USDT → {crypto1} (Bybit) → {crypto2} (BestChange) → USDT (Bybit)",

            # Финансы
            'start_usdt': round(start_usdt, 2),
            'final_usdt': round(final_usdt, 2),
            'potential_profit': round(spread_usdt, 2),
            'spread_percent': round(spread_percent, 2),

            # Детали обмена
            'step1_buy': {
                'crypto': crypto1,
                'amount': round(amount_crypto1, 8),
                'price_usdt': round(price1, 8),
                'total_usdt': round(start_usdt, 2)
            },

            'step2_exchange': {
                'from_crypto': crypto1,
                'from_amount': round(amount_crypto1, 8),
                'to_crypto': crypto2,
                'to_amount': round(amount_crypto2, 8),
                'rate': round(bc_offer['rate'], 8),
                'exchanger_name': bc_offer['exchanger'],
                'exchanger_id': bc_offer['exchanger_id'],
                'reserve': round(bc_offer.get('reserve', 0), 2),
                'min_amount': round(bc_offer.get('give', 0), 8)
            },

            'step3_sell': {
                'crypto': crypto2,
                'amount': round(amount_crypto2, 8),
                'price_usdt': round(price2, 8),
                'total_usdt': round(final_usdt, 2)
            },

            # Сравнение курсов
            'rates_comparison': {
                f'{crypto1}_to_{crypto2}_bestchange': round(bestchange_rate, 8),
                f'{crypto1}_to_{crypto2}_bybit': round(direct_rate_bybit, 8),
                'rate_difference_percent': round(rate_difference_percent, 2),
                'is_bestchange_better': bestchange_rate > direct_rate_bybit
            },

            # Текущие цены
            'current_prices': {
                f'{crypto1}_usdt': round(price1, 8),
                f'{crypto2}_usdt': round(price2, 8)
            },

            # Предупреждения
            'warnings': [
                "⚠️ Расчёт БЕЗ учёта комиссий - требуется достаточный спред",
                "⚠️ Проверьте лимиты обменника перед выполнением",
                "⚠️ Учтите время подтверждения транзакций (10-30 минут)",
                "⚠️ Цены могут измениться за время выполнения операции",
                "⚠️ Убедитесь что резерв обменника достаточен",
                f"{'✅' if rate_difference_percent > 0 else '❌'} Курс BestChange {'выгоднее' if rate_difference_percent > 0 else 'хуже'} Bybit на {abs(rate_difference_percent):.2f}%"
            ]
        }