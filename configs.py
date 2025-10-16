# configs.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация арбитражного бота"""

    # ════════════════════════════════════════════════════════════════
    # API КЛЮЧИ
    # ════════════════════════════════════════════════════════════════
    BYBIT_API_KEY = os.getenv('BYBIT_API_KEY', '')
    BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET', '')
    BESTCHANGE_API_KEY = os.getenv('BESTCHANGE_API_KEY', '')  # не используется пока

    # ════════════════════════════════════════════════════════════════
    # ПАРАМЕТРЫ АРБИТРАЖА
    # ════════════════════════════════════════════════════════════════

    # Минимальный процент прибыли для отображения возможности
    MIN_PROFIT_PERCENT = float(os.getenv('MIN_PROFIT_PERCENT', '0.5'))

    # Начальная сумма для расчёта в USD
    MIN_AMOUNT_USD = float(os.getenv('MIN_AMOUNT_USD', '100'))

    # Сколько лучших возможностей показывать и сохранять
    TOP_OPPORTUNITIES = int(os.getenv('TOP_OPPORTUNITIES', '5'))

    # ════════════════════════════════════════════════════════════════
    # КОМИССИИ
    # ════════════════════════════════════════════════════════════════

    # Торговая комиссия Bybit (0.1% = 0.001)
    BYBIT_TRADING_FEE = 0.001

    # Примерная комиссия за вывод с биржи (в USD)
    WITHDRAWAL_FEE_USD = float(os.getenv('WITHDRAWAL_FEE_USD', '3.0'))

    # Примерная комиссия за депозит на биржу (в USD)
    DEPOSIT_FEE_USD = float(os.getenv('DEPOSIT_FEE_USD', '2.0'))

    # ════════════════════════════════════════════════════════════════
    # ПУТИ И ДИРЕКТОРИИ
    # ════════════════════════════════════════════════════════════════
    BASE_DIR = Path(__file__).parent
    RESULTS_DIR = BASE_DIR / 'results'

    # Создаём папку для результатов если не существует
    RESULTS_DIR.mkdir(exist_ok=True)

    # ════════════════════════════════════════════════════════════════
    # BESTCHANGE API
    # ════════════════════════════════════════════════════════════════

    BESTCHANGE_API_URL = "http://api.bestchange.ru/info.zip"
    BESTCHANGE_CACHE_SECONDS = 15

    # ════════════════════════════════════════════════════════════════
    # BYBIT API
    # ════════════════════════════════════════════════════════════════

    BYBIT_BASE_URL = "https://api.bybit.com"
    BYBIT_TESTNET_URL = "https://api-testnet.bybit.com"
    USE_TESTNET = os.getenv('USE_TESTNET', 'False').lower() == 'true'
    CURRENT_BYBIT_URL = BYBIT_TESTNET_URL if USE_TESTNET else BYBIT_BASE_URL

    # ════════════════════════════════════════════════════════════════
    # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ
    # ════════════════════════════════════════════════════════════════

    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))
    VERBOSE_LOGGING = os.getenv('VERBOSE_LOGGING', 'False').lower() == 'true'
