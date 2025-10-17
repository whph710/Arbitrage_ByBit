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
    BESTCHANGE_API_KEY = os.getenv('BESTCHANGE_API_KEY', '')

    # ════════════════════════════════════════════════════════════════
    # ПАРАМЕТРЫ АРБИТРАЖА
    # ════════════════════════════════════════════════════════════════

    # Разрешенные криптовалюты для торговли (топ ликвидные монеты)
    ALLOWED_COINS = {
        'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE',
        'DOT', 'MATIC', 'LTC', 'SHIB', 'AVAX', 'TRX', 'LINK', 'BCH', 'XLM',
        'UNI', 'ATOM', 'XMR', 'ETC', 'FIL', 'APT', 'NEAR', 'ARB', 'OP',
        'TON', 'DAI', 'BUSD', 'TUSD', 'XTZ', 'ALGO', 'VET', 'ICP', 'HBAR',
        'QNT', 'GRT', 'AAVE', 'MKR', 'SAND', 'MANA', 'AXS', 'THETA', 'FTM'
    }

    # Минимальный процент разницы для отображения возможности
    # Большой спред компенсирует все комиссии
    MIN_PROFIT_PERCENT = float(os.getenv('MIN_PROFIT_PERCENT', '2.0'))

    # Начальная сумма для расчёта в USD
    MIN_AMOUNT_USD = float(os.getenv('MIN_AMOUNT_USD', '100'))

    # Сколько лучших возможностей показывать и сохранять
    TOP_OPPORTUNITIES = int(os.getenv('TOP_OPPORTUNITIES', '10'))

    # ════════════════════════════════════════════════════════════════
    # ПУТИ И ДИРЕКТОРИИ
    # ════════════════════════════════════════════════════════════════
    BASE_DIR = Path(__file__).parent
    RESULTS_DIR = BASE_DIR / 'results'

    # Создаём папку для результатов если не существует
    RESULTS_DIR.mkdir(exist_ok=True)

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