import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация проекта"""

    # API ключи
    BYBIT_API_KEY = os.getenv('BYBIT_API_KEY', '')
    BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET', '')
    BESTCHANGE_API_KEY = os.getenv('BESTCHANGE_API_KEY', '')

    # Параметры арбитража
    MIN_PROFIT_PERCENT = float(os.getenv('MIN_PROFIT_PERCENT', '0.5'))
    MIN_AMOUNT_USD = float(os.getenv('MIN_AMOUNT_USD', '100'))
    TOP_OPPORTUNITIES = int(os.getenv('TOP_OPPORTUNITIES', '5'))

    # Комиссии
    BYBIT_TRADING_FEE = 0.001  # 0.1%
    WITHDRAWAL_FEE_USD = 3.0  # примерная комиссия за вывод
    DEPOSIT_FEE_USD = 2.0  # примерная комиссия за ввод

    # Пути
    BASE_DIR = Path(__file__).parent
    RESULTS_DIR = BASE_DIR / 'results'

    # Создаём папку для результатов
    RESULTS_DIR.mkdir(exist_ok=True)

    # BestChange
    BESTCHANGE_API_URL = "http://api.bestchange.ru/info.zip"
    BESTCHANGE_CACHE_SECONDS = 15

    # Bybit
    BYBIT_BASE_URL = "https://api.bybit.com"
    BYBIT_TESTNET_URL = "https://api-testnet.bybit.com"
    USE_TESTNET = False