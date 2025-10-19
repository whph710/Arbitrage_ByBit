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
MIN_PROFIT_USD = float(os.getenv("MIN_PROFIT_USD", 0.5))  # Минимальная прибыль в долларах
SHOW_TOP = int(os.getenv("SHOW_TOP", 10))

# Максимальная прибыль в процентах (для фильтрации ошибок)
MAX_REASONABLE_SPREAD = float(os.getenv("MAX_REASONABLE_SPREAD", 50.0))

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
MIN_24H_VOLUME_USDT = float(os.getenv("MIN_24H_VOLUME_USDT", 100000.0))  # Повышено для скорости
MIN_LIQUIDITY_SCORE = float(os.getenv("MIN_LIQUIDITY_SCORE", 40.0))  # Повышено для качества
USE_ONLY_TOP_LIQUID_COINS = int(os.getenv("USE_ONLY_TOP_LIQUID_COINS", 200))  # Топ-200 монет

# ============================================================================
# НАСТРОЙКИ API ЗАПРОСОВ
# ============================================================================
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 100))  # Увеличено для скорости
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 0.05))  # Уменьшено для скорости
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 200))  # Увеличено для скорости
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 2))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", 0.3))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 20))

# ============================================================================
# WEBSOCKET НАСТРОЙКИ (НОВОЕ)
# ============================================================================
WEBSOCKET_ENABLED = os.getenv("WEBSOCKET_ENABLED", "True").lower() in ("true", "1", "yes")
WEBSOCKET_RECONNECT_DELAY = float(os.getenv("WEBSOCKET_RECONNECT_DELAY", 5.0))
WEBSOCKET_PING_INTERVAL = float(os.getenv("WEBSOCKET_PING_INTERVAL", 20.0))

# ============================================================================
# РЕЖИМ МОНИТОРИНГА (НОВОЕ)
# ============================================================================
MONITORING_MODE = os.getenv("MONITORING_MODE", "False").lower() in ("true", "1", "yes")
MONITORING_INTERVAL = float(os.getenv("MONITORING_INTERVAL", 30.0))  # Секунды между проверками
AUTO_ALERT_THRESHOLD = float(os.getenv("AUTO_ALERT_THRESHOLD", 2.0))  # % для автоуведомлений

# ============================================================================
# BYBIT API SETTINGS
# ============================================================================
BYBIT_API_URL = os.getenv("BYBIT_API_URL", "https://api.bybit.com")
BYBIT_WS_URL = os.getenv("BYBIT_WS_URL", "wss://stream.bybit.com/v5/public/spot")
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
# КЭШИРОВАНИЕ (НОВОЕ)
# ============================================================================
ENABLE_CACHE = True
CACHE_HOT_PAIRS = 100  # Количество "горячих" пар для кэширования
CACHE_TTL = 60  # Время жизни кэша в секундах

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
    print(f"MIN_PROFIT_USD = {MIN_PROFIT_USD}")
    print(f"MAX_REASONABLE_SPREAD = {MAX_REASONABLE_SPREAD}")
    print(f"SHOW_TOP = {SHOW_TOP}")
    print(f"ENABLE_COIN_FILTER = {ENABLE_COIN_FILTER}")
    print(f"WHITELIST_COINS = {len(WHITELIST_COINS)} монет" if WHITELIST_COINS else "WHITELIST_COINS = не задан")
    print(f"BLACKLIST_COINS = {len(BLACKLIST_COINS)} монет" if BLACKLIST_COINS else "BLACKLIST_COINS = пуст")
    print(f"USE_ONLY_TOP_LIQUID_COINS = {USE_ONLY_TOP_LIQUID_COINS}")
    print(f"MAX_CONCURRENT_REQUESTS = {MAX_CONCURRENT_REQUESTS}")
    print(f"REQUEST_DELAY = {REQUEST_DELAY}")
    print(f"BATCH_SIZE = {BATCH_SIZE}")
    print(f"WEBSOCKET_ENABLED = {WEBSOCKET_ENABLED}")
    print(f"MONITORING_MODE = {MONITORING_MODE}")
    print(f"ENABLE_CACHE = {ENABLE_CACHE}")
    print(f"BYBIT_API_URL = {BYBIT_API_URL}")
    print(f"BYBIT_WS_URL = {BYBIT_WS_URL}")
    print(f"BYBIT_API_KEY = {'задан' if BYBIT_API_KEY else 'не задан'}")
    print(f"BESTCHANGE_API_KEY = {'задан ✓' if BESTCHANGE_API_KEY else 'НЕ ЗАДАН ✗'}")
    print(f"RESULTS_DIR = {RESULTS_DIR}")
    print(f"LOGS_DIR = {LOGS_DIR}")
    print("===========================\n")