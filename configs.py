# configs.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Максимальная прибыль в процентах (для фильтрации ошибок)
# Если спред больше этого значения - скорее всего ошибка в данных
MAX_REASONABLE_SPREAD = 10.0  # 10% - максимальный реалистичный спред

START_AMOUNT = float(os.getenv("START_AMOUNT", 100.0))
MIN_SPREAD = float(os.getenv("MIN_SPREAD", 0.5))
SHOW_TOP = int(os.getenv("SHOW_TOP", 10))

# ============================================================================
# ФИЛЬТРАЦИЯ МОНЕТ
# ============================================================================

# ЧЁРНЫЙ СПИСОК - монеты, которые нужно ИСКЛЮЧИТЬ из анализа
# Добавляй сюда проблемные монеты (делистинг, нет переводов, заморожены и т.д.)
BLACKLIST_COINS = {
    'XEM',      # NEM - проблемы с переводами
    'LUNA',     # Terra Classic - делистинг на многих биржах
    'UST',      # TerraUSD - обвалилась
    'FTT',      # FTX Token - делистинг
    'BUSD',     # Binance USD - прекращён выпуск
    'TUSD',     # TrueUSD - проблемы на некоторых биржах
    'PAX',      # Paxos - ограничения
    'USDC',     # Часто заморожен на переводах между биржами
    # Добавляй сюда свои монеты
}

# БЕЛЫЙ СПИСОК - работать ТОЛЬКО с этими монетами (если не пустой)
# Если список пустой - используются все монеты кроме чёрного списка
# Если заполнен - работает ТОЛЬКО с этими монетами
WHITELIST_COINS = {
    # Популярные и ликвидные монеты (раскомментируй если хочешь использовать только их)
    # 'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL', 'TRX', 'MATIC', 'DOT',
    # 'LTC', 'SHIB', 'AVAX', 'UNI', 'LINK', 'ATOM', 'XLM', 'ETC', 'BCH', 'APT'
}

# Режим работы фильтра:
# - True: используется БЕЛЫЙ список (если он заполнен), иначе ВСЕ монеты минус чёрный список
# - False: отключить фильтрацию полностью (не рекомендуется)
ENABLE_COIN_FILTER = True

# ============================================================================
# ОПТИМИЗИРОВАННЫЕ НАСТРОЙКИ ДЛЯ API
# ============================================================================
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 2))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 0.8))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", 2.0))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

# ============================================================================
# BYBIT API SETTINGS
# ============================================================================
BYBIT_API_URL = os.getenv("BYBIT_API_URL", "https://api.bybit.com")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")

# ============================================================================
# BINANCE API SETTINGS
# ============================================================================
BINANCE_API_URL = os.getenv("BINANCE_API_URL", "https://api.binance.com")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# ============================================================================
# DIRECTORIES
# ============================================================================
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"
RESULTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

if DEBUG:
    print("\n===== CONFIG SUMMARY =====")
    print(f"START_AMOUNT = {START_AMOUNT}")
    print(f"MIN_SPREAD = {MIN_SPREAD}")
    print(f"SHOW_TOP = {SHOW_TOP}")
    print(f"ENABLE_COIN_FILTER = {ENABLE_COIN_FILTER}")
    print(f"BLACKLIST_COINS = {len(BLACKLIST_COINS)} монет")
    print(f"WHITELIST_COINS = {len(WHITELIST_COINS)} монет")
    print(f"MAX_CONCURRENT_REQUESTS = {MAX_CONCURRENT_REQUESTS}")
    print(f"REQUEST_DELAY = {REQUEST_DELAY}")
    print(f"BATCH_SIZE = {BATCH_SIZE}")
    print(f"MAX_RETRIES = {MAX_RETRIES}")
    print(f"RETRY_DELAY = {RETRY_DELAY}")
    print(f"REQUEST_TIMEOUT = {REQUEST_TIMEOUT}")
    print(f"BYBIT_API_URL = {BYBIT_API_URL}")
    print(f"BINANCE_API_URL = {BINANCE_API_URL}")
    print(f"RESULTS_DIR = {RESULTS_DIR}")
    print(f"LOGS_DIR = {LOGS_DIR}")
    print("===========================\n")