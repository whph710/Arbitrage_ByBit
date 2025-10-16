import requests
import zipfile
import io
from typing import Dict, List, Optional
from datetime import datetime
from configs import Config


class BestChangeHandler:
    """Обработчик данных BestChange"""

    def __init__(self):
        self.base_url = Config.BESTCHANGE_API_URL
        self.currencies = {}  # {id: name}
        self.exchangers = {}  # {id: name}
        self.rates = []
        self.last_update = None

        # Маппинг полных названий к тикерам
        self.crypto_mapping = {
            'BITCOIN': 'BTC',
            'ETHEREUM': 'ETH',
            'TETHER': 'USDT',
            'RIPPLE': 'XRP',
            'LITECOIN': 'LTC',
            'CARDANO': 'ADA',
            'DOGECOIN': 'DOGE',
            'POLKADOT': 'DOT',
            'BINANCE COIN': 'BNB',
            'STELLAR': 'XLM',
            'CHAINLINK': 'LINK',
            'UNISWAP': 'UNI',
            'SOLANA': 'SOL',
            'POLYGON': 'MATIC',
            'AVALANCHE': 'AVAX',
            'COSMOS': 'ATOM',
            'MONERO': 'XMR',
            'TRON': 'TRX',
            'DASH': 'DASH',
            'ZCASH': 'ZEC',
            'TEZOS': 'XTZ',
            'NEO': 'NEO',
            'MAKER': 'MKR',
            'AAVE': 'AAVE',
            'ALGORAND': 'ALGO',
            'EOS': 'EOS',
            'FILECOIN': 'FIL',
            'BITCOIN CASH': 'BCH',
            'ETHEREUM CLASSIC': 'ETC',
            'VECHAIN': 'VET',
            'THETA': 'THETA',
            'ELROND': 'EGLD',
            'KUSAMA': 'KSM',
            'SHIBA INU': 'SHIB',
            'FANTOM': 'FTM',
            'NEAR': 'NEAR',
            'HARMONY': 'ONE',
            'HEDERA': 'HBAR',
            'DECENTRALAND': 'MANA',
            'SANDBOX': 'SAND',
            'AXIE INFINITY': 'AXS',
            'APECOIN': 'APE',
            'OPTIMISM': 'OP',
            'ARBITRUM': 'ARB',
            'INJECTIVE': 'INJ',
            'SUI': 'SUI',
            'PEPE': 'PEPE',
            'STACKS': 'STX',
            'TON': 'TON',
            'TELEGRAM': 'TON',
        }

    def update_data(self) -> bool:
        """Загружает свежие данные с BestChange"""
        try:
            print("[BestChange] Загрузка данных...")

            response = requests.get(self.base_url, timeout=15)
            response.raise_for_status()

            self.currencies.clear()
            self.exchangers.clear()
            self.rates.clear()

            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                # Используем windows-1251 для кириллицы
                with zip_file.open('bm_cy.dat') as f:
                    self._parse_currencies(f.read().decode('windows-1251'))

                with zip_file.open('bm_exch.dat') as f:
                    self._parse_exchangers(f.read().decode('windows-1251'))

                with zip_file.open('bm_rates.dat') as f:
                    self._parse_rates(f.read().decode('windows-1251'))

            self.last_update = datetime.now()

            print(f"[BestChange] ✓ Загружено:")
            print(f"  • Валют: {len(self.currencies)}")
            print(f"  • Обменников: {len(self.exchangers)}")
            print(f"  • Курсов: {len(self.rates)}")

            return True

        except Exception as e:
            print(f"[BestChange] ✗ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _parse_currencies(self, data: str):
        """Парсит файл с валютами"""
        for line in data.strip().split('\n'):
            if not line:
                continue
            parts = line.split(';')
            if len(parts) >= 2:
                try:
                    currency_id = int(parts[0])
                    currency_name = parts[1]
                    self.currencies[currency_id] = currency_name
                except (ValueError, IndexError):
                    continue

    def _parse_exchangers(self, data: str):
        """Парсит файл с обменниками"""
        for line in data.strip().split('\n'):
            if not line:
                continue
            parts = line.split(';')
            if len(parts) >= 2:
                try:
                    exchanger_id = int(parts[0])
                    exchanger_name = parts[1]
                    self.exchangers[exchanger_id] = exchanger_name
                except (ValueError, IndexError):
                    continue

    def _parse_rates(self, data: str):
        """Парсит файл с курсами обмена"""
        for line in data.strip().split('\n'):
            if not line:
                continue
            parts = line.split(';')
            if len(parts) >= 5:
                try:
                    self.rates.append({
                        'from_id': int(parts[0]),
                        'to_id': int(parts[1]),
                        'exchanger_id': int(parts[2]),
                        'give': float(parts[3]),
                        'receive': float(parts[4]),
                        'reserve': float(parts[5]) if len(parts) > 5 else 0
                    })
                except (ValueError, IndexError):
                    continue

    def _normalize_crypto(self, name: str) -> str:
        """
        Нормализует название криптовалюты

        Примеры:
        'Bitcoin (BTC) TRC20' -> 'BTC'
        'Ethereum ERC20' -> 'ETH'
        'USDT TRC20' -> 'USDT'
        """
        if not name:
            return ''

        original_name = name
        name = name.upper().strip()

        # Шаг 1: Сначала проверяем скобки - там обычно короткий код
        if '(' in name and ')' in name:
            try:
                start = name.index('(') + 1
                end = name.index(')')
                code = name[start:end].strip()
                # Берём только если это похоже на криптовалютный код
                if code and 2 <= len(code) <= 10 and code.replace('-', '').isalnum():
                    return code
            except (ValueError, IndexError):
                pass

        # Шаг 2: Удаляем типы сетей
        networks = [
            ' TRC20', ' TRC-20', ' TRC',
            ' ERC20', ' ERC-20', ' ERC',
            ' BEP20', ' BEP-20', ' BEP',
            ' SOL', ' SOLANA',
            ' OMNI',
            ' ARBITRUM',
            ' POLYGON',
            ' AVALANCHE',
            ' BSC', ' BINANCE SMART CHAIN',
            ' BNB CHAIN',
            'TRC20', 'TRC-20', 'TRC',
            'ERC20', 'ERC-20', 'ERC',
            'BEP20', 'BEP-20', 'BEP',
        ]

        for network in networks:
            name = name.replace(network, ' ')

        # Шаг 3: Очищаем от лишних символов
        name = name.strip(' ()-_,.')
        name = ' '.join(name.split())  # Убираем множественные пробелы

        # Шаг 4: Проверяем маппинг полных названий
        # Проверяем начало строки (может быть "BITCOIN CODE" -> должен найти "BITCOIN")
        for full_name, ticker in self.crypto_mapping.items():
            if name.startswith(full_name):
                return ticker

        # Шаг 5: Если получилось длинное название, берём первое слово
        if len(name) > 10 and ' ' in name:
            first_word = name.split()[0]
            # Проверяем первое слово в маппинге
            if first_word in self.crypto_mapping:
                return self.crypto_mapping[first_word]
            return first_word

        # Шаг 6: Последняя проверка - может это уже тикер?
        if 2 <= len(name) <= 10:
            return name

        return ''

    def get_crypto_to_crypto_pairs(self) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Получает только крипто-крипто пары (без фиата)

        Returns:
            {
                'BTC': {
                    'ETH': [
                        {
                            'rate': 15.5,
                            'exchanger': 'Exchanger Name',
                            'exchanger_id': 123,
                            'reserve': 1000.0,
                            'give': 1.0,
                            'receive': 15.5
                        },
                        ...
                    ],
                    ...
                },
                ...
            }
        """
        pairs = {}

        # Список фиатных валют для исключения
        fiat_keywords = [
            'RUB', 'USD', 'EUR', 'GBP', 'UAH', 'KZT', 'BYN', 'CNY', 'JPY',
            'QIWI', 'YANDEX', 'SBERBANK', 'TINKOFF', 'ALFABANK', 'VTB',
            'PAYEER', 'PERFECT MONEY', 'WEBMONEY', 'ADVCASH', 'PAYPAL',
            'VISA', 'MASTERCARD', 'MIR', 'CASH', 'WIRE', 'SEPA', 'BANK',
            'RUBLE', 'DOLLAR', 'EURO', 'YUAN',
        ]

        processed_count = 0
        skipped_fiat = 0
        skipped_same = 0
        skipped_empty = 0

        for rate in self.rates:
            from_name = self.currencies.get(rate['from_id'], '')
            to_name = self.currencies.get(rate['to_id'], '')

            if not from_name or not to_name:
                continue

            from_code = self._normalize_crypto(from_name)
            to_code = self._normalize_crypto(to_name)

            # Пропускаем пустые
            if not from_code or not to_code:
                skipped_empty += 1
                continue

            # Пропускаем одинаковые
            if from_code == to_code:
                skipped_same += 1
                continue

            # Пропускаем если это фиат
            is_fiat = False
            for fiat in fiat_keywords:
                if fiat in from_code.upper() or fiat in to_code.upper():
                    is_fiat = True
                    break
                # Проверяем также исходные названия
                if fiat in from_name.upper() or fiat in to_name.upper():
                    is_fiat = True
                    break

            if is_fiat:
                skipped_fiat += 1
                continue

            # Создаём структуру
            if from_code not in pairs:
                pairs[from_code] = {}

            if to_code not in pairs[from_code]:
                pairs[from_code][to_code] = []

            # Курс обмена: сколько to_code получим за 1 from_code
            exchange_rate = rate['receive'] / rate['give'] if rate['give'] > 0 else 0

            if exchange_rate > 0:
                pairs[from_code][to_code].append({
                    'rate': exchange_rate,
                    'exchanger': self.exchangers.get(rate['exchanger_id'], 'Unknown'),
                    'exchanger_id': rate['exchanger_id'],
                    'reserve': rate['reserve'],
                    'give': rate['give'],
                    'receive': rate['receive']
                })
                processed_count += 1

        # Сортируем по лучшему курсу
        for from_crypto in pairs:
            for to_crypto in pairs[from_crypto]:
                pairs[from_crypto][to_crypto].sort(
                    key=lambda x: x['rate'],
                    reverse=True
                )

        # Отладочная информация
        print(f"[BestChange] Обработано курсов: {processed_count}")
        print(f"[BestChange] Пропущено: фиат={skipped_fiat}, одинаковые={skipped_same}, пустые={skipped_empty}")
        print(f"[BestChange] Найдено крипто-пар: {len(pairs)}")

        if len(pairs) > 0:
            # Показываем первые 15 криптовалют
            sample_cryptos = sorted(list(pairs.keys()))[:15]
            print(f"[BestChange] Примеры криптовалют: {', '.join(sample_cryptos)}")

            # Показываем несколько примеров пар для первой криптовалюты
            first_crypto = sample_cryptos[0]
            if first_crypto in pairs:
                pairs_for_first = list(pairs[first_crypto].keys())[:5]
                print(f"[BestChange] Пары для {first_crypto}: {', '.join(pairs_for_first)}")

        return pairs

    def get_best_rate(self, from_crypto: str, to_crypto: str) -> Optional[Dict]:
        """Получает лучший курс для пары"""
        pairs = self.get_crypto_to_crypto_pairs()

        if from_crypto in pairs and to_crypto in pairs[from_crypto]:
            rates = pairs[from_crypto][to_crypto]
            if rates:
                return rates[0]  # первый = лучший (уже отсортировано)

        return None