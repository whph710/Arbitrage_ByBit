# config.py — Конфигурационные настройки для арбитражного бота Bybit
# =============================================================================
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# =============================================================================
# ОСНОВНЫЕ НАСТРОЙКИ ТОРГОВЛИ
# =============================================================================
MIN_PROFIT_THRESHOLD = 0.001  # Минимальный порог прибыли для арбитража в процентах (0.001 = 0.1%)
TRADING_COMMISSION = 0.001  # Комиссия за торговлю (0.1% = 0.001)
INITIAL_AMOUNT = 5000.0  # Начальный капитал для оценки исполнимости арбитража в USDT
MAX_OPPORTUNITIES_DISPLAY = 50  # Максимальное количество арбитражных возможностей, отображаемых за один раз

# =============================================================================
# НАСТРОЙКИ API И ПОДКЛЮЧЕНИЯ
# =============================================================================
BYBIT_BASE_URL = "https://api.bybit.com/v5"  # Базовый URL API Bybit
HTTP_TIMEOUT = 6
API_RETRY_ATTEMPTS = 8
API_RETRY_DELAY = 0.2

# =============================================================================
# НАСТРОЙКИ API КЛЮЧЕЙ ДЛЯ РЕАЛЬНОЙ ТОРГОВЛИ
# =============================================================================
# Ключи загружаются из файла .env
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

API_TESTNET = False
TESTNET_BASE_URL = "https://api-testnet.bybit.com/v5"

# =============================================================================
# НАСТРОЙКИ ВРЕМЕННЫХ ИНТЕРВАЛОВ
# =============================================================================
SCAN_INTERVAL = 1
ERROR_RETRY_INTERVAL = 1
ORDERBOOK_TIMEOUT = 4

# =============================================================================
# НАСТРОЙКИ ВАЛЮТНЫХ ПАР — МАКСИМУМ
# =============================================================================
CROSS_CURRENCIES = [
    'USDT', 'USDC', 'BUSD', 'DAI', 'USD', 'TUSD',
    'BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'LTC', 'DOGE', 'MATIC', 'TRX', 'AVAX', 'DOT', 'LINK', 'ATOM',
    'NEAR', 'FTM', 'XLM', 'EOS', 'ICP', 'XTZ', 'AAVE', 'SUSHI', 'UNI', 'ZEC', 'BAT', 'CHZ', 'KSM', 'RUNE',
    'ALGO', 'VET', 'KLAY', 'HNT', 'ONT', 'MANA', 'GRT', 'CELO', 'OKB', 'XTZ', 'NANO', 'QTUM', 'DASH', 'ZIL',
    'ANKR', 'ANK', 'IOST', 'ENJ', 'SC', 'WAVES', 'ZRX', 'RVN', 'HBAR', 'COMP', 'SNX', 'BTT', 'ICX', 'STORJ',
    'DCR', 'KNC', 'LRC', 'RVN', 'ONE', 'GALA', 'MINA', 'AR', 'CHSB', 'KAVA', 'SUSHI', 'RAY', 'SRM', 'STEEM',
    'SHIB', 'PEPE', 'FLOKI', 'ELON', 'TAMA', 'BABYDOGE', 'WIF'
]
EXCLUDED_CURRENCIES = []

MIN_LIQUIDITY_VOLUME = 50  # Минимальная ликвидность для соответствия требованиям биржи

# =============================================================================
# НАСТРОЙКИ ЛОГИРОВАНИЯ
# =============================================================================
LOG_LEVEL = "DEBUG"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "arbitrage_max_aggressive.log"
LOG_MAX_SIZE = 200 * 1024 * 1024
LOG_BACKUP_COUNT = 20
LOG_ENCODING = "utf-8"

# =============================================================================
# НАСТРОЙКИ УВЕДОМЛЕНИЙ
# =============================================================================
CONSOLE_NOTIFICATIONS = True
SOUND_NOTIFICATIONS = False
SOUND_FILE_PATH = "alert.wav"

# =============================================================================
# ПРОДВИНУТЫЕ НАСТРОЙКИ
# =============================================================================
USE_ORDERBOOK_CACHE = False
ORDERBOOK_CACHE_TTL = 0
MAX_CONCURRENT_REQUESTS = 500  # Высокое значение для агрессивного сканирования
PERFORMANCE_DIAGNOSTICS = True

