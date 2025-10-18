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
MAX_REASONABLE_SPREAD = 10.0  # 10% - максимальный реалистичный спред

# ============================================================================
# ФИЛЬТРАЦИЯ МОНЕТ - ОТКЛЮЧЕНА для работы с обменниками
# ============================================================================
BLACKLIST_COINS = set()
WHITELIST_COINS = set()
ENABLE_COIN_FILTER = False  # Отключаем фильтрацию - берём ВСЕ монеты

# ============================================================================
# НАСТРОЙКИ API ЗАПРОСОВ (МАКСИМАЛЬНО ОПТИМИЗИРОВАННЫЕ)
# ============================================================================
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 20))  # Увеличено для параллелизма
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 0.1))  # Минимальная задержка
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 1))  # Только 1 повтор для скорости
RETRY_DELAY = float(os.getenv("RETRY_DELAY", 0.5))  # Быстрые повторы
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 15))  # Короткий таймаут

# ============================================================================
# BYBIT API SETTINGS
# ============================================================================
BYBIT_API_URL = os.getenv("BYBIT_API_URL", "https://api.bybit.com")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")

# ============================================================================
# CHANGENOW API SETTINGS
# ============================================================================
CHANGENOW_API_KEY = os.getenv("CHANGENOW_API_KEY", "")  # Опционально

# ============================================================================
# SWAPZONE API SETTINGS
# ============================================================================
SWAPZONE_API_KEY = os.getenv("SWAPZONE_API_KEY", "XQZenodya")  # Ваш API ключ

# ============================================================================
# НАСТРОЙКИ АНАЛИЗА ОБМЕННИКОВ (МАКСИМАЛЬНО ОПТИМИЗИРОВАННЫЕ)
# ============================================================================
# Максимальное количество пар для проверки
# Рекомендуется: 100-200 для быстрого анализа (1-3 мин), 300-1000 для полного (5-15 мин)
MAX_PAIRS_TO_CHECK = int(os.getenv("MAX_PAIRS_TO_CHECK", 150))

# Задержка между запросами к обменнику (секунды)
# 0 = максимальная скорость (риск rate limit), 0.05-0.1 = оптимально
EXCHANGE_REQUEST_DELAY = float(os.getenv("EXCHANGE_REQUEST_DELAY", 0.0))

# Минимальная сумма для обмена (USDT)
MIN_EXCHANGE_AMOUNT = float(os.getenv("MIN_EXCHANGE_AMOUNT", 10.0))

# Максимальная сумма для обмена (USDT)
MAX_EXCHANGE_AMOUNT = float(os.getenv("MAX_EXCHANGE_AMOUNT", 10000.0))

# Кэширование неудачных пар (не запрашивать повторно)
CACHE_FAILED_PAIRS = True

# Количество параллельных запросов к обменнику (10-50 оптимально)
PARALLEL_EXCHANGE_REQUESTS = int(os.getenv("PARALLEL_EXCHANGE_REQUESTS", 20))

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
    print(f"SHOW_TOP = {SHOW_TOP}")
    print(f"ENABLE_COIN_FILTER = {ENABLE_COIN_FILTER}")
    print(f"MAX_PAIRS_TO_CHECK = {MAX_PAIRS_TO_CHECK}")
    print(f"EXCHANGE_REQUEST_DELAY = {EXCHANGE_REQUEST_DELAY}")
    print(f"MAX_CONCURRENT_REQUESTS = {MAX_CONCURRENT_REQUESTS}")
    print(f"REQUEST_DELAY = {REQUEST_DELAY}")
    print(f"MAX_RETRIES = {MAX_RETRIES}")
    print(f"REQUEST_TIMEOUT = {REQUEST_TIMEOUT}")
    print(f"CACHE_FAILED_PAIRS = {CACHE_FAILED_PAIRS}")
    print(f"BYBIT_API_URL = {BYBIT_API_URL}")
    print(f"CHANGENOW_API_KEY = {'задан' if CHANGENOW_API_KEY else 'не задан'}")
    print(f"RESULTS_DIR = {RESULTS_DIR}")
    print(f"LOGS_DIR = {LOGS_DIR}")
    print("===========================\n")