import logging
import sys
from logging.handlers import RotatingFileHandler
from config import *


def setup_logging():
    """Настройка логирования - УЛУЧШЕННАЯ"""
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    # Очищаем существующие handlers
    logging.getLogger().handlers.clear()

    handlers = []

    # Консольный обработчик с цветной подсветкой
    console_handler = logging.StreamHandler(sys.stdout)

    # Улучшенный формат для консоли
    console_format = "%(asctime)s [%(levelname)8s] %(name)-20s: %(message)s"
    console_formatter = logging.Formatter(
        console_format,
        datefmt="%H:%M:%S"
    )

    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    handlers.append(console_handler)

    # Файловый обработчик
    if LOG_FILE:
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_MAX_SIZE,
                backupCount=LOG_BACKUP_COUNT,
                encoding=LOG_ENCODING
            )

            # Подробный формат для файла
            file_format = "%(asctime)s [%(levelname)8s] %(name)-25s %(filename)s:%(lineno)d - %(message)s"
            file_formatter = logging.Formatter(file_format)

            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(log_level)
            handlers.append(file_handler)

        except Exception as e:
            print(f"⚠️  Не удалось создать файл лога: {e}")

    # Настройка корневого логгера
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )

    # Настройка уровней для сторонних библиотек
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    # Тестовое сообщение
    logger = logging.getLogger(__name__)
    logger.info(f"📝 Логирование настроено (уровень: {LOG_LEVEL})")


def check_dependencies():
    """Проверка зависимостей - УЛУЧШЕННАЯ"""
    required_packages = ['aiohttp']
    optional_packages = {
        'numpy': 'для расчетов статистики',
        'playsound': 'для звуковых уведомлений'
    }

    missing_required = []
    missing_optional = []

    # Проверяем обязательные пакеты
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_required.append(package)

    # Проверяем опциональные пакеты
    for package, description in optional_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing_optional.append((package, description))

    # Сообщения об отсутствующих пакетах
    if missing_required:
        logging.critical("❌ Отсутствуют обязательные пакеты:")
        for package in missing_required:
            logging.critical(f"   - {package}")
        logging.critical("📦 Установите их: pip install " + " ".join(missing_required))
        return False

    if missing_optional:
        logging.warning("⚠️  Отсутствуют опциональные пакеты:")
        for package, description in missing_optional:
            logging.warning(f"   - {package}: {description}")

    logging.info("✅ Все обязательные зависимости установлены")
    return True


