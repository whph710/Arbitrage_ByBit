# config.py — Конфигурационные настройки для арбитражного бота Bybit
# =============================================================================
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# =============================================================================
# ОСНОВНЫЕ НАСТРОЙКИ ТОРГОВЛИ - ОПТИМИЗИРОВАНО ДЛЯ АГРЕССИВНОГО ПОИСКА
# =============================================================================
MIN_PROFIT_THRESHOLD = 0.001  # СНИЖЕНО: 0.01% для поиска минимальных возможностей
TRADING_COMMISSION = 0.001  # Комиссия Bybit 0.1%
INITIAL_AMOUNT = 1000.0  # УВЕЛИЧЕНО: для более точных расчетов больших арбитражей
MAX_OPPORTUNITIES_DISPLAY = 100  # УВЕЛИЧЕНО: показываем больше возможностей

# =============================================================================
# НАСТРОЙКИ API И ПОДКЛЮЧЕНИЯ - ОПТИМИЗИРОВАНО
# =============================================================================
BYBIT_BASE_URL = "https://api.bybit.com/v5"
HTTP_TIMEOUT = 5  # УВЕЛИЧЕНО: для стабильности
API_RETRY_ATTEMPTS = 3  # ОПТИМИЗИРОВАНО: быстрее реагируем на ошибки
API_RETRY_DELAY = 0.1  # УМЕНЬШЕНО: быстрее повторяем запросы

# =============================================================================
# НАСТРОЙКИ API КЛЮЧЕЙ ДЛЯ РЕАЛЬНОЙ ТОРГОВЛИ
# =============================================================================
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
API_TESTNET = False
TESTNET_BASE_URL = "https://api-testnet.bybit.com/v5"

# =============================================================================
# ВРЕМЕННЫЕ ИНТЕРВАЛЫ - АГРЕССИВНЫЕ НАСТРОЙКИ
# =============================================================================
SCAN_INTERVAL = 2  # УМЕНЬШЕНО: сканируем каждые 0.5 секунды
ERROR_RETRY_INTERVAL = 1  # УМЕНЬШЕНО: быстрее восстанавливаемся после ошибок
ORDERBOOK_TIMEOUT = 5  # УВЕЛИЧЕНО: даем больше времени на получение данных

# =============================================================================
# ВАЛЮТНЫЕ ПАРЫ - РАСШИРЕННЫЙ СПИСОК ДЛЯ МАКСИМАЛЬНОГО ПОКРЫТИЯ
# =============================================================================
CROSS_CURRENCIES = [
    # Стейблкоины (основа арбитража)
    'USDT', 'USDC', 'BUSD', 'DAI', 'USD', 'TUSD', 'FDUSD',

    # Топ криптовалюты (высокая ликвидность)
    'BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'DOGE', 'MATIC', 'TRX', 'AVAX',
    'DOT', 'LTC', 'LINK', 'ATOM', 'NEAR', 'FTM', 'XLM', 'ICP', 'AAVE', 'UNI',

    # Популярные альткоины
    'VET', 'XTZ', 'ALGO', 'MANA', 'GRT', 'SAND', 'CRV', 'MKR', 'COMP', 'SNX',
    'SUSHI', 'BAT', 'ENJ', 'ZRX', 'LRC', 'KNC', 'REN', 'STORJ', 'NMR', 'BAND',

    # Мем токены (высокая волатильность = больше возможностей)
    'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'DEGEN', 'BOME', 'MYRO',

    # DeFi токены
    'CRV', 'CAKE', 'JOE', 'RAY', '1INCH', 'YFI', 'ALPHA', 'BETA', 'AUTO',

    # Метавселенная и игровые токены
    'AXS', 'SLP', 'GALA', 'ENJ', 'CHZ', 'FLOW', 'WAX', 'ALICE', 'TLM',

    # L2 и scaling решения
    'ARB', 'OP', 'MATIC', 'LRC', 'IMX',

    # AI и новые технологии
    'FET', 'AGIX', 'RNDR', 'OCEAN', 'TAO'
]

EXCLUDED_CURRENCIES = [
    # Исключаем проблемные или малоликвидные пары
    'PAXG', 'TUSD', 'USDD'  # Минимальные исключения для максимального покрытия
]

MIN_LIQUIDITY_VOLUME = 20  # СНИЖЕНО: ищем даже малые возможности

