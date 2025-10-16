import gzip
import requests
from typing import Dict, List, Set
from io import BytesIO
from configs import Config


class BestChangeHandler:
    """Парсер данных BestChange с умным сопоставлением тикеров"""

    def __init__(self):
        self.base_url = "https://api.bestchange.ru/info.zip"
        self.currencies = {}  # id -> полное название
        self.currency_tickers = {}  # id -> тикер (BTC, ETH...)
        self.exchangers = {}
        self.rates = []

    def _download_data(self) -> bytes:
        """Загружает ZIP файл с данными"""
        try:
            print("[BestChange] Подключение к API...")
            response = requests.get(
                self.base_url,
                timeout=Config.REQUEST_TIMEOUT,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            response.raise_for_status()
            print("[BestChange] ✓ Данные получены")
            return response.content
        except requests.exceptions.Timeout:
            print(f"[BestChange] ✗ Таймаут подключения ({Config.REQUEST_TIMEOUT}s)")
            raise
        except requests.exceptions.RequestException as e:
            print(f"[BestChange] ✗ Ошибка подключения: {e}")
            raise

    def load_data(self, bybit_tickers: Set[str] = None):
        """
        Загружает данные BestChange и сопоставляет с тикерами Bybit

        Args:
            bybit_tickers: Множество тикеров из Bybit (например, {'BTC', 'ETH', 'USDT'})
        """
        print("[BestChange] Загрузка данных...")
        raw = self._download_data()

        with gzip.GzipFile(fileobj=BytesIO(raw)) as gz:
            content = gz.read().decode("utf-8", errors="ignore")

        sections = content.split("##########")

        if len(sections) < 4:
            raise ValueError("Неверный формат данных от BestChange")

        # ═══════════════════════════════════════════════════════════
        # ШАГ 1: Парсим валюты и извлекаем тикеры
        # ═══════════════════════════════════════════════════════════
        currencies_text = sections[1]
        for line in currencies_text.strip().splitlines():
            parts = line.split(";")
            if len(parts) >= 3:
                cid = int(parts[0])
                name = parts[2].strip()
                self.currencies[cid] = name

                # Извлекаем тикер из названия
                ticker = self._extract_ticker(name, bybit_tickers)
                if ticker:
                    self.currency_tickers[cid] = ticker

        print(f"[BestChange] ✓ Валют загружено: {len(self.currencies)}")
        print(f"[BestChange] ✓ Распознано криптовалют: {len(self.currency_tickers)}")

        # Показываем примеры распознанных тикеров
        if self.currency_tickers:
            sample = list(self.currency_tickers.values())[:20]
            print(f"[BestChange] Примеры распознанных: {', '.join(sorted(set(sample)))}")

        # ═══════════════════════════════════════════════════════════
        # ШАГ 2: Парсим обменники
        # ═══════════════════════════════════════════════════════════
        exchangers_text = sections[2]
        for line in exchangers_text.strip().splitlines():
            parts = line.split(";")
            if len(parts) >= 2:
                eid = int(parts[0])
                name = parts[1].strip()
                self.exchangers[eid] = name

        print(f"[BestChange] ✓ Обменников: {len(self.exchangers)}")

        # ═══════════════════════════════════════════════════════════
        # ШАГ 3: Парсим курсы обмена
        # ═══════════════════════════════════════════════════════════
        rates_text = sections[3]
        crypto_rates = 0

        for line in rates_text.strip().splitlines():
            parts = line.split(";")
            if len(parts) >= 6:
                try:
                    from_id = int(parts[0])
                    to_id = int(parts[1])

                    # Проверяем что обе валюты распознаны как крипто
                    if from_id not in self.currency_tickers or to_id not in self.currency_tickers:
                        continue

                    rate = float(parts[2]) if parts[2] else 0.0
                    if rate <= 0:
                        continue

                    rate_data = {
                        "from_id": from_id,
                        "to_id": to_id,
                        "from_ticker": self.currency_tickers[from_id],
                        "to_ticker": self.currency_tickers[to_id],
                        "rate": rate,
                        "give": float(parts[3]) if parts[3] else 0.0,
                        "exchanger_id": int(parts[4]),
                        "reserve": float(parts[5]) if parts[5] else 0.0,
                    }

                    self.rates.append(rate_data)
                    crypto_rates += 1

                except (ValueError, IndexError):
                    continue

        print(f"[BestChange] ✓ Крипто-крипто курсов: {crypto_rates}")

    def _extract_ticker(self, currency_name: str, bybit_tickers: Set[str] = None) -> str:
        """
        Извлекает тикер криптовалюты из названия BestChange.

        Примеры названий в BestChange:
        - "Bitcoin BTC"
        - "Tether TRC20 USDT"
        - "Ethereum ETH"
        - "BNB Smart Chain BNB BEP20"

        Стратегия:
        1. Если передан список тикеров Bybit - ищем точное совпадение
        2. Ищем известные паттерны в конце строки
        3. Ищем известные криптовалюты в любом месте
        """
        name_upper = currency_name.upper()

        # Если есть список тикеров Bybit - приоритет точному совпаденю
        if bybit_tickers:
            for ticker in bybit_tickers:
                # Ищем ticker как отдельное слово (не часть другого слова)
                if f" {ticker} " in f" {name_upper} " or name_upper.endswith(f" {ticker}"):
                    return ticker

        # Известные паттерны в конце названия
        # Пример: "Bitcoin BTC" -> BTC
        words = name_upper.split()
        if len(words) >= 2:
            last_word = words[-1]
            # Проверяем что последнее слово похоже на тикер (2-5 символов, заглавные)
            if 2 <= len(last_word) <= 5 and last_word.isalpha():
                if bybit_tickers is None or last_word in bybit_tickers:
                    return last_word

        # Список всех известных криптовалют (расширенный)
        known_cryptos = {
            # Топ по капитализации
            'BTC', 'ETH', 'USDT', 'BNB', 'XRP', 'USDC', 'ADA', 'DOGE', 'SOL', 'TRX',
            'DOT', 'MATIC', 'LTC', 'SHIB', 'AVAX', 'DAI', 'LINK', 'BCH', 'XLM', 'UNI',
            'ATOM', 'XMR', 'ETC', 'ICP', 'FIL', 'APT', 'VET', 'ALGO', 'HBAR', 'QNT',
            'NEAR', 'GRT', 'AAVE', 'MKR', 'SAND', 'MANA', 'AXS', 'EGLD', 'THETA', 'FTM',
            'RUNE', 'ZEC', 'DASH', 'XTZ', 'EOS', 'NEO', 'IOTA', 'BSV', 'WAVES', 'KSM',
            # Популярные альткоины
            'ARB', 'OP', 'TON', 'PEPE', 'INJ', 'TIA', 'SEI', 'SUI', 'ORDI', 'STX',
            'IMX', 'RNDR', 'FTM', 'BONK', 'WIF', 'PYTH', 'JUP', 'DYM', 'STRK',
            # Стейблкоины
            'TUSD', 'BUSD', 'USDD', 'FRAX', 'USDP',
            # DeFi
            'CRV', 'SNX', 'COMP', 'YFI', '1INCH', 'SUSHI', 'BAL', 'LDO',
            # Layer 2
            'MATIC', 'IMX', 'LRC', 'METIS',
            # Мемкоины
            'DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK',
        }

        # Ищем в любом месте строки
        for crypto in known_cryptos:
            if crypto in name_upper:
                # Дополнительная проверка для коротких тикеров (2-3 символа)
                if len(crypto) <= 3:
                    # Проверяем что это отдельное слово
                    if f" {crypto} " in f" {name_upper} " or name_upper.startswith(crypto + " ") or name_upper.endswith(
                            " " + crypto):
                        return crypto
                else:
                    return crypto

        return ""

    def get_crypto_to_crypto_pairs(self) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Возвращает словарь криптовалютных пар.

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
                    },
                    ...
                ],
                'USDT': [...]
            }
        }
        """
        crypto_pairs = {}

        for rate in self.rates:
            from_ticker = rate['from_ticker']
            to_ticker = rate['to_ticker']

            # Пропускаем обмены валюты на саму себя
            if from_ticker == to_ticker:
                continue

            # Создаём структуру
            if from_ticker not in crypto_pairs:
                crypto_pairs[from_ticker] = {}

            if to_ticker not in crypto_pairs[from_ticker]:
                crypto_pairs[from_ticker][to_ticker] = []

            # Получаем название обменника
            exchanger_name = self.exchangers.get(
                rate['exchanger_id'],
                f"Exchanger #{rate['exchanger_id']}"
            )

            # Добавляем предложение
            crypto_pairs[from_ticker][to_ticker].append({
                'rate': rate['rate'],
                'exchanger': exchanger_name,
                'exchanger_id': rate['exchanger_id'],
                'reserve': rate['reserve'],
                'give': rate['give'],
            })

        # Сортируем предложения по курсу (лучший первым)
        for from_crypto in crypto_pairs:
            for to_crypto in crypto_pairs[from_crypto]:
                crypto_pairs[from_crypto][to_crypto].sort(
                    key=lambda x: x['rate'],
                    reverse=True
                )

        total_directions = sum(len(v) for v in crypto_pairs.values())
        total_offers = sum(
            sum(len(offers) for offers in directions.values())
            for directions in crypto_pairs.values()
        )

        print(f"[BestChange] ✓ Уникальных пар: {total_directions}")
        print(f"[BestChange] ✓ Всего предложений: {total_offers}")

        # Показываем примеры
        if crypto_pairs:
            sample_pairs = []
            for from_crypto in list(crypto_pairs.keys())[:5]:
                for to_crypto in list(crypto_pairs[from_crypto].keys())[:2]:
                    sample_pairs.append(f"{from_crypto}→{to_crypto}")
            if sample_pairs:
                print(f"[BestChange] Примеры пар: {', '.join(sample_pairs)}")

        return crypto_pairs

    def update_data(self, bybit_tickers: Set[str] = None) -> bool:
        """Обновляет данные с учётом тикеров Bybit"""
        try:
            self.load_data(bybit_tickers)
            return True
        except Exception as e:
            print(f"[BestChange] ✗ Ошибка обновления данных: {e}")
            return False