def print_startup_info():
    """Вывод информации о запуске - РАСШИРЕННАЯ"""

    print("=" * 80)
    print("🚀 АРБИТРАЖНЫЙ БОТ BYBIT - АГРЕССИВНАЯ ВЕРСИЯ")
    print("=" * 80)

    # Основные настройки торговли
    print("📊 ТОРГОВЫЕ НАСТРОЙКИ:")
    print(f"   💰 Минимальная прибыль: {MIN_PROFIT_THRESHOLD}%")
    print(f"   🏦 Комиссия торгов: {TRADING_COMMISSION * 100}%")
    print(f"   💵 Тестовая сумма: ${INITIAL_AMOUNT:,.0f}")

    # Настройки сканирования
    print("\n🔍 НАСТРОЙКИ СКАНИРОВАНИЯ:")
    print(f"   ⏱️  Интервал: {SCAN_INTERVAL}s")
    print(f"   📈 Показывать возможностей: {MAX_OPPORTUNITIES_DISPLAY}")
    print(f"   💱 Валютных пар: {len(CROSS_CURRENCIES)}")
    print(f"   🔄 Параллельных запросов: {MAX_CONCURRENT_REQUESTS}")

    # Технические настройки
    print("\n⚙️  ТЕХНИЧЕСКИЕ НАСТРОЙКИ:")
    print(f"   📝 Уровень логирования: {LOG_LEVEL}")
    print(f"   💾 Кеш orderbook: {'включен' if USE_ORDERBOOK_CACHE else 'выключен'}")
    if USE_ORDERBOOK_CACHE:
        print(f"   ⏰ TTL кеша: {ORDERBOOK_CACHE_TTL}s")

    # Режим торговли
    print("\n💼 РЕЖИМ ТОРГОВЛИ:")
    if ENABLE_LIVE_TRADING:
        if LIVE_TRADING_DRY_RUN:
            print("   🔴 DRY RUN - Только симуляция сделок")
        else:
            network = "🧪 ТЕСТОВАЯ СЕТЬ" if API_TESTNET else "🟡 РЕАЛЬНАЯ ТОРГОВЛЯ"
            api_status = "✅ Настроены" if API_KEY and API_SECRET else "❌ Не настроены"
            print(f"   {network}")
            print(f"   🔑 API ключи: {api_status}")
            print(f"   💰 Лимит сделки: ${LIVE_TRADING_MIN_TRADE_USDT}-${LIVE_TRADING_MAX_TRADE_USDT}")
    else:
        print("   🟢 ТОЛЬКО МОНИТОРИНГ - торговля отключена")

    # Проверка конфигурации
    errors, warnings, info_messages = validate_config()

    if errors:
        print("\n❌ КРИТИЧЕСКИЕ ОШИБКИ:")
        for error in errors:
            print(f"   • {error}")

    if warnings:
        print("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"   • {warning}")

    # Информация о агрессивных настройках
    if hasattr(globals(), 'info_messages') or len(CROSS_CURRENCIES) > 50:
        print("\n🎯 АГРЕССИВНЫЕ НАСТРОЙКИ:")
        print(f"   🔥 Максимальное покрытие: {len(CROSS_CURRENCIES)} валютных пар")
        print(f"   ⚡ Высокочастотное сканирование: каждые {SCAN_INTERVAL}s")
        print(f"   🔍 Микро-арбитраж: порог {MIN_PROFIT_THRESHOLD}%")
        print(f"   📊 Анализ до {MAX_OPPORTUNITIES_DISPLAY} возможностей")

    # Список некоторых валют для понимания
    sample_currencies = CROSS_CURRENCIES[:15]
    remaining = len(CROSS_CURRENCIES) - 15
    currencies_text = ', '.join(sample_currencies)
    if remaining > 0:
        currencies_text += f" и еще {remaining}"
    print(f"\n💱 ВАЛЮТЫ: {currencies_text}")

    print("=" * 80)

    # Дополнительные предупреждения для агрессивного режима
    if SCAN_INTERVAL < 1.0 or MAX_CONCURRENT_REQUESTS > 100:
        print("⚡ ВНИМАНИЕ: Включен агрессивный режим!")
        print("   • Высокая частота запросов к API")
        print("   • Следите за лимитами Bybit")
        print("   • Возможны временные блокировки при превышении лимитов")
        print("=" * 80)

    print("💡 Управление:")
    print("   • Для остановки: Ctrl+C")
    print("   • Логи сохраняются в:", LOG_FILE if LOG_FILE else "консоль")
    print("   • CSV файлы: opportunities.csv, executed_trades.csv")
    print("=" * 80)


def format_currency_amount(amount: float, currency: str = "USDT") -> str:
    """Форматирует сумму валюты для красивого вывода"""
    if amount >= 1000000:
        return f"${amount / 1000000:.2f}M {currency}"
    elif amount >= 1000:
        return f"${amount / 1000:.1f}K {currency}"
    else:
        return f"${amount:.2f} {currency}"


def format_percentage(value: float, precision: int = 3) -> str:
    """Форматирует процентное значение"""
    if value >= 10:
        return f"{value:.1f}%"
    elif value >= 1:
        return f"{value:.2f}%"
    else:
        return f"{value:.{precision}f}%"


def format_duration(seconds: float) -> str:
    """Форматирует продолжительность в человекочитаемый вид"""
    if seconds < 60:
        return f"{seconds:.1f}с"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}м"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}ч"


def print_performance_stats(scan_times: list, opportunities_found: int, total_scans: int):
    """Выводит статистику производительности"""
    if not scan_times:
        return

    avg_time = sum(scan_times) / len(scan_times)
    min_time = min(scan_times)
    max_time = max(scan_times)

    print("\n📊 СТАТИСТИКА ПРОИЗВОДИТЕЛЬНОСТИ:")
    print(f"   ⏱️  Среднее время сканирования: {avg_time:.2f}с")
    print(f"   🏃‍♂️ Быстрейшее сканирование: {min_time:.2f}с")
    print(f"   🐌 Самое долгое сканирование: {max_time:.2f}с")
    print(f"   🎯 Найдено возможностей: {opportunities_found}")
    print(f"   📈 Эффективность: {opportunities_found / max(1, total_scans) * 100:.1f}% сканирований с результатом")


def validate_trading_settings():
    """Валидирует настройки торговли"""
    issues = []

    if LIVE_TRADING_MIN_TRADE_USDT < 5.0:
        issues.append("Минимальная сумма сделки может быть слишком мала для Bybit")

    if TRADING_COMMISSION * 3 > MIN_PROFIT_THRESHOLD:
        issues.append(
            f"Порог прибыли ({MIN_PROFIT_THRESHOLD}%) слишком низок относительно комиссии ({TRADING_COMMISSION * 100}%)")

    if SCAN_INTERVAL < 0.3:
        issues.append("Очень частое сканирование может привести к блокировке API")

    return issues