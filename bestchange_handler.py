import requests
from typing import Dict, List, Set, Optional
from configs import Config


class BestChangeHandler:
    """Обработчик BestChange API v2.0 с сопоставлением тикеров Bybit"""

    def __init__(self):
        self.api_key = Config.BESTCHANGE_API_KEY
        if not self.api_key:
            raise ValueError("BESTCHANGE_API_KEY не найден в .env файле!")

        self.base_url = "https://bestchange.app"
        self.lang = "en"  # Используем английский для лучшего сопоставления

        self.currencies = {}  # id -> полная информация о валюте
        self.currency_tickers = {}  # id -> тикер (BTC, ETH...)
        self.ticker_to_id = {}  # тикер -> id
        self.changers = {}  # id -> название обменника
        self.rates_cache = {}  # кеш курсов

    def _make_request(self, endpoint: str) -> Optional[Dict]:
        """Выполняет запрос к API BestChange"""
        url = f"{self.base_url}/v2/{self.api_key}/{endpoint}"

        try:
            response = requests.get(
                url,
                headers={
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip',
                    'User-Agent': 'Mozilla/5.0'
                },
                timeout=Config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"[BestChange] ✗ Ошибка запроса {endpoint}: {e}")
            return None

    def load_data(self, bybit_tickers: Set[str] = None):
        """
        Загружает данные из BestChange API v2.0

        Args:
            bybit_tickers: Множество тикеров из Bybit для сопоставления
        """
        print("[BestChange] Загрузка данных через API v2.0...")

        # ═══════════════════════════════════════════════════════════
        # ШАГ 1: Загружаем список валют
        # ═══════════════════════════════════════════════════════════
        print("[BestChange] Загрузка валют...")
        currencies_data = self._make_request(f"currencies/{self.lang}")

        if not currencies_data or 'currencies' not in currencies_data:
            raise ValueError("Не удалось загрузить список валют")

        # Обрабатываем валюты
        for currency in currencies_data['currencies']:
            cid = currency['id']
            self.currencies[cid] = currency

            # Извлекаем тикер
            ticker = self._extract_ticker(currency, bybit_tickers)
            if ticker:
                self.currency_tickers[cid] = ticker
                self.ticker_to_id[ticker] = cid

        print(f"[BestChange] ✓ Валют загружено: {len(self.currencies)}")
        print(f"[BestChange] ✓ Распознано криптовалют: {len(self.currency_tickers)}")

        # Показываем распознанные тикеры
        if self.currency_tickers:
            recognized = sorted(set(self.currency_tickers.values()))[:25]
            print(f"[BestChange] Распознанные тикеры: {', '.join(recognized)}")

        # ═══════════════════════════════════════════════════════════
        # ШАГ 2: Загружаем список обменников
        # ═══════════════════════════════════════════════════════════
        print("[BestChange] Загрузка обменников...")
        changers_data = self._make_request(f"changers/{self.lang}")

        if changers_data and 'changers' in changers_data:
            for changer in changers_data['changers']:
                if changer.get('active', False):  # Только активные
                    self.changers[changer['id']] = changer['name']

            print(f"[BestChange] ✓ Активных обменников: {len(self.changers)}")

    def _extract_ticker(self, currency: Dict, bybit_tickers: Set[str] = None) -> str:
        """
        Извлекает тикер из данных валюты BestChange

        Поля валюты:
        - code: короткий код (например "BTC", "ETHBEP20")
        - viewname: отображаемое имя (например "BTC", "ETH BEP20")
        - name: полное имя (например "Bitcoin", "Ethereum BEP20")
        - crypto: True если криптовалюта
        """
        # Только криптовалюты
        if not currency.get('crypto', False):
            return ""

        name = currency.get('name', '').upper()
        code = currency.get('code', '').upper()
        viewname = currency.get('viewname', '').upper()

        # Приоритет 1: Точное совпадение с Bybit тикерами
        if bybit_tickers:
            # Проверяем code
            if code in bybit_tickers:
                return code

            # Извлекаем базовый тикер из code (например ETHBEP20 -> ETH)
            for ticker in bybit_tickers:
                if code.startswith(ticker) and len(ticker) >= 3:
                    return ticker

            # Ищем в viewname
            for ticker in bybit_tickers:
                if ticker in viewname.split():
                    return ticker

        # Приоритет 2: Известные криптовалюты
        known_cryptos = {
            'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE',
            'DOT', 'MATIC', 'LTC', 'SHIB', 'AVAX', 'TRX', 'LINK', 'BCH', 'XLM',
            'UNI', 'ATOM', 'XMR', 'ETC', 'FIL', 'APT', 'NEAR', 'ARB', 'OP',
            'TON', 'DAI', 'BUSD', 'TUSD', 'XTZ', 'ALGO', 'VET', 'ICP', 'HBAR',
            'QNT', 'GRT', 'AAVE', 'MKR', 'SAND', 'MANA', 'AXS', 'THETA', 'FTM'
        }

        # Проверяем code на известные тикеры
        for crypto in known_cryptos:
            if code == crypto or code.startswith(crypto):
                return crypto

        # Проверяем viewname
        viewname_parts = viewname.split()
        for part in viewname_parts:
            if part in known_cryptos:
                return part

        # Приоритет 3: Первое слово из viewname (если короткое)
        if viewname_parts and 2 <= len(viewname_parts[0]) <= 5:
            first_word = viewname_parts[0]
            if first_word.isalpha():
                return first_word

        return ""

    def get_crypto_to_crypto_pairs(self) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Возвращает словарь криптовалютных пар с курсами обмена

        Структура:
        {
            'BTC': {
                'ETH': [
                    {
                        'rate': 15.5,
                        'exchanger': 'Exchanger Name',
                        'exchanger_id': 123,
                        'reserve': 100.5,
                        'give': 0.01,
                        'receive': 15.5
                    },
                    ...
                ]
            }
        }
        """
        print("\n[BestChange] Загрузка курсов обмена...")

        crypto_pairs = {}
        total_requests = 0
        total_rates = 0

        # Получаем все распознанные криптовалюты
        crypto_ids = list(self.currency_tickers.keys())

        print(f"[BestChange] Проверка направлений для {len(crypto_ids)} криптовалют...")

        # Для каждой криптовалюты проверяем доступные направления
        for from_id in crypto_ids:
            from_ticker = self.currency_tickers[from_id]

            # Получаем доступные направления (пары) для этой валюты
            presences = self._make_request(f"presences/{from_id}-0")

            if not presences or 'presences' not in presences:
                continue

            total_requests += 1

            # Собираем пары для пакетного запроса (до 500 пар)
            pair_list = []
            valid_targets = {}  # to_id -> to_ticker

            for presence in presences['presences']:
                pair_str = presence['pair']
                parts = pair_str.split('-')

                if len(parts) >= 2:
                    to_id = int(parts[1])

                    # Проверяем что целевая валюта тоже криптовалюта
                    if to_id in self.currency_tickers:
                        to_ticker = self.currency_tickers[to_id]

                        # Не меняем валюту на саму себя
                        if from_ticker != to_ticker:
                            pair_list.append(pair_str)
                            valid_targets[to_id] = to_ticker

            if not pair_list:
                continue

            # Делаем пакетный запрос курсов (максимум 500 пар)
            batch_size = 500
            for i in range(0, len(pair_list), batch_size):
                batch = pair_list[i:i + batch_size]
                pair_string = '+'.join(batch)

                rates_data = self._make_request(f"rates/{pair_string}")

                if not rates_data or 'rates' not in rates_data:
                    continue

                total_requests += 1

                # Обрабатываем полученные курсы
                for pair_id, rates_list in rates_data['rates'].items():
                    parts = pair_id.split('-')
                    if len(parts) < 2:
                        continue

                    to_id = int(parts[1])
                    to_ticker = valid_targets.get(to_id)

                    if not to_ticker:
                        continue

                    # Создаём структуру
                    if from_ticker not in crypto_pairs:
                        crypto_pairs[from_ticker] = {}

                    if to_ticker not in crypto_pairs[from_ticker]:
                        crypto_pairs[from_ticker][to_ticker] = []

                    # Добавляем предложения от обменников
                    for rate_data in rates_list:
                        exchanger_id = rate_data['changer']
                        exchanger_name = self.changers.get(
                            exchanger_id,
                            f"Exchanger #{exchanger_id}"
                        )

                        try:
                            offer = {
                                'rate': float(rate_data['rate']),
                                'exchanger': exchanger_name,
                                'exchanger_id': exchanger_id,
                                'reserve': float(rate_data.get('reserve', 0)),
                                'give': float(rate_data.get('inmin', 0)),
                                'receive': 0  # Рассчитается при использовании
                            }

                            # Пропускаем нулевые или отрицательные курсы
                            if offer['rate'] <= 0:
                                continue

                            crypto_pairs[from_ticker][to_ticker].append(offer)
                            total_rates += 1

                        except (ValueError, TypeError):
                            continue

            # Показываем прогресс
            if total_requests % 10 == 0:
                print(f"[BestChange] Обработано {total_requests} запросов, найдено {total_rates} курсов...")

        # Сортируем предложения по курсу (лучший первым)
        for from_ticker in crypto_pairs:
            for to_ticker in crypto_pairs[from_ticker]:
                crypto_pairs[from_ticker][to_ticker].sort(
                    key=lambda x: x['rate'],
                    reverse=True
                )

        # Статистика
        total_directions = sum(len(v) for v in crypto_pairs.values())

        print(f"\n[BestChange] ✓ API запросов: {total_requests}")
        print(f"[BestChange] ✓ Уникальных направлений: {total_directions}")
        print(f"[BestChange] ✓ Всего предложений: {total_rates}")

        # Показываем примеры
        if crypto_pairs:
            sample_pairs = []
            for from_ticker in list(crypto_pairs.keys())[:5]:
                for to_ticker in list(crypto_pairs[from_ticker].keys())[:3]:
                    count = len(crypto_pairs[from_ticker][to_ticker])
                    sample_pairs.append(f"{from_ticker}→{to_ticker}({count})")

            if sample_pairs:
                print(f"[BestChange] Примеры: {', '.join(sample_pairs)}")

        return crypto_pairs

    def update_data(self, bybit_tickers: Set[str] = None) -> bool:
        """Обновляет данные с учётом тикеров Bybit"""
        try:
            self.load_data(bybit_tickers)
            return True
        except Exception as e:
            print(f"[BestChange] ✗ Ошибка обновления: {e}")
            return False