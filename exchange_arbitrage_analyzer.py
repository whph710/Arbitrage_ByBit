import asyncio
from typing import List, Dict, Optional
from datetime import datetime


class SimpleExchangeAnalyzer:
    """
    Простой анализатор арбитража через один обменник
    Схема: Bybit (купить A) → Exchange (обменять A→B) → Bybit (продать B)
    """

    def __init__(self, bybit_client, exchange_client, exchange_name: str):
        self.bybit = bybit_client
        self.exchange = exchange_client
        self.exchange_name = exchange_name
        self.found_count = 0
        self.checked_pairs = 0

    async def find_opportunities(
            self,
            start_amount: float = 100.0,
            min_spread: float = 0.3,
            max_pairs: int = 100,
            parallel_requests: int = 10
    ) -> List[Dict]:
        """
        Ищет простые арбитражные связки через один обменник
        """
        print(f"\n[{self.exchange_name}] 🔍 Начало поиска связок...")
        print(f"[{self.exchange_name}] Параметры: ${start_amount}, мин. спред {min_spread}%")
        print(f"[{self.exchange_name}] ⚡ Параллельных запросов: {parallel_requests}")

        opportunities = []

        # Находим общие монеты между Bybit и обменником
        common_coins = self.exchange.get_common_currencies(self.bybit.coins)

        if not common_coins:
            print(f"[{self.exchange_name}] ❌ Нет общих монет с Bybit")
            return opportunities

        common_coins_list = sorted(list(common_coins))[:max_pairs]

        # Создаём все возможные пары для проверки
        all_pairs = []
        for coin_a in common_coins_list:
            for coin_b in common_coins_list:
                if coin_a != coin_b:
                    all_pairs.append((coin_a, coin_b))

        total_pairs = len(all_pairs)
        print(f"\n[{self.exchange_name}] 📦 Всего пар для проверки: {total_pairs}")
        print(f"[{self.exchange_name}] 💡 Результаты выводятся по мере обнаружения...")
        print("=" * 100)

        self.checked_pairs = 0
        self.found_count = 0

        # Обрабатываем пары пакетами (параллельно)
        semaphore = asyncio.Semaphore(parallel_requests)
        tasks = []

        for coin_a, coin_b in all_pairs:
            task = self._check_pair_with_semaphore(
                semaphore, coin_a, coin_b, start_amount, min_spread
            )
            tasks.append(task)

        # Запускаем все задачи параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Собираем результаты
        for result in results:
            if isinstance(result, dict) and 'spread' in result:
                opportunities.append(result)
                self.found_count += 1
                self._print_opportunity(result, self.found_count)

        print("=" * 100)
        print(f"\n[{self.exchange_name}] ✅ Проверка завершена!")
        print(f"[{self.exchange_name}] 📊 Проверено пар: {self.checked_pairs}")
        print(f"[{self.exchange_name}] 🎯 Найдено связок: {self.found_count}")
        print(f"[{self.exchange_name}] ❌ Недоступных пар: {self.exchange.get_failed_pairs_count()}")

        # Сортируем по спреду
        opportunities.sort(key=lambda x: x['spread'], reverse=True)

        return opportunities

    async def _check_pair_with_semaphore(
            self,
            semaphore: asyncio.Semaphore,
            coin_a: str,
            coin_b: str,
            start_amount: float,
            min_spread: float
    ):
        """Проверяет одну пару с ограничением параллелизма"""
        async with semaphore:
            self.checked_pairs += 1

            # Показываем прогресс каждые 100 пар (компактно)
            if self.checked_pairs % 100 == 0:
                print(f"[{self.exchange_name}] 📊 Прогресс: {self.checked_pairs}/9900 | Найдено: {self.found_count}")

            return await self._check_single_pair(coin_a, coin_b, start_amount, min_spread)

    async def _check_single_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float,
            min_spread: float
    ) -> Optional[Dict]:
        """
        Проверяет одну пару монет
        Схема: USDT → CoinA (Bybit) → CoinB (Exchange) → USDT (Bybit)
        """
        try:
            # Шаг 1: USDT → CoinA на Bybit
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            if not price_a_usdt or price_a_usdt <= 0:
                return None

            amount_coin_a = start_amount / price_a_usdt

            # Шаг 2: CoinA → CoinB на обменнике
            pair_key = f"{coin_a}_{coin_b}"

            # Быстрая проверка кэша неудачных пар
            if pair_key in self.exchange.failed_pairs:
                return None

            exchange_result = await self.exchange.get_estimated_amount(
                from_currency=coin_a,
                to_currency=coin_b,
                from_amount=amount_coin_a
            )

            if not exchange_result or exchange_result.get('to_amount', 0) <= 0:
                return None

            amount_coin_b = exchange_result['to_amount']

            # Проверяем адекватность курса
            if amount_coin_b <= 0 or amount_coin_a <= 0:
                return None

            exchange_rate = amount_coin_b / amount_coin_a

            # Шаг 3: CoinB → USDT на Bybit
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
            if not price_b_usdt or price_b_usdt <= 0:
                return None

            final_usdt = amount_coin_b * price_b_usdt

            # Рассчитываем спред
            spread = ((final_usdt - start_amount) / start_amount) * 100

            # Фильтруем нереалистичные спреды
            if spread > 50.0 or spread < -50.0:
                return None

            # Дополнительная валидация (проверка адекватности курса)
            expected_price_b = price_a_usdt / exchange_rate
            price_deviation = abs(expected_price_b - price_b_usdt) / price_b_usdt * 100

            if price_deviation > 100:  # Если отклонение больше 100%, что-то не так
                return None

            if spread >= min_spread:
                return {
                    'type': 'simple_exchange_arbitrage',
                    'path': f"USDT → {coin_a} → {coin_b} → USDT",
                    'scheme': f"Bybit → {self.exchange_name} → Bybit",
                    'coins': [coin_a, coin_b],
                    'exchange_used': self.exchange_name,
                    'initial': start_amount,
                    'final': final_usdt,
                    'profit': final_usdt - start_amount,
                    'spread': spread,
                    'steps': [
                        f"1️⃣  Купить {amount_coin_a:.8f} {coin_a} за {start_amount:.2f} USDT на Bybit (курс: ${price_a_usdt:.8f})",
                        f"2️⃣  Перевести {amount_coin_a:.8f} {coin_a} с Bybit на {self.exchange_name}",
                        f"3️⃣  Обменять {amount_coin_a:.8f} {coin_a} → {amount_coin_b:.8f} {coin_b} на {self.exchange_name} (курс: {exchange_rate:.8f})",
                        f"4️⃣  Продать {amount_coin_b:.8f} {coin_b} за {final_usdt:.2f} USDT на Bybit (курс: ${price_b_usdt:.8f})",
                        f"✅ ИТОГ: {start_amount:.2f} USDT → {final_usdt:.2f} USDT (+{final_usdt - start_amount:.2f} USDT, {spread:.4f}%)"
                    ],
                    'exchange_rate': exchange_rate,
                    'bybit_rate_a': price_a_usdt,
                    'bybit_rate_b': price_b_usdt,
                    'timestamp': datetime.now().isoformat()
                }

            return None

        except Exception as e:
            # Тихо игнорируем ошибки
            return None

    def _print_opportunity(self, opp: Dict, rank: int):
        """Выводит найденную возможность сразу в консоль"""
        print(f"\n🎯 НАЙДЕНА СВЯЗКА #{rank} через {self.exchange_name}")
        print(f"   📍 Путь: {opp['path']}")
        print(f"   💰 Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}")
        print(f"   📊 Детальный расчёт:")
        print(f"      1️⃣  {opp['initial']:.2f} USDT → {opp['initial'] / opp['bybit_rate_a']:.8f} {opp['coins'][0]}")
        print(f"         (Bybit: 1 {opp['coins'][0]} = ${opp['bybit_rate_a']:.8f})")
        print(
            f"      2️⃣  {opp['initial'] / opp['bybit_rate_a']:.8f} {opp['coins'][0]} → {(opp['initial'] / opp['bybit_rate_a']) * opp['exchange_rate']:.8f} {opp['coins'][1]}")
        print(f"         ({self.exchange_name}: 1 {opp['coins'][0]} = {opp['exchange_rate']:.8f} {opp['coins'][1]})")
        print(
            f"      3️⃣  {(opp['initial'] / opp['bybit_rate_a']) * opp['exchange_rate']:.8f} {opp['coins'][1]} → {opp['final']:.2f} USDT")
        print(f"         (Bybit: 1 {opp['coins'][1]} = ${opp['bybit_rate_b']:.8f})")
        print(f"   ✅ Итог: ${opp['initial']:.2f} → ${opp['final']:.2f} (+${opp['profit']:.4f})")
        print("-" * 100)

    async def analyze_specific_pair(
            self,
            coin_a: str,
            coin_b: str,
            start_amount: float = 100.0
    ) -> Dict:
        """Анализирует конкретную пару монет"""
        print(f"\n[{self.exchange_name}] 🔬 Детальный анализ пары {coin_a} → {coin_b}")

        try:
            # Шаг 1: USDT → CoinA на Bybit
            price_a_usdt = self.bybit.usdt_pairs.get(coin_a)
            if not price_a_usdt:
                return {'error': f'Цена {coin_a} не найдена на Bybit'}

            amount_coin_a = start_amount / price_a_usdt
            print(f"   1. {start_amount} USDT → {amount_coin_a:.8f} {coin_a} (Bybit: ${price_a_usdt:.8f})")

            # Шаг 2: CoinA → CoinB на обменнике
            print(f"   2. Запрос курса {coin_a} → {coin_b} на {self.exchange_name}...")

            exchange_result = await self.exchange.get_estimated_amount(
                from_currency=coin_a,
                to_currency=coin_b,
                from_amount=amount_coin_a
            )

            if not exchange_result:
                return {'error': f'{self.exchange_name} не поддерживает {coin_a} → {coin_b}'}

            amount_coin_b = exchange_result['to_amount']
            exchange_rate = amount_coin_b / amount_coin_a
            print(f"   ✓ {amount_coin_a:.8f} {coin_a} → {amount_coin_b:.8f} {coin_b} (курс: {exchange_rate:.8f})")

            # Шаг 3: CoinB → USDT на Bybit
            price_b_usdt = self.bybit.usdt_pairs.get(coin_b)
            if not price_b_usdt:
                return {'error': f'Цена {coin_b} не найдена на Bybit'}

            final_usdt = amount_coin_b * price_b_usdt
            print(f"   3. {amount_coin_b:.8f} {coin_b} → {final_usdt:.2f} USDT (Bybit: ${price_b_usdt:.8f})")

            spread = ((final_usdt - start_amount) / start_amount) * 100
            profit = final_usdt - start_amount

            print(f"\n   ✅ Итог: {spread:.4f}% ({'+' if profit >= 0 else ''}{profit:.2f} USDT)")

            return {
                'success': True,
                'spread': spread,
                'profit': profit,
                'final_usdt': final_usdt,
                'exchange': self.exchange_name
            }

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return {'error': str(e)}