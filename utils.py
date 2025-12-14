"""
Утилиты для валидации данных и кэширования
"""
import math
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from collections import OrderedDict


def is_valid_number(value: Any) -> bool:
    """
    Проверяет, является ли значение валидным числом (не NaN, не Infinity)
    
    Args:
        value: Значение для проверки
        
    Returns:
        True если значение валидно, False иначе
    """
    if value is None:
        return False
    
    try:
        float_val = float(value)
        # Проверяем на NaN и Infinity
        if math.isnan(float_val) or math.isinf(float_val):
            return False
        # Проверяем на отрицательные значения для цен и курсов
        if float_val <= 0:
            return False
        return True
    except (ValueError, TypeError):
        return False


def validate_price(price: Optional[float], name: str = "цена") -> bool:
    """
    Валидирует цену
    
    Args:
        price: Цена для проверки
        name: Название для сообщения об ошибке
        
    Returns:
        True если цена валидна
    """
    if not is_valid_number(price):
        return False
    return True


def validate_rate(rate: Optional[float], name: str = "курс") -> bool:
    """
    Валидирует курс обмена
    
    Args:
        rate: Курс для проверки
        name: Название для сообщения об ошибке
        
    Returns:
        True если курс валиден
    """
    return validate_price(rate, name)


class TTLCache:
    """
    Кэш с временем жизни (TTL) и ограничением размера
    Использует LRU (Least Recently Used) стратегию
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        Args:
            max_size: Максимальный размер кэша
            ttl_seconds: Время жизни записей в секундах
        """
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, datetime] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """
        Получает значение из кэша
        
        Args:
            key: Ключ
            
        Returns:
            Значение или None если не найдено или истек срок
        """
        if key not in self.cache:
            return None
        
        # Проверяем TTL
        if key in self.timestamps:
            if datetime.now() - self.timestamps[key] > self.ttl:
                # Истек срок - удаляем
                del self.cache[key]
                del self.timestamps[key]
                return None
        
        # Перемещаем в конец (LRU)
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: str, value: Any) -> None:
        """
        Сохраняет значение в кэш
        
        Args:
            key: Ключ
            value: Значение
        """
        # Если ключ уже есть, обновляем
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            # Если кэш полон, удаляем самый старый
            if len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                if oldest_key in self.timestamps:
                    del self.timestamps[oldest_key]
        
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
    
    def clear(self) -> None:
        """Очищает весь кэш"""
        self.cache.clear()
        self.timestamps.clear()
    
    def size(self) -> int:
        """Возвращает текущий размер кэша"""
        return len(self.cache)
    
    def cleanup_expired(self) -> int:
        """
        Удаляет истекшие записи
        
        Returns:
            Количество удаленных записей
        """
        now = datetime.now()
        expired_keys = [
            key for key, timestamp in self.timestamps.items()
            if now - timestamp > self.ttl
        ]
        
        for key in expired_keys:
            if key in self.cache:
                del self.cache[key]
            if key in self.timestamps:
                del self.timestamps[key]
        
        return len(expired_keys)


class MemoizedCalculator:
    """
    Мемоизация для частых расчетов (комиссии, конвертации)
    """
    
    def __init__(self, cache_size: int = 500, ttl_seconds: int = 60):
        """
        Args:
            cache_size: Размер кэша
            ttl_seconds: Время жизни записей
        """
        self.cache = TTLCache(max_size=cache_size, ttl_seconds=ttl_seconds)
    
    def calculate_fee(self, amount: float, fee_rate: float) -> tuple:
        """
        Рассчитывает комиссию с мемоизацией
        
        Args:
            amount: Сумма
            fee_rate: Ставка комиссии
            
        Returns:
            (комиссия, сумма_после_комиссии)
        """
        # Создаем ключ с округлением для кэширования
        cache_key = f"fee_{amount:.8f}_{fee_rate:.8f}"
        cached = self.cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        fee_amount = amount * fee_rate
        amount_after_fee = amount - fee_amount
        result = (fee_amount, amount_after_fee)
        
        self.cache.put(cache_key, result)
        return result
    
    def convert_amount(self, amount: float, rate: float) -> float:
        """
        Конвертирует сумму по курсу с мемоизацией
        
        Args:
            amount: Сумма
            rate: Курс
            
        Returns:
            Конвертированная сумма
        """
        cache_key = f"convert_{amount:.8f}_{rate:.8f}"
        cached = self.cache.get(cache_key)
        
        if cached is not None:
            return cached
        
        result = amount * rate
        self.cache.put(cache_key, result)
        return result
    
    def cleanup(self) -> int:
        """Очищает истекшие записи"""
        return self.cache.cleanup_expired()
