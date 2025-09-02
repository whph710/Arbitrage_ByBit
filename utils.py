import logging
import sys
from logging.handlers import RotatingFileHandler
from config import LOG_LEVEL, LOG_FORMAT, LOG_FILE, LOG_MAX_SIZE, LOG_BACKUP_COUNT, LOG_ENCODING


def setup_logging():
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    handlers = []

    # Консольный обработчик (всегда UTF-8)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    console_handler.setLevel(log_level)
    handlers.append(console_handler)

    # Файловый обработчик с правильной кодировкой
    if LOG_FILE:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_SIZE,
            backupCount=LOG_BACKUP_COUNT,
            encoding=LOG_ENCODING  # Добавлена кодировка UTF-8
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    # Настройка корневого логгера
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        format=LOG_FORMAT,
        force=True  # Принудительно переопределить существующие настройки
    )


def check_dependencies():
    required_packages = ['aiohttp']
    optional_packages = {'playsound': False}  # SOUND_NOTIFICATIONS отключен
    missing_required = []
    missing_optional = []

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_required.append(package)

    for package, needed in optional_packages.items():
        if needed:
            try:
                __import__(package)
            except ImportError:
                missing_optional.append(package)

    if missing_required:
        logging.critical(f"Отсутствуют обязательные пакеты: {missing_required}")
        logging.critical("Установите их: pip install aiohttp")
        return False

    if missing_optional:
        logging.warning(f"Отсутствуют опциональные пакеты: {missing_optional}")
        logging.warning("Установите их: pip install playsound")

    return True


def print_startup_info():
    from config import (MIN_PROFIT_THRESHOLD, TRADING_COMMISSION, SCAN_INTERVAL,
                        MAX_OPPORTUNITIES_DISPLAY, CROSS_CURRENCIES, LOG_LEVEL,
                        ENABLE_LIVE_TRADING, LIVE_TRADING_DRY_RUN, API_TESTNET,
                        API_KEY, validate_config)

    print("=" * 80)
    print("🚀 АРБИТРАЖНЫЙ БОТ BYBIT - ЗАПУСК")
    print("=" * 80)
    print(f"📊 Минимальная прибыль: {MIN_PROFIT_THRESHOLD}%")
    print(f"💰 Комиссия торгов: {TRADING_COMMISSION * 100}%")
    print(f"⏱️  Интервал сканирования: {SCAN_INTERVAL}s")
    print(f"🔢 Максимум показываемых возможностей: {MAX_OPPORTUNITIES_DISPLAY}")
    print(f"💱 Базовые валюты: {', '.join(CROSS_CURRENCIES)}")
    print(f"📝 Уровень логирования: {LOG_LEVEL}")

    # Информация о торговом режиме
    print("─" * 80)
    if ENABLE_LIVE_TRADING:
        if LIVE_TRADING_DRY_RUN:
            print("🔴 РЕЖИМ: Тестовый (DRY RUN) - сделки не выполняются")
        else:
            network = "ТЕСТОВАЯ СЕТЬ" if API_TESTNET else "РЕАЛЬНАЯ ТОРГОВЛЯ"
            api_status = "✅ Настроен" if API_KEY else "❌ Не настроен"
            print(f"🟡 РЕЖИМ: {network}")
            print(f"🔑 API ключ: {api_status}")
    else:
        print("🟢 РЕЖИМ: Только мониторинг - торговля отключена")

    # Проверка конфигурации
    errors, warnings = validate_config()
    if errors:
        print("─" * 80)
        print("❌ ОШИБКИ КОНФИГУРАЦИИ:")
        for error in errors:
            print(f"   • {error}")

    if warnings:
        print("─" * 80)
        print("⚠️  ПРЕДУПРЕЖДЕНИЯ:")
        for warning in warnings:
            print(f"   • {warning}")

    print("=" * 80)
    print("💡 Для остановки нажмите Ctrl+C")
    print("=" * 80)