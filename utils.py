import logging
import sys
from logging.handlers import RotatingFileHandler
from config import LOG_LEVEL, LOG_FORMAT, LOG_FILE, LOG_MAX_SIZE, LOG_BACKUP_COUNT

def setup_logging():
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handlers.append(console_handler)
    if LOG_FILE:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_SIZE,
            backupCount=LOG_BACKUP_COUNT
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handlers.append(file_handler)
    logging.basicConfig(level=log_level, handlers=handlers, format=LOG_FORMAT)

def check_dependencies():
    required_packages = ['aiohttp', 'sqlite3']
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
    from config import MIN_PROFIT_THRESHOLD, TRADING_COMMISSION, SCAN_INTERVAL, MAX_OPPORTUNITIES_DISPLAY, CROSS_CURRENCIES, LOG_LEVEL

    print("=" * 80)
    print("🚀 АРБИТРАЖНЫЙ БОТ BYBIT - ЗАПУСК")
    print("=" * 80)
    print(f"📊 Минимальная прибыль: {MIN_PROFIT_THRESHOLD}%")
    print(f"💰 Комиссия торгов: {TRADING_COMMISSION * 100}%")
    print(f"⏱️  Интервал сканирования: {SCAN_INTERVAL}s")
    print(f"🔢 Максимум показываемых возможностей: {MAX_OPPORTUNITIES_DISPLAY}")
    print(f"💱 Базовые валюты: {', '.join(CROSS_CURRENCIES)}")
    print(f"📝 Уровень логирования: {LOG_LEVEL}")
    print("=" * 80)
    print("💡 Для остановки нажмите Ctrl+C")
    print("=" * 80)
