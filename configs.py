# configs.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# ============================================================================
# ОСНОВНЫЕ ПАРАМЕТРЫ АНАЛИЗА
# ============================================================================
START_AMOUNT = float(os.getenv("START_AMOUNT", 100.0))
MIN_SPREAD = float(os.getenv("MIN_SPREAD", 0.5))
SHOW_TOP = int(os.getenv("SHOW_TOP", 10))

# Максимальная прибыль в процентах (для фильтрации ошибок)
MAX_REASONABLE_SPREAD = float(os.getenv("MAX_REASONABLE_SPREAD", 10.0))

# ============================================================================
# ФИЛЬТРАЦИЯ МОНЕТ
# ============================================================================
# Чёрный список - монеты, которые НЕ будут использоваться в арбитраже
BLACKLIST_COINS = set()

# Белый список - если задан, будут использоваться ТОЛЬКО эти монеты
WHITELIST_COINS = set()

# Включить фильтрацию монет (True = использовать белый/чёрный список)
ENABLE_COIN_FILTER = False

# ============================================================================
# ФИЛЬТРАЦИЯ ПО ЛИКВИДНОСТИ
# ============================================================================
MIN_24H_VOLUME_USDT = float(os.getenv("MIN_24H_VOLUME_USDT", 50000.0))
MIN_LIQUIDITY_SCORE = float(os.getenv("MIN_LIQUIDITY_SCORE", 30.0))
USE_ONLY_TOP_LIQUID_COINS = int(os.getenv("USE_ONLY_TOP_LIQUID_COINS", 0))

# ============================================================================
# НАСТРОЙКИ API ЗАПРОСОВ
# ============================================================================
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 20))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 0.1))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 1))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", 0.5))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 15))

# ============================================================================
# BYBIT API SETTINGS
# ============================================================================
BYBIT_API_URL = os.getenv("BYBIT_API_URL", "https://api.bybit.com")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")

# ============================================================================
# BESTCHANGE API SETTINGS
# ============================================================================
BESTCHANGE_API_KEY = os.getenv("BESTCHANGE_API_KEY", "")

if not BESTCHANGE_API_KEY:
    print("⚠️  ПРЕДУПРЕЖДЕНИЕ: BESTCHANGE_API_KEY не задан в .env файле")
    print("    Получите ключ на https://www.bestchange.com/wiki/api.html")

# ============================================================================
# НАСТРОЙКИ ВНУТРИБИРЖЕВОГО АРБИТРАЖА
# ============================================================================
CHECK_TRIANGULAR = True
CHECK_QUADRILATERAL = True
QUAD_MAX_COINS = int(os.getenv("QUAD_MAX_COINS", 100))

# ============================================================================
# DIRECTORIES
# ============================================================================
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"
RESULTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ============================================================================
# DEBUG MODE
# ============================================================================
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

if DEBUG:
    print("\n===== CONFIG SUMMARY =====")
    print(f"START_AMOUNT = {START_AMOUNT}")
    print(f"MIN_SPREAD = {MIN_SPREAD}")
    print(f"MAX_REASONABLE_SPREAD = {MAX_REASONABLE_SPREAD}")
    print(f"SHOW_TOP = {SHOW_TOP}")
    print(f"ENABLE_COIN_FILTER = {ENABLE_COIN_FILTER}")
    print(f"WHITELIST_COINS = {len(WHITELIST_COINS)} монет" if WHITELIST_COINS else "WHITELIST_COINS = не задан")
    print(f"BLACKLIST_COINS = {len(BLACKLIST_COINS)} монет" if BLACKLIST_COINS else "BLACKLIST_COINS = пуст")
    print(f"CHECK_TRIANGULAR = {CHECK_TRIANGULAR}")
    print(f"CHECK_QUADRILATERAL = {CHECK_QUADRILATERAL}")
    print(f"QUAD_MAX_COINS = {QUAD_MAX_COINS}")
    print(f"MAX_CONCURRENT_REQUESTS = {MAX_CONCURRENT_REQUESTS}")
    print(f"REQUEST_DELAY = {REQUEST_DELAY}")
    print(f"MAX_RETRIES = {MAX_RETRIES}")
    print(f"REQUEST_TIMEOUT = {REQUEST_TIMEOUT}")
    print(f"BYBIT_API_URL = {BYBIT_API_URL}")
    print(f"BYBIT_API_KEY = {'задан' if BYBIT_API_KEY else 'не задан'}")
    print(f"BESTCHANGE_API_KEY = {'задан ✓' if BESTCHANGE_API_KEY else 'НЕ ЗАДАН ✗'}")
    print(f"RESULTS_DIR = {RESULTS_DIR}")
    print(f"LOGS_DIR = {LOGS_DIR}")
    print("===========================\n")