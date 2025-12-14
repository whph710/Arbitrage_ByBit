import asyncio
import math
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from configs_continuous import ENABLE_CACHE, CACHE_HOT_PAIRS, MIN_PROFIT_USD
from utils import is_valid_number, validate_price, validate_rate, TTLCache, MemoizedCalculator


class ExchangeArbitrageAnalyzer:
    """
    Оптимизированный анализатор арбитража через обменники (BestChange)
    Схема: Bybit (купить A) → BestChange (обменять A→B) → Bybit (продать B)

    С учетом:
    - Комиссий Bybit на торговлю (Taker/Maker)
    - Комиссий Bybit на вывод монет (через API)
    """

    # Комиссии Bybit Spot
    BYBIT_TAKER_FEE = 0.001800  # 0.1800%
    BYBIT_MAKER_FEE = 0.001000  # 0.1000%

    def __init__(self, bybit_client, bestchange_client):
        self.bybit = bybit_client
        self.bestchange = bestchange_client
        self.found_count = 0
        self.checked_pairs = 0

        # Кэширование "горячих" пар с TTL и ограничением размера
        self.hot_pairs_cache = TTLCache(max_size=CACHE_HOT_PAIRS, ttl_seconds=600)  # 10 минут TTL
        self.pair_performance = defaultdict(lambda: {'checks': 0, 'finds': 0, 'avg_spread': 0})
        
        # Мемоизация для частых расчетов
        self.calculator = MemoizedCalculator(cache_size=500, ttl_seconds=60)
        
        # Кэш для результатов проверки пар (избегаем повторных проверок)
        self.pair_check_cache = TTLCache(max_size=1000, ttl_seconds=30)  # 30 секунд TTL

    def _get_bybit_trade_url(self, coin: str, quote: str = 'USDT') -> str:
        """Генерирует ссылку на торговую пару Bybit"""
        return f"https://www.bybit.com/ru-RU/trade/spot/{coin}/{quote}"

    def _get_bybit_deposit_url(self) -> str:
        """Генерирует ссылку на страницу депозита Bybit"""
        return "https://www.bybit.com/user/assets/deposit?source=AssetDeposit"

    def _get_bybit_withdraw_url(self) -> str:
        """Генерирует ссылку на страницу вывода Bybit"""
        return "https://www.bybit.com/user/assets/home/overview"

    def _get_bestchange_exchanger_url(self, exchanger_id: int) -> str:
        """Генерирует ссылку на обменник BestChange"""
        return f"https://www.bestchange.com/click.php?id={exchanger_id}"

    def _calculate_bybit_fees(self, amount: float, is_taker: bool = True) -> tuple:
        """
        Рассчитывает комиссии Bybit с мемоизацией

        Args:
            amount: Сумма сделки
            is_taker: True для Taker (0.18%), False для Maker (0.10%)

        Returns:
            (сумма_комиссии, сумма_после_комиссии)
        """
        # Валидация входных данных
        if not is_valid_number(amount):
            return (0.0, 0.0)
        
        fee_rate = self.BYBIT_TAKER_FEE if is_taker else self.BYBIT_MAKER_FEE
        return self.calculator.calculate_fee(amount, fee_rate)

    def _get_withdrawal_fee_in_usdt(self, coin: str, amount: float, price_usdt: float) -> tuple:
        """
        Получает комиссию на вывод монеты в USDT

        Args:
            coin: Тикер монеты
            amount: Количество монет для вывода
            price_usdt: Цена монеты в USDT

        Returns:
            (комиссия_в_монетах, комиссия_в_usdt, название_сети)
        """
        # Получаем минимальную комиссию на вывод
        withdrawal_fee_coin = self.bybit.get_min_withdrawal_fee(coin)

        if withdrawal_fee_coin is None:
            # Если данные о комиссии недоступны, используем приблизительную оценку
            # На основе типичных комиссий
            estimated_fees = {
                'BTC': 0.0005,
                'ETH': 0.005,
                'USDT': 1.0,
                'USDC': 1.0,
                'BNB': 0.0001,
                'SOL': 0.01,
                'XRP': 0.25,
                'DOGE': 5.0,
                'TRX': 1.0
            }
            withdrawal_fee_coin = estimated_fees.get(coin, 0.01)  # По умолчанию 0.01 монеты
            best_chain = "неизвестна (оценка)"
        else:
            # Получаем информацию о лучшей сети
            best_chain_info = self.bybit.get_best_withdrawal_chain(coin)
            best_chain = best_chain_info['chain'] if best_chain_info else "неизвестна"

        # Конвертируем в USDT
        withdrawal_fee_usdt = withdrawal_fee_coin * price_usdt

        return withdrawal_fee_coin, withdrawal_fee_usdt, best_chain

    async def find_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.3,
            max_spread: float = 50.0,
            min_reserve: float = 0,
            parallel_requests: int = 500
    ) -> List[Dict]:
        """
        Ищет арбитражные связки через обменники BestChange (ОПТИМИЗИРОВАНО)

        С учетом:
        - Комиссий Bybit на торговлю
        - Комиссий Bybit на вывод (withdrawal fees)

        Args:
            start_amount: Начальная сумма в USDT
            min_spread: Минимальный спред для фильтрации
            max_spread: Максимальный спред (защита от аномалий)
            min_reserve: Минимальный резерв обменника
            parallel_requests: Количество параллельных проверок
        """
        print(f"\n[BestChange Arbitrage] 🚀 БЫСТРЫЙ ПОИСК связок...")
        print(f"[BestChange Arbitrage] Параметры: ${start_amount}, спред {min_spread}%-{max_spread}%")
        print(f"[BestChange Arbitrage] ⚡ Параллельных запросов: {parallel_requests}")
        print(f"[BestChange Arbitrage] 💰 Мин. резерв: ${min_reserve}, мин. прибыль: ${MIN_PROFIT_USD}")
        print(
            f"[BestChange Arbitrage] 💳 Комиссии Bybit: Taker {self.BYBIT_TAKER_FEE * 100:.4f}%, Maker {self.BYBIT_MAKER_FEE * 100:.4f}%")

        if self.bybit.withdrawal_info_loaded:
            print(
                f"[BestChange Arbitrage] ✅ Учитываются комиссии на вывод (загружено для {len(self.bybit.min_withdrawal_fees)} монет)")
        else:
            print(f"[BestChange Arbitrage] ⚠️  Комиссии на вывод будут оценочными (добавьте API ключи для точности)")

        opportunities = []

        # Находим общие монеты
        bybit_coins = set(self.bybit.usdt_pairs.keys())
        bestchange_coins = set(self.bestchange.crypto_currencies.keys())
        common_coins = bybit_coins & bestchange_coins

        if not common_coins:
            print(f"[BestChange Arbitrage] ❌ Нет общих монет между Bybit и BestChange")
            return opportunities

        # Фильтруем только самые ликвидные монеты (оптимизировано)
        liquid_coins = []
        for coin in common_coins:
            liquidity = self.bybit.get_liquidity_score(coin, 'USDT')
            # Ранний выход - пропускаем неликвидные монеты
            if liquidity < 30:
                continue
            
            volume = self.bybit.get_volume_24h(coin, 'USDT')
            liquid_coins.append((coin, liquidity, volume))

        # Оптимизированная сортировка - только по ликвидности
        liquid_coins.sort(key=lambda x: x[1], reverse=True)
        common_coins_list = [coin for coin, _, _ in liquid_coins]

        print(f"[BestChange Arbitrage] ✓ Общих монет: {len(common_coins)}")
        print(f"[BestChange Arbitrage] ✓ Высоколиквидных: {len(common_coins_list)}")

        # Создаём все возможные пары
        all_pairs = []
        all_pairs_set = set()  # Для быстрой проверки наличия

        # Сначала проверяем кэшированные "горячие" пары
        if ENABLE_CACHE:
            # Очищаем истекшие записи
            self.hot_pairs_cache.cleanup_expired()
            self.calculator.cleanup()
            
            # Получаем актуальные горячие пары
            hot_pairs = self.get_hot_pairs()
            
            if hot_pairs:
                print(f"[BestChange Arbitrage] 🔥 Приоритет для {len(hot_pairs)} горячих пар")
                for pair in hot_pairs:
                    if pair not in all_pairs_set:
                        all_pairs.append(pair)
                        all_pairs_set.add(pair)

        # Добавляем остальные пары (оптимизировано - используем set для быстрой проверки)
        for coin_a in common_coins_list:
            for coin_b in common_coins_list:
                if coin_a != coin_b:
                    pair = (coin_a, coin_b)
                    if pair not in all_pairs_set:
                        all_pairs.append(pair)
                        all_pairs_set.add(pair)

        total_pairs = len(all_pairs)
        print(f"[BestChange Arbitrage] 📦 Всего пар для проверки: {total_pairs}")
        print(f"[BestChange Arbitrage] 💡 Результаты выводятся в реальном времени...")
        print("=" * 100)

        self.checked_pairs = 0
        self.found_count = 0

        # Массово-параллельная обработка (оптимизировано)
        # Используем батчинг для лучшей производительности
        semaphore = asyncio.Semaphore(parallel_requests)
        tasks = []

        for coin_a, coin_b in all_pairs:
            task = self._check_pair_with_semaphore(
                semaphore, coin_a, coin_b, start_amount, min_spread, max_spread, min_reserve
            )
            tasks.append(task)

        # Оптимизировано: запускаем задачи батчами для лучшего контроля
        batch_size = min(parallel_requests, 100)  # Обрабатываем по 100 задач за раз
        results = []
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)

        # Собираем результаты
        for result in results:
            if isinstance(result, dict) and 'spread' in result:
                opportunities.append(result)

        print("=" * 100)
        print(f"\n[BestChange Arbitrage] ✅ Проверка завершена!")
        print(f"[BestChange Arbitrage] 📊 Проверено пар: {self.checked_pairs}")
        print(f"[BestChange Arbitrage] 🎯 Найдено связок: {len(opportunities)}")

        # Обновляем кэш горячих пар
        if ENABLE_CACHE and opportunities:
            self._update_hot_pairs_cache(opportunities)

        # Сортируем по прибыли
        opportunities.sort(key=lambda x: x['profit'], reverse=True)

        return opportunities

    async def _check_pair_with_semaphore(
            self,
            semaphore: asyncio.Semaphore,
            coin_a: str,
            coin_b: str,
            start_amount: float,
            min_spread: float,
            max_spread: float,
            min_reserve: float
    ):
        """Проверяет одну пару с ограничением параллелизма"""
        async with semaphore:
            self.checked_pairs += 1

            # Прогресс каждые 200 пар
            if self.checked_pairs % 200 == 0:
                print(f"[BestChange Arbitrage] 📊 Прогресс: {self.checked_pairs} | Найдено: {self.found_count}")

            result = await self._check_single_pair(coin_a, coin_b, start_amount, min_spread, max_spread, min_reserve)

            if result:
                self.found_count += 1
                self._print_opportunity(result, self.found_count)

                # Обновляем статистику пары
                pair_key = (coin_a, coin_b)
                self.pair_performance[pair_key]['finds'] += 1
                self.pair_performance[pair_key]['avg_spread'] = (
                                                                        self.pair_performance[pair_key]['avg_spread'] +
                                                                        result['spread']
                                                                ) / 2

            # Обновляем счётчик проверок
            pair_key = (coin_a, coin_b)
            self.pair_performance[pair_key]['checks'] += 1

            return result

    async def _check_single_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float,
            min_spread: float,
            max_spread: float,
            min_reserve: float
    ) -> Optional[Dict]:
        """
        Проверяет одну пару монет с учетом ВСЕХ комиссий Bybit
        Схема: USDT → CoinA (Bybit + trade fee) → CoinB (BestChange) → USDT (Bybit + trade fee)

        НОВОЕ: Учитываются комиссии на вывод (withdrawal fees)
        ОПТИМИЗИРОВАНО: Добавлена валидация данных, кэширование, ранний выход
        """
        # Проверяем кэш результатов (избегаем повторных проверок)
        cache_key = f"{coin_a}_{coin_b}_{start_amount:.2f}_{min_reserve:.2f}"
        cached_result = self.pair_check_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            # Валидация входных параметров
            if not is_valid_number(start_amount) or start_amount <= 0:
                return None
            
            # Получаем цены на Bybit с валидацией
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)

            if not validate_price(price_a_usdt, f"цена {coin_a}"):
                return None
            if not validate_price(price_b_usdt, f"цена {coin_b}"):
                return None

            # Получаем курс от BestChange
            best_rate = self.bestchange.get_best_rate(coin_a, coin_b, min_reserve)
            if not best_rate:
                return None

            give_rate = best_rate.rankrate
            if not validate_rate(give_rate, f"курс {coin_a}→{coin_b}"):
                return None

            # Инвертируем для получения правильного курса обмена
            exchange_rate = 1.0 / give_rate

            if not validate_rate(exchange_rate, f"обменный курс {coin_a}→{coin_b}"):
                return None

            # === РАСЧЁТ С УЧЁТОМ ВСЕХ КОМИССИЙ BYBIT ===

            # Шаг 1: Покупаем coin_a за USDT на Bybit (Taker 0.18%)
            amount_coin_a_gross = start_amount / price_a_usdt
            
            # Валидация результата деления
            if not is_valid_number(amount_coin_a_gross):
                return None
            
            fee_buy, amount_coin_a = self._calculate_bybit_fees(amount_coin_a_gross, is_taker=True)
            
            # Валидация результатов расчета комиссии
            if not is_valid_number(amount_coin_a) or amount_coin_a <= 0:
                return None

            # Шаг 2: Выводим coin_a с Bybit (withdrawal fee)
            withdraw_fee_a_coin, withdraw_fee_a_usdt, withdraw_chain_a = self._get_withdrawal_fee_in_usdt(
                coin_a, amount_coin_a, price_a_usdt
            )
            amount_coin_a_after_withdraw = amount_coin_a - withdraw_fee_a_coin

            if amount_coin_a_after_withdraw <= 0:
                return None

            # Шаг 3: Обмениваем coin_a на coin_b через BestChange (без комиссии от нас)
            amount_coin_b = self.calculator.convert_amount(amount_coin_a_after_withdraw, exchange_rate)
            
            # Валидация результата конвертации
            if not is_valid_number(amount_coin_b) or amount_coin_b <= 0:
                return None

            # Шаг 4: Вносим coin_b на Bybit (обычно без комиссии, но проверим минимум)
            # Deposit обычно бесплатный, но учитываем минимальную сумму вывода с обменника

            # Шаг 5: Выводим coin_b с обменника на Bybit (может быть комиссия обменника, но обычно включена в курс)

            # Шаг 6: Продаём coin_b за USDT на Bybit (Taker 0.18%)
            usdt_gross = self.calculator.convert_amount(amount_coin_b, price_b_usdt)
            
            # Валидация
            if not is_valid_number(usdt_gross) or usdt_gross <= 0:
                return None
            
            fee_sell, usdt_after_sell = self._calculate_bybit_fees(usdt_gross, is_taker=True)
            
            # Валидация
            if not is_valid_number(usdt_after_sell) or usdt_after_sell <= 0:
                return None

            # Шаг 7: Выводим USDT с Bybit (withdrawal fee) - НЕ УЧИТЫВАЕМ, т.к. конечный результат в USDT на Bybit
            # Если бы выводили USDT, то нужно было бы вычесть комиссию
            final_usdt = usdt_after_sell

            # Общие комиссии Bybit
            total_bybit_trading_fee = fee_buy * price_a_usdt + fee_sell
            total_bybit_withdrawal_fee = withdraw_fee_a_usdt
            total_bybit_fee = total_bybit_trading_fee + total_bybit_withdrawal_fee

            # Проверка лимитов обменника
            if best_rate.give_min > 0 and amount_coin_a_after_withdraw < best_rate.give_min:
                return None
            if best_rate.give_max > 0 and amount_coin_a_after_withdraw > best_rate.give_max:
                return None

            # Расчёт прибыли и спреда с валидацией
            profit = final_usdt - start_amount
            
            # Валидация прибыли
            if not is_valid_number(profit):
                return None
            
            # Проверка деления на ноль
            if start_amount <= 0:
                return None
            
            spread = (profit / start_amount) * 100
            
            # Валидация спреда
            if not is_valid_number(spread) or math.isnan(spread) or math.isinf(spread):
                return None

            # Фильтрация
            if spread < min_spread or spread > max_spread:
                return None
            if abs(spread) > 100:
                return None
            if profit < MIN_PROFIT_USD:
                return None

            # Возвращаем результат
            return {
                'type': 'bestchange_arbitrage',
                'path': f"USDT → {coin_a} → {coin_b} → USDT",
                'scheme': f"Bybit → BestChange → Bybit",
                'coins': [coin_a, coin_b],
                'initial': start_amount,
                'final': final_usdt,
                'profit': profit,
                'spread': spread,
                'exchanger': best_rate.exchanger,
                'exchanger_id': best_rate.exchanger_id,
                'reserve': best_rate.reserve,
                'give_min': best_rate.give_min,
                'give_max': best_rate.give_max,
                'liquidity_a': self.bybit.get_liquidity_score(coin_a, 'USDT'),
                'liquidity_b': self.bybit.get_liquidity_score(coin_b, 'USDT'),
                'volume_a': self.bybit.get_volume_24h(coin_a, 'USDT'),
                'volume_b': self.bybit.get_volume_24h(coin_b, 'USDT'),
                'bybit_url_a': self._get_bybit_trade_url(coin_a),
                'bybit_url_b': self._get_bybit_trade_url(coin_b),
                'bybit_deposit_url': self._get_bybit_deposit_url(),
                'bybit_withdraw_url': self._get_bybit_withdraw_url(),
                'exchanger_url': self._get_bestchange_exchanger_url(best_rate.exchanger_id),
                'bybit_fee_buy': fee_buy * price_a_usdt,
                'bybit_fee_sell': fee_sell,
                'bybit_trading_fee': total_bybit_trading_fee,
                'bybit_withdrawal_fee_a': withdraw_fee_a_usdt,
                'bybit_withdrawal_fee_a_coin': withdraw_fee_a_coin,
                'bybit_withdrawal_chain_a': withdraw_chain_a,
                'bybit_total_fee': total_bybit_fee,
                'steps': [
                    f"1️⃣  Купить {amount_coin_a_gross:.8f} {coin_a} за {start_amount:.2f} USDT на Bybit (цена: ${price_a_usdt:.8f})",
                    f"    💳 Комиссия торговли Bybit (Taker 0.18%): {fee_buy:.8f} {coin_a} (${fee_buy * price_a_usdt:.4f})",
                    f"    ✅ Получено: {amount_coin_a:.8f} {coin_a}",
                    f"2️⃣  Вывести {amount_coin_a:.8f} {coin_a} с Bybit",
                    f"    💳 Комиссия на вывод Bybit ({withdraw_chain_a}): {withdraw_fee_a_coin:.8f} {coin_a} (${withdraw_fee_a_usdt:.4f})",
                    f"    ✅ Выведено: {amount_coin_a_after_withdraw:.8f} {coin_a}",
                    f"3️⃣  Обменять {amount_coin_a_after_withdraw:.8f} {coin_a} → {amount_coin_b:.8f} {coin_b} на {best_rate.exchanger}",
                    f"    📊 Курс GET: 1 {coin_a} = {exchange_rate:.8f} {coin_b}",
                    f"4️⃣  Внести {amount_coin_b:.8f} {coin_b} на Bybit (обычно без комиссии)",
                    f"5️⃣  Продать {amount_coin_b:.8f} {coin_b} за {usdt_gross:.2f} USDT на Bybit (цена: ${price_b_usdt:.8f})",
                    f"    💳 Комиссия торговли Bybit (Taker 0.18%): ${fee_sell:.4f}",
                    f"    ✅ Получено: {final_usdt:.2f} USDT",
                    f"",
                    f"💰 ИТОГО комиссий Bybit:",
                    f"   • Торговые: ${total_bybit_trading_fee:.4f}",
                    f"   • Вывод {coin_a}: ${withdraw_fee_a_usdt:.4f}",
                    f"   • Всего: ${total_bybit_fee:.4f}",
                    f"✅ ЧИСТАЯ ПРИБЫЛЬ: {start_amount:.2f} USDT → {final_usdt:.2f} USDT (+{profit:.2f} USDT, {spread:.4f}%)"
                ],
                'exchange_rate': exchange_rate,
                'give_rate': give_rate,
                'bybit_rate_a': price_a_usdt,
                'bybit_rate_b': price_b_usdt,
                'timestamp': datetime.now().isoformat()
            }
            
            # Сохраняем в кэш перед возвратом
            self.pair_check_cache.put(cache_key, result)
            return result

        except (ZeroDivisionError, ValueError, TypeError, KeyError) as e:
            # Специфичная обработка известных ошибок
            return None
        except Exception:
            # Общая обработка остальных ошибок
            return None

    def _print_opportunity(self, opp: Dict, rank: int):
        """Выводит найденную возможность сразу в консоль"""
        print(f"\n🎯 НАЙДЕНА СВЯЗКА #{rank} через BestChange")
        print(f"   📍 Путь: {opp['path']}")
        print(f"   🔗 Bybit {opp['coins'][0]}/USDT: {opp['bybit_url_a']}")
        print(f"   🔗 Bybit {opp['coins'][1]}/USDT: {opp['bybit_url_b']}")
        print(f"   🔗 Обменник: {opp['exchanger_url']}")
        print(f"   💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
        print(f"   💳 Комиссии Bybit: ${opp['bybit_total_fee']:.4f}")
        print(f"      • Торговые: ${opp['bybit_trading_fee']:.4f}")
        print(
            f"      • Вывод {opp['coins'][0]} ({opp['bybit_withdrawal_chain_a']}): ${opp['bybit_withdrawal_fee_a']:.4f}")
        print(f"   🏦 Обменник: {opp['exchanger']} (резерв: ${opp['reserve']:,.0f})")
        print(
            f"   💧 Ликвидность: {opp['coins'][0]} ({opp['liquidity_a']:.1f}) → {opp['coins'][1]} ({opp['liquidity_b']:.1f})")
        print(f"   📊 Курс GET: 1 {opp['coins'][0]} = {opp['exchange_rate']:.8f} {opp['coins'][1]}")
        print("-" * 100)

    def _update_hot_pairs_cache(self, opportunities: List[Dict]):
        """Обновляет кэш горячих пар с TTL"""
        if not opportunities:
            return
        
        # Оптимизированная сортировка - только по прибыли
        sorted_opps = sorted(opportunities, key=lambda x: x.get('profit', 0), reverse=True)
        
        # Очищаем старые записи
        self.hot_pairs_cache.cleanup_expired()

        # Добавляем новые горячие пары
        added_count = 0
        for opp in sorted_opps[:CACHE_HOT_PAIRS]:
            if 'coins' not in opp or len(opp['coins']) < 2:
                continue
            
            pair = tuple(opp['coins'])
            # Сохраняем как строку для удобства
            cache_key = f"({pair[0]}, {pair[1]})"
            cache_data = {
                'last_spread': opp.get('spread', 0),
                'last_profit': opp.get('profit', 0),
                'last_check': datetime.now()
            }
            
            self.hot_pairs_cache.put(cache_key, cache_data)
            added_count += 1

        print(f"\n[Cache] 🔥 Обновлён кэш: {added_count} горячих пар (размер кэша: {self.hot_pairs_cache.size()})")

    async def analyze_specific_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float = 100.0,
            min_reserve: float = 0
    ) -> Dict:
        """Анализирует конкретную пару монет с учетом всех комиссий"""
        print(f"\n[BestChange Arbitrage] 🔬 Детальный анализ пары {coin_a} → {coin_b}")

        try:
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            if not price_a_usdt:
                return {'error': f'Цена {coin_a} не найдена на Bybit'}

            amount_coin_a = start_amount / price_a_usdt
            print(f"   1. {start_amount} USDT → {amount_coin_a:.8f} {coin_a} (Bybit: ${price_a_usdt:.8f})")

            # Комиссия на вывод
            withdraw_fee_coin, withdraw_fee_usdt, chain = self._get_withdrawal_fee_in_usdt(coin_a, amount_coin_a,
                                                                                           price_a_usdt)
            amount_after_withdraw = amount_coin_a - withdraw_fee_coin
            print(
                f"   1a. Комиссия на вывод {coin_a} ({chain}): {withdraw_fee_coin:.8f} {coin_a} (${withdraw_fee_usdt:.4f})")
            print(f"       После вывода: {amount_after_withdraw:.8f} {coin_a}")

            print(f"   2. Запрос курса {coin_a} → {coin_b} на BestChange...")
            top_rates = self.bestchange.get_top_rates(coin_a, coin_b, top_n=5, min_reserve=min_reserve)

            if not top_rates:
                return {'error': f'BestChange не поддерживает {coin_a} → {coin_b}'}

            print(f"   ✓ Найдено {len(top_rates)} обменников:")
            for idx, rate in enumerate(top_rates, 1):
                get_rate = 1.0 / rate.rankrate if rate.rankrate > 0 else 0
                amount_b = amount_after_withdraw * get_rate
                print(
                    f"      {idx}. {rate.exchanger}: курс GET 1 {coin_a} = {get_rate:.8f} {coin_b} → {amount_b:.8f} {coin_b} (резерв: ${rate.reserve:,.0f})")

            best_rate = top_rates[0]
            get_rate = 1.0 / best_rate.rankrate if best_rate.rankrate > 0 else 0
            amount_coin_b = amount_after_withdraw * get_rate

            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
            if not price_b_usdt:
                return {'error': f'Цена {coin_b} не найдена на Bybit'}

            final_usdt = amount_coin_b * price_b_usdt
            print(f"   3. {amount_coin_b:.8f} {coin_b} → {final_usdt:.2f} USDT (Bybit: ${price_b_usdt:.8f})")

            spread = ((final_usdt - start_amount) / start_amount) * 100
            profit = final_usdt - start_amount

            print(f"\n   ✅ Итог: {spread:.4f}% ({'+' if profit >= 0 else ''}{profit:.2f} USDT)")
            print(f"   🏦 Лучший обменник: {best_rate.exchanger}")
            print(f"   💳 Комиссия на вывод {coin_a}: ${withdraw_fee_usdt:.4f}")

            return {
                'success': True,
                'spread': spread,
                'profit': profit,
                'final_usdt': final_usdt,
                'exchanger': best_rate.exchanger,
                'withdrawal_fee': withdraw_fee_usdt,
                'top_exchangers': [
                    {'name': r.exchanger, 'rate': 1.0 / r.rankrate if r.rankrate > 0 else 0, 'reserve': r.reserve}
                    for r in top_rates
                ]
            }

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return {'error': str(e)}

    def get_hot_pairs(self) -> List[tuple]:
        """Возвращает список горячих пар из кэша"""
        # Очищаем истекшие записи
        self.hot_pairs_cache.cleanup_expired()
        
        hot_pairs = []
        hot_pairs_set = set()  # Для быстрой проверки дубликатов
        
        # Проходим по всем ключам в кэше
        for key in list(self.hot_pairs_cache.cache.keys()):
            cached_data = self.hot_pairs_cache.get(key)
            if cached_data is not None:
                try:
                    pair = None
                    
                    # Ключ хранится как строка вида "(coin_a, coin_b)"
                    if isinstance(key, str):
                        key = key.strip()
                        if key.startswith('(') and key.endswith(')'):
                            # Убираем скобки и разбиваем
                            content = key[1:-1].strip()
                            parts = [p.strip().strip("'\"") for p in content.split(',')]
                            if len(parts) == 2:
                                pair = (parts[0], parts[1])
                    elif isinstance(key, tuple) and len(key) == 2:
                        # Если ключ уже tuple
                        pair = key
                    
                    # Добавляем если валидная пара и еще не добавлена
                    if pair and isinstance(pair, tuple) and len(pair) == 2:
                        if pair not in hot_pairs_set:
                            hot_pairs.append(pair)
                            hot_pairs_set.add(pair)
                except Exception:
                    continue
        
        return hot_pairs

    def get_pair_statistics(self) -> Dict:
        """Возвращает статистику по парам"""
        stats = {
            'total_pairs_checked': len(self.pair_performance),
            'hot_pairs_cached': len(self.hot_pairs_cache),
            'top_performers': []
        }

        sorted_pairs = sorted(
            self.pair_performance.items(),
            key=lambda x: x[1]['finds'] / max(x[1]['checks'], 1),
            reverse=True
        )[:10]

        for pair, perf in sorted_pairs:
            stats['top_performers'].append({
                'pair': f"{pair[0]} → {pair[1]}",
                'finds': perf['finds'],
                'checks': perf['checks'],
                'success_rate': perf['finds'] / max(perf['checks'], 1) * 100,
                'avg_spread': perf['avg_spread']
            })

        return stats