# =============================================================================
# НАСТРОЙКИ ФИЛЬТРАЦИИ
# =============================================================================
FILTER_LOW_LIQUIDITY = True
MAX_SPREAD_PERCENT = 10.0
EXCLUDE_HIGH_VOLATILITY = False
MAX_VOLATILITY_PERCENT = 100.0

# =============================================================================
# НАСТРОЙКИ БЕЗОПАСНОСТИ / СЕТИ
# =============================================================================
API_RATE_LIMIT = 5000  # Высокий лимит для максимального сканирования
SSL_VERIFY = True
NETWORK_TIMEOUT = 15

# =============================================================================
# ЭКСПЕРИМЕНТАЛЬНЫЕ НАСТРОЙКИ
# =============================================================================
EXPERIMENTAL_OPTIMIZATIONS = True
ML_VOLATILITY_PREDICTION = True
ORDERBOOK_DEPTH_ANALYSIS = True
ORDERBOOK_LEVELS = 50

# =============================================================================
# НАСТРОЙКИ ДЛЯ АВТОНОМНОЙ ТОРГОВЛИ
# =============================================================================
ENABLE_LIVE_TRADING = True
LIVE_TRADING_DRY_RUN = False

LIVE_TRADING_MAX_TRADE_USDT = 1000.0  # Максимальная сумма сделки
LIVE_TRADING_MIN_TRADE_USDT = 5.0     # Минимальная сумма сделки

LIVE_TRADING_MAX_EXEC_PER_MIN = 60
LIVE_TRADING_ORDER_GAP_SEC = 0.05
ALLOW_PARTIAL_FILL_EXECUTION = True
REQUIRE_BALANCE_CHECK_BEFORE_LIVE = True

# =============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ
# =============================================================================
SESSION_MAX_DRAWDOWN_PERCENT = 50.0
LOG_API_RESPONSES = False

# =============================================================================
# ПРОВЕРКА КОНФИГУРАЦИИ
# =============================================================================
def validate_config():
    errors = []
    warnings = []

    # Проверка настроек торговли
    if ENABLE_LIVE_TRADING and not LIVE_TRADING_DRY_RUN:
        if not API_KEY or not API_SECRET:
            errors.append("Для реальной торговли необходимы API_KEY и API_SECRET")
        if API_TESTNET:
            warnings.append("Включена тестовая сеть (API_TESTNET=True), реальные сделки выполняться не будут")
        else:
            warnings.append("ВНИМАНИЕ: Включена РЕАЛЬНАЯ торговля на основной сети!")

    # Проверка размеров сделок
    if ENABLE_LIVE_TRADING and LIVE_TRADING_MAX_TRADE_USDT > 10000:
        warnings.append(f"Очень большой размер сделки: {LIVE_TRADING_MAX_TRADE_USDT} USDT")

    # Проверка интервалов
    if SCAN_INTERVAL < 0.1:
        warnings.append("Очень короткий интервал сканирования может вызвать превышение лимитов API")

    # Проверка минимальной суммы сделки
    if LIVE_TRADING_MIN_TRADE_USDT < 5.0:
        warnings.append("Минимальная сумма сделки может быть слишком мала для Bybit (рекомендуется >= $5)")

    # Проверка ликвидности
    if MIN_LIQUIDITY_VOLUME < LIVE_TRADING_MIN_TRADE_USDT:
        warnings.append(f"MIN_LIQUIDITY_VOLUME ({MIN_LIQUIDITY_VOLUME}) меньше LIVE_TRADING_MIN_TRADE_USDT ({LIVE_TRADING_MIN_TRADE_USDT})")

    # Проверка прибыльности
    if MIN_PROFIT_THRESHOLD < 0.001:
        warnings.append("Очень низкий порог прибыли может привести к убыточным сделкам из-за комиссий")

    # Проверка API лимитов
    if API_RATE_LIMIT > 1000:
        warnings.append("Высокий API_RATE_LIMIT может вызвать блокировку от биржи")

    # Проверка агрессивных настроек
    if MAX_CONCURRENT_REQUESTS > 100:
        warnings.append("Высокое значение MAX_CONCURRENT_REQUESTS может перегрузить API")

    if LIVE_TRADING_ORDER_GAP_SEC < 0.1:
        warnings.append("Очень короткий интервал между ордерами может вызвать ошибки API")

    return errors, warnings