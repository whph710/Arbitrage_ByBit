# configs.py
import os
from pathlib import Path
from dotenv import load_dotenv

# ───────────────────────────────
# Путь к проекту и .env
# ───────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# ───────────────────────────────
# Основные параметры арбитража
# ───────────────────────────────
START_AMOUNT = float(os.getenv("START_AMOUNT", 100.0))  # начальная сумма в USD
MIN_SPREAD = float(os.getenv("MIN_SPREAD", 0.5))        # минимальный спред в %
SHOW_TOP = int(os.getenv("SHOW_TOP", 10))               # количество лучших связок для отображения
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 10))  # параллельные запросы

# ───────────────────────────────
# Bybit API
# ───────────────────────────────
BYBIT_API_URL = os.getenv("BYBIT_API_URL", "https://api.bybit.com/v5/market/tickers")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")

# ───────────────────────────────
# BestChange API
# ───────────────────────────────
BESTCHANGE_BASE_URL = os.getenv("BESTCHANGE_BASE_URL", "https://bestchange.app")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))  # таймаут для HTTP запросов

# ───────────────────────────────
# Пути для результатов и логов
# ───────────────────────────────
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"
RESULTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ───────────────────────────────
# Режим отладки
# ───────────────────────────────
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

if DEBUG:
    print("\n===== CONFIG SUMMARY =====")
    print(f"START_AMOUNT = {START_AMOUNT}")
    print(f"MIN_SPREAD = {MIN_SPREAD}")
    print(f"SHOW_TOP = {SHOW_TOP}")
    print(f"MAX_CONCURRENT_REQUESTS = {MAX_CONCURRENT_REQUESTS}")
    print(f"BYBIT_API_URL = {BYBIT_API_URL}")
    print(f"BESTCHANGE_BASE_URL = {BESTCHANGE_BASE_URL}")
    print(f"RESULTS_DIR = {RESULTS_DIR}")
    print(f"LOGS_DIR = {LOGS_DIR}")
    print("===========================\n")
