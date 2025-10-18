# configs.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Максимальная прибыль в процентах (для фильтрации ошибок)
MAX_REASONABLE_PROFIT = 50

START_AMOUNT = float(os.getenv("START_AMOUNT", 100.0))
MIN_SPREAD = float(os.getenv("MIN_SPREAD", 0.5))
SHOW_TOP = int(os.getenv("SHOW_TOP", 10))

# ============================================================================
# ОПТИМИЗИРОВАННЫЕ НАСТРОЙКИ ДЛЯ BESTCHANGE API
# ============================================================================
# Уменьшаем количество одновременных запросов с 10 до 2
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 2))

# Увеличиваем задержку между запросами с 0.1 до 0.8 секунд
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 0.8))

# Размер пакета для batch загрузки (уменьшено с 100 до 50)
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))

# Количество повторных попыток при ошибке
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))

# Задержка при повторной попытке (в секундах)
RETRY_DELAY = float(os.getenv("RETRY_DELAY", 2.0))

# Таймаут для запросов (увеличен с 15 до 30 секунд)
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
# BESTCHANGE API SETTINGS
# ============================================================================
BESTCHANGE_API_KEY = os.getenv("BESTCHANGE_API_KEY", "")
BESTCHANGE_BASE_URL = os.getenv("BESTCHANGE_BASE_URL", "https://bestchange.app")

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
    print(f"MAX_CONCURRENT_REQUESTS = {MAX_CONCURRENT_REQUESTS}")
    print(f"REQUEST_DELAY = {REQUEST_DELAY}")
    print(f"BATCH_SIZE = {BATCH_SIZE}")
    print(f"MAX_RETRIES = {MAX_RETRIES}")
    print(f"RETRY_DELAY = {RETRY_DELAY}")
    print(f"REQUEST_TIMEOUT = {REQUEST_TIMEOUT}")
    print(f"BYBIT_API_URL = {BYBIT_API_URL}")
    print(f"BINANCE_API_URL = {BINANCE_API_URL}")
    print(f"BESTCHANGE_API_KEY = {'***' if BESTCHANGE_API_KEY else 'NOT SET'}")
    print(f"BESTCHANGE_BASE_URL = {BESTCHANGE_BASE_URL}")
    print(f"RESULTS_DIR = {RESULTS_DIR}")
    print(f"LOGS_DIR = {LOGS_DIR}")
    print("===========================\n")