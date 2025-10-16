import gzip
import requests
from typing import Dict, List
from io import BytesIO
from configs import Config


class BestChangeHandler:
    """Парсер данных BestChange"""

    def __init__(self):
        self.base_url = "https://api.bestchange.ru/info.zip"
        self.currencies = {}
        self.exchangers = {}
        self.rates = []

    def _download_data(self) -> bytes:
        response = requests.get(self.base_url, timeout=Config.REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.content

    def load_data(self):
        """Загружает данные BestChange (info.zip)"""
        print("[BestChange] Загрузка данных...")
        raw = self._download_data()

        with gzip.GzipFile(fileobj=BytesIO(raw)) as gz:
            content = gz.read().decode("utf-8", errors="ignore")

        # Каждая секция отделена строками "..."
        sections = content.split("##########")

        # currencies.txt
        currencies_text = sections[1]
        for line in currencies_text.strip().splitlines():
            parts = line.split(";")
            if len(parts) >= 3:
                cid, _, name = parts[:3]
                self.currencies[int(cid)] = name.strip()

        # exchangers.txt
        exchangers_text = sections[2]
        for line in exchangers_text.strip().splitlines():
            parts = line.split(";")
            if len(parts) >= 2:
                eid, name = parts[:2]
                self.exchangers[int(eid)] = name.strip()

        # rates.txt
        rates_text = sections[3]
        for line in rates_text.strip().splitlines():
            parts = line.split(";")
            if len(parts) >= 5:
                self.rates.append({
                    "from_id": int(parts[0]),
                    "to_id": int(parts[1]),
                    "rate": float(parts[2]) if parts[2] else 0.0,
                    "exchanger_id": int(parts[4]),
                })

        print(f"[BestChange] ✓ Загружено:")
        print(f"  • Валют: {len(self.currencies)}")
        print(f"  • Обменников: {len(self.exchangers)}")
        print(f"  • Курсов: {len(self.rates)}")

    def get_crypto_to_crypto_pairs(self, bybit_tickers: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        """
        Возвращает словарь доступных обменов криптовалюты на криптовалюту.
        Ищет совпадения по тикерам из Bybit.
        """
        crypto_pairs = {}
        total = 0
        matched = 0

        bybit_symbols = list(bybit_tickers.keys())

        for rate in self.rates:
            from_name = self.currencies.get(rate["from_id"], "")
            to_name = self.currencies.get(rate["to_id"], "")
            if not from_name or not to_name:
                continue

            from_code = None
            to_code = None

            for sym in bybit_symbols:
                if sym in from_name.upper():
                    from_code = sym
                if sym in to_name.upper():
                    to_code = sym

            if not from_code or not to_code:
                continue

            total += 1
            matched += 1

            if from_code not in crypto_pairs:
                crypto_pairs[from_code] = {}

            crypto_pairs[from_code][to_code] = rate["rate"]

        print(f"[BestChange] Обработано курсов: {total}")
        print(f"[BestChange] Найдено совпадений по тикерам Bybit: {matched}")
        print(f"[BestChange] Найдено крипто-пар: {len(crypto_pairs)}")

        return crypto_pairs
    def update_data(self) -> bool:
        """Совместимость со старым кодом main.py"""
        try:
            self.load_data()
            return True
        except Exception as e:
            print(f"[BestChange] ✗ Ошибка обновления данных: {e}")
            return False
