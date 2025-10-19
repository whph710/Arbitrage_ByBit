# configs_continuous.py
# Конфигурация для непрерывного мониторинга арбитража
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# ============================================================================
# ОСНОВНЫЕ ПАРАМЕТРЫ НЕПРЕРЫВНОГО МОНИТОРИНГА
# ============================================================================
START_AMOUNT = float(os.getenv("START_AMOUNT", 100.0))
MIN_SPREAD = float(os.getenv("MIN_SPREAD", 0.3))  # Минимальный спред для вывода
MIN_PROFIT_USD = float(os.getenv("MIN_PROFIT_USD", 0.5))  # Минимальная прибыль в долларах
MAX_REASONABLE_SPREAD = float(os.getenv("MAX_REASONABLE_SPREAD", 50.0))

# Интервал между проверками (секунды)
# Рекомендуется: 15-30 секунд для баланса скорости и нагрузки
MONITORING_INTERVAL = float(os.getenv("MONITORING_INTERVAL", 20.0))

# Автоматическая перезагрузка данных (секунды)
# Данные BestChange и Bybit будут перезагружаться автоматически
DATA_RELOAD_INTERVAL = int(os.getenv("DATA_RELOAD_INTERVAL", 3600))  # 1 час

# Минимальное время между показом одной и той же связки (секунды)
MIN_TIME_BETWEEN_DUPLICATE = int(os.getenv("MIN_TIME_BETWEEN_DUPLICATE", 60))

# ============================================================================
# ФИЛЬТРАЦИЯ ПО ЛИКВИДНОСТИ (для скорости и качества)
# ============================================================================
MIN_24H_VOLUME_USDT = float(os.getenv("MIN_24H_VOLUME_USDT", 100000.0))
MIN_LIQUIDITY_SCORE = float(os.getenv("MIN_LIQUIDITY_SCORE", 40.0))
USE_ONLY_TOP_LIQUID_COINS = int(os.getenv("USE_ONLY_TOP_LIQUID_COINS", 200))

# ============================================================================
# ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ
# ============================================================================
# Количество параллельных запросов к BestChange
# Больше = быстрее, но выше нагрузка
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 100))

# Задержка между запросами (секунды)
# Меньше = быстрее, но риск rate limit
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 0.05))

# Размер батча для групповых запросов
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 200))

# Повторные попытки при ошибках
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", 0.5))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

# ============================================================================
# КЭШИРОВАНИЕ ДЛЯ УСКОРЕНИЯ
# ============================================================================
ENABLE_CACHE = True
CACHE_HOT_PAIRS = int(os.getenv("CACHE_HOT_PAIRS", 100))  # Количество "горячих" пар
CACHE_TTL = int(os.getenv("CACHE_TTL", 300))  # Время жизни кэша (секунды)

# ============================================================================
# WEBSOCKET (для real-time обновлений цен)
# ============================================================================
WEBSOCKET_ENABLED = os.getenv("WEBSOCKET_ENABLED", "True").lower() in ("true", "1", "yes")
WEBSOCKET_RECONNECT_DELAY = float(os.getenv("WEBSOCKET_RECONNECT_DELAY", 5.0))
WEBSOCKET_PING_INTERVAL = float(os.getenv("WEBSOCKET_PING_INTERVAL", 20.0))

# ============================================================================
# API НАСТРОЙКИ
# ============================================================================
BYBIT_API_URL = os.getenv("BYBIT_API_URL", "https://api.bybit.com")
BYBIT_WS_URL = os.getenv("BYBIT_WS_URL", "wss://stream.bybit.com/v5/public/spot")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")

BESTCHANGE_API_KEY = os.getenv("BESTCHANGE_API_KEY", "")

