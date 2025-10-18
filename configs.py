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
# Пример популярных монет с высокой ликвидностью:
# WHITELIST_COINS = {'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL', 'DOT', 'MATIC', 'LTC', 'AVAX', 'LINK', 'UNI', 'ATOM', 'ETC', 'XLM', 'FIL', 'TRX', 'ALGO', 'VET'}
WHITELIST_COINS = set()

# Включить фильтрацию монет (True = использовать белый/чёрный список)
ENABLE_COIN_FILTER = False  # По умолчанию отключено - анализируем все монеты

# ============================================================================
# ФИЛЬТРАЦИЯ ПО ЛИКВИДНОСТИ (КРИТИЧНО ДЛЯ ИЗБЕЖАНИЯ ПРОСКАЛЬЗЫВАНИЯ!)
# ============================================================================

# Минимальный объём торгов за 24 часа в USDT
# Рекомендуемые значения:
# - 10,000 USDT - для тестов (много пар, но могут быть неликвидные)
# - 50,000 USDT - консервативно (хороший баланс)
# - 100,000 USDT - безопасно (только ликвидные пары)
# - 500,000 USDT - очень консервативно (топовые монеты)
MIN_24H_VOLUME_USDT = float(os.getenv("MIN_24H_VOLUME_USDT", 50000.0))

# Минимальная оценка ликвидности (0-100)
# Учитывает объём, оборот и спред bid/ask
# Рекомендуемые значения:
# - 20 - для тестов (много пар)
# - 30 - консервативно (хорошая ликвидность)
# - 40 - безопасно (высокая ликвидность)
# - 50 - очень консервативно (только топ)
MIN_LIQUIDITY_SCORE = float(os.getenv("MIN_LIQUIDITY_SCORE", 30.0))

# Использовать ТОЛЬКО монеты из топ-N по ликвидности
# 0 = отключено, использовать все подходящие
# 50 = использовать только топ-50 самых ликвидных монет
# 100 = использовать только топ-100
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
# НАСТРОЙКИ ВНУТРИБИРЖЕВОГО АРБИТРАЖА
# ============================================================================
# Проверять треугольный арбитраж (3 сделки: USDT -> A -> B -> USDT)
CHECK_TRIANGULAR = True

# Проверять четырехугольный арбитраж (4 сделки: USDT -> A -> B -> C -> USDT)
CHECK_QUADRILATERAL = True

# Лимит монет для четырехугольного арбитража (чтобы не перегружать)
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
    print(f"RESULTS_DIR = {RESULTS_DIR}")
    print(f"LOGS_DIR = {LOGS_DIR}")
    print("===========================\n")