# =============================================================================
# НАСТРОЙКИ ЛОГИРОВАНИЯ - ПОДРОБНОЕ
# =============================================================================
LOG_LEVEL = "DEBUG"  # Максимальная детализация для отладки
LOG_FORMAT = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"
LOG_FILE = "arbitrage_aggressive.log"
LOG_MAX_SIZE = 100 * 1024 * 1024  # 100MB
LOG_BACKUP_COUNT = 10
LOG_ENCODING = "utf-8"

# =============================================================================
# ПРОДВИНУТЫЕ НАСТРОЙКИ - АГРЕССИВНЫЕ
# =============================================================================
USE_ORDERBOOK_CACHE = False  # ВКЛЮЧЕНО: кешируем для скорости
ORDERBOOK_CACHE_TTL = 1  # 1 секунда кеша - баланс между скоростью и актуальностью
MAX_CONCURRENT_REQUESTS = 200  # ОПТИМИЗИРОВАНО: много, но не критично
PERFORMANCE_DIAGNOSTICS = True

# =============================================================================
# ФИЛЬТРАЦИЯ - МИНИМАЛЬНАЯ ДЛЯ МАКСИМАЛЬНОГО ПОИСКА
# =============================================================================
FILTER_LOW_LIQUIDITY = True
MAX_SPREAD_PERCENT = 15.0  # УВЕЛИЧЕНО: позволяем больше спредов
EXCLUDE_HIGH_VOLATILITY = False  # ОТКЛЮЧЕНО: волатильность = возможности
MAX_VOLATILITY_PERCENT = 100.0

# =============================================================================
# СЕТЕВЫЕ НАСТРОЙКИ - ОПТИМИЗИРОВАННЫЕ
# =============================================================================
API_RATE_LIMIT = 600  # ВЫСОКИЙ: 10 запросов в секунду
SSL_VERIFY = True
NETWORK_TIMEOUT = 15

# =============================================================================
# ЭКСПЕРИМЕНТАЛЬНЫЕ НАСТРОЙКИ - ВСЕ ВКЛЮЧЕНО
# =============================================================================
EXPERIMENTAL_OPTIMIZATIONS = True
ML_VOLATILITY_PREDICTION = True
ORDERBOOK_DEPTH_ANALYSIS = True
ORDERBOOK_LEVELS = 20  # УМЕНЬШЕНО: для скорости, но достаточно для анализа

# =============================================================================
# НАСТРОЙКИ АВТОНОМНОЙ ТОРГОВЛИ - ОСТОРОЖНЫЕ ЗНАЧЕНИЯ
# =============================================================================
ENABLE_LIVE_TRADING = True
LIVE_TRADING_DRY_RUN = True  # БЕЗОПАСНО: по умолчанию только симуляция

LIVE_TRADING_MAX_TRADE_USDT = 100.0  # БЕЗОПАСНОЕ ЗНАЧЕНИЕ для начала
LIVE_TRADING_MIN_TRADE_USDT = 10.0  # Минимум для Bybit

LIVE_TRADING_MAX_EXEC_PER_MIN = 30  # УВЕЛИЧЕНО: до 30 сделок в минуту
LIVE_TRADING_ORDER_GAP_SEC = 0.2  # УВЕЛИЧЕНО: безопасная пауза между ордерами
ALLOW_PARTIAL_FILL_EXECUTION = True
REQUIRE_BALANCE_CHECK_BEFORE_LIVE = True

# =============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ БЕЗОПАСНОСТИ
# =============================================================================
SESSION_MAX_DRAWDOWN_PERCENT = 30.0  # СНИЖЕНО: более консервативно
LOG_API_RESPONSES = False  # Отключаем для производительности

# =============================================================================
# НОВЫЕ ОПТИМИЗАЦИИ ДЛЯ АГРЕССИВНОГО ПОИСКА
# =============================================================================
# Минимальные требования для поиска микро-арбитража
MICRO_ARBITRAGE_MODE = True
MICRO_PROFIT_THRESHOLD = 0.005  # 0.005% = 5 базисных пунктов

# Расширенные комбинации валютных пар
ENABLE_REVERSE_PAIRS = True  # Ищем в обоих направлениях
MAX_PATHS_TO_ANALYZE = 5000  # Максимум путей для анализа

# Оптимизация производительности
PARALLEL_PROCESSING = True
BATCH_SIZE_ORDERBOOKS = 50  # Батчи для получения orderbook'ов

# Статистика и мониторинг
ENABLE_DETAILED_STATS = True
STATS_WINDOW_MINUTES = 60  # Окно для расчета статистики


# =============================================================================
# ПРОВЕРКА КОНФИГУРАЦИИ - РАСШИРЕННАЯ
# =============================================================================
def validate_config():
    errors = []
    warnings = []

    # Проверка торговых настроек
    if ENABLE_LIVE_TRADING and not LIVE_TRADING_DRY_RUN:
        if not API_KEY or not API_SECRET:
            errors.append("❌ Для реальной торговли необходимы API_KEY и API_SECRET")

        if API_TESTNET:
            warnings.append("🧪 Используется тестовая сеть (безопасно)")
        else:
            warnings.append("⚠️ РЕАЛЬНАЯ ТОРГОВЛЯ ВКЛЮЧЕНА! Будьте осторожны!")

    # Проверка размеров сделок
    if LIVE_TRADING_MAX_TRADE_USDT > 500:
        warnings.append(f"💰 Большой размер сделки: ${LIVE_TRADING_MAX_TRADE_USDT}")

    # Проверка агрессивности
    if SCAN_INTERVAL < 0.5:
        warnings.append("⚡ Очень агрессивное сканирование - возможны лимиты API")

    if MAX_CONCURRENT_REQUESTS > 150:
        warnings.append("🚀 Высокий параллелизм - следите за нагрузкой")

    # Проверка прибыльности
    if MIN_PROFIT_THRESHOLD < TRADING_COMMISSION * 3:
        warnings.append("📉 Порог прибыли может быть слишком низким из-за комиссий")

    # Проверка ликвидности
    if MIN_LIQUIDITY_VOLUME < LIVE_TRADING_MIN_TRADE_USDT:
        warnings.append("💧 MIN_LIQUIDITY_VOLUME меньше мин. суммы сделки")

    # Позитивная информация об агрессивных настройках
    info_messages = []

    if len(CROSS_CURRENCIES) > 50:
        info_messages.append(f"🎯 Максимальное покрытие: {len(CROSS_CURRENCIES)} валют")

    if MIN_PROFIT_THRESHOLD <= 0.01:
        info_messages.append(f"🔍 Микро-арбитраж: порог {MIN_PROFIT_THRESHOLD}%")

    if SCAN_INTERVAL <= 1.0:
        info_messages.append(f"⚡ Высокочастотное сканирование: {SCAN_INTERVAL}s")

    if MAX_OPPORTUNITIES_DISPLAY >= 100:
        info_messages.append(f"📊 Показ {MAX_OPPORTUNITIES_DISPLAY} лучших возможностей")

    return errors, warnings, info_messages


# =============================================================================
# ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ ДЛЯ АГРЕССИВНОГО РЕЖИМА
# =============================================================================

def get_aggressive_config_summary():
    """Возвращает сводку агрессивных настроек"""
    return {
        "scan_frequency": f"Каждые {SCAN_INTERVAL}s",
        "profit_threshold": f"{MIN_PROFIT_THRESHOLD}%",
        "currency_pairs": len(CROSS_CURRENCIES),
        "max_concurrent": MAX_CONCURRENT_REQUESTS,
        "orderbook_cache": f"{ORDERBOOK_CACHE_TTL}s" if USE_ORDERBOOK_CACHE else "Disabled",
        "max_opportunities": MAX_OPPORTUNITIES_DISPLAY,
        "trading_mode": "DRY RUN" if LIVE_TRADING_DRY_RUN else ("TESTNET" if API_TESTNET else "LIVE"),
        "micro_arbitrage": MICRO_ARBITRAGE_MODE
    }


def print_aggressive_mode_warning():
    """Выводит предупреждение об агрессивном режиме"""
    print("🚨" + "=" * 78 + "🚨")
    print("⚡ АГРЕССИВНЫЙ РЕЖИМ АКТИВИРОВАН ⚡")
    print("🚨" + "=" * 78 + "🚨")
    print("📈 Настройки оптимизированы для максимального поиска возможностей")
    print(f"🔍 Порог прибыли: {MIN_PROFIT_THRESHOLD}% (микро-арбитраж)")
    print(f"⚡ Частота сканирования: {SCAN_INTERVAL}s")
    print(f"💱 Валютных пар: {len(CROSS_CURRENCIES)}")
    print(f"🔄 Параллельных запросов: {MAX_CONCURRENT_REQUESTS}")
    print("⚠️  Следите за лимитами API и производительностью!")
    print("🚨" + "=" * 78 + "🚨")