if not BESTCHANGE_API_KEY:
    print("⚠️  КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ: BESTCHANGE_API_KEY не задан!")
    print("    Непрерывный мониторинг не будет работать без API ключа BestChange")
    print("    Получите ключ на: https://www.bestchange.com/wiki/api.html")
    print("    Добавьте в .env файл: BESTCHANGE_API_KEY=ваш_ключ\n")

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Сохранять ли найденные связки в файл (помимо консоли)
SAVE_OPPORTUNITIES_TO_FILE = os.getenv("SAVE_OPPORTUNITIES_TO_FILE", "True").lower() in ("true", "1", "yes")
OPPORTUNITIES_LOG_FILE = LOGS_DIR / "opportunities.log"

# Уровень детализации логов
# 0 = минимум (только найденные связки)
# 1 = стандарт (+ статистика каждые 10 итераций)
# 2 = максимум (+ детали каждой итерации)
LOG_LEVEL = int(os.getenv("LOG_LEVEL", 1))

# ============================================================================
# ФИЛЬТРАЦИЯ МОНЕТ (опционально)
# ============================================================================
BLACKLIST_COINS = set()
WHITELIST_COINS = set()
ENABLE_COIN_FILTER = False

# ============================================================================
# РЕЗУЛЬТАТЫ
# ============================================================================
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ============================================================================
# DEBUG MODE
# ============================================================================
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

# ============================================================================
# ВЫВОД КОНФИГУРАЦИИ ПРИ ЗАПУСКЕ
# ============================================================================
def print_config_summary():
    """Выводит сводку конфигурации"""
    print("\n" + "="*100)
    print("⚙️  КОНФИГУРАЦИЯ НЕПРЕРЫВНОГО МОНИТОРИНГА")
    print("="*100)
    print(f"💰 Начальная сумма: ${START_AMOUNT}")
    print(f"📊 Минимальный спред: {MIN_SPREAD}%")
    print(f"💵 Минимальная прибыль: ${MIN_PROFIT_USD}")
    print(f"⏱️  Интервал проверки: {MONITORING_INTERVAL}с")
    print(f"🔄 Перезагрузка данных: каждые {DATA_RELOAD_INTERVAL//60}мин")
    print(f"🚫 Фильтр дубликатов: {MIN_TIME_BETWEEN_DUPLICATE}с")
    print(f"\n💧 ЛИКВИДНОСТЬ:")
    print(f"   • Мин. объем 24ч: ${MIN_24H_VOLUME_USDT:,.0f}")
    print(f"   • Мин. оценка: {MIN_LIQUIDITY_SCORE}")
    print(f"   • Топ монет: {USE_ONLY_TOP_LIQUID_COINS}")
    print(f"\n⚡ ПРОИЗВОДИТЕЛЬНОСТЬ:")
    print(f"   • Параллельных запросов: {MAX_CONCURRENT_REQUESTS}")
    print(f"   • Задержка запросов: {REQUEST_DELAY}с")
    print(f"   • Размер батча: {BATCH_SIZE}")
    print(f"\n🔌 WEBSOCKET: {'✅ Включен' if WEBSOCKET_ENABLED else '❌ Выключен'}")
    print(f"💾 КЭШИРОВАНИЕ: {'✅ Включено' if ENABLE_CACHE else '❌ Выключено'}")
    if ENABLE_CACHE:
        print(f"   • Горячих пар: {CACHE_HOT_PAIRS}")
    print(f"\n📝 ЛОГИРОВАНИЕ:")
    print(f"   • Уровень: {LOG_LEVEL}")
    print(f"   • Сохранение в файл: {'Да' if SAVE_OPPORTUNITIES_TO_FILE else 'Нет'}")
    print(f"\n🔑 API КЛЮЧИ:")
    print(f"   • Bybit: {'✅ Задан' if BYBIT_API_KEY else '⚠️  Не задан (не обязателен)'}")
    print(f"   • BestChange: {'✅ Задан' if BESTCHANGE_API_KEY else '❌ НЕ ЗАДАН (КРИТИЧНО!)'}")
    print("="*100 + "\n")

if __name__ == "__main__":
    print_config_summary()