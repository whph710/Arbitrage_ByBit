import requests
import zipfile
import io
from typing import Dict, List
from datetime import datetime
from configs import Config


class BestChangeHandler:
    """Обработчик данных BestChange"""

    def __init__(self):
        self.base_url = Config.BESTCHANGE_API_URL
        self.currencies = {}
        self.exchangers = {}
        self.rates = []
        self.last_update = None

    def update_data(self) -> bool:
        """Загружает свежие данные с BestChange"""
        try:
            print("[BestChange] Загрузка данных...")

            response = requests.get(self.base_url, timeout=10)
            response.raise_for_status()

            self.currencies.clear()
            self.exchangers.clear()
            self.rates.clear()

            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                with zip_file.open('bm_cy.dat') as f:
                    self._parse_currencies(f.read().decode('utf-8'))

                with zip_file.open('bm_exch.dat') as f:
                    self._parse_exchangers(f.read().decode('utf-8'))

                with zip_file.open('bm_rates.dat') as f:
                    self._parse_rates(f.read().decode('utf-8'))

            self.last_update = datetime.now()
            print(f"[BestChange] ✓ Загружено: {len(self.currencies)} валют, {len(self.rates)} курсов")
            return True

        except Exception as e:
            print(f"[BestChange] ✗ Ошибка: {e}")
            return False

    def _parse_currencies(self, data: str):
        """Парсит файл с валютами"""
        for line in data.strip().split('\n'):
            parts = line.split(';')
            if len(parts) >= 2:
                self.currencies[int(parts[0])] = parts[1]

    def _parse_exchangers(self, data: str):
        """Парсит файл с обменниками"""
        for line in data.strip().split('\n'):
            parts = line.split(';')
            if len(parts) >= 2:
                self.exchangers[int(parts[0])] = parts[1]

    def _parse_rates(self, data: str):
        """Парсит файл с курсами обмена"""
        for line in data.strip().split('\n'):
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
        """Нормализует название криптовалюты"""
        name = name.upper()
        suffixes = ['TRC20', 'TRC', 'ERC20', 'ERC', 'BEP20', 'BEP',
                    'SOL', 'OMNI', 'ARBITRUM', 'POLYGON', 'AVAX']
        for suffix in suffixes:
            name = name.replace(suffix, '')
        return name.strip()

    def get_exchange_pairs(self) -> Dict[str, Dict[str, List[Dict]]]:
        """
        Получает все торговые пары с обменников

        Returns:
            {from_crypto: {to_crypto: [{rate, exchanger, reserve}, ...]}}
        """
        pairs = {}

        for rate in self.rates:
            from_code = self._normalize_crypto(
                self.currencies.get(rate['from_id'], '')
            )
            to_code = self._normalize_crypto(
                self.currencies.get(rate['to_id'], '')
            )

            # Пропускаем пустые и одинаковые пары
            if not from_code or not to_code or from_code == to_code:
                continue

            # Пропускаем пары с USDT (нам нужны крипта-крипта)
            if 'USDT' in from_code or 'USDT' in to_code:
                continue

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

        return pairs