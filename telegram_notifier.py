"""
Модуль для отправки уведомлений в Telegram
"""

import aiohttp
import asyncio
from typing import Dict, Optional
from configs_continuous import (
    os, BASE_DIR, Path
)

# Загружаем переменные окружения
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class TelegramNotifier:
    """Класс для отправки уведомлений в Telegram"""
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.bot_token and self.chat_id)
        self.session: Optional[aiohttp.ClientSession] = None
        
        if not self.enabled:
            print("[Telegram] ⚠️  Уведомления отключены (не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID)")
        else:
            print("[Telegram] ✅ Уведомления включены")
    
    async def create_session(self):
        """Создает HTTP сессию"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Закрывает HTTP сессию"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Отправляет сообщение в Telegram
        
        Args:
            text: Текст сообщения
            parse_mode: Режим парсинга (HTML или Markdown)
        
        Returns:
            True если успешно, False иначе
        """
        if not self.enabled:
            return False
        
        if not self.session:
            await self.create_session()
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        try:
            async with self.session.post(url, json={
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': False
            }) as response:
                if response.status == 200:
                    return True
                else:
                    error_text = await response.text()
                    print(f"[Telegram] ❌ Ошибка отправки: {response.status} - {error_text}")
                    return False
        except Exception as e:
            print(f"[Telegram] ❌ Ошибка при отправке сообщения: {e}")
            return False
    
    async def send_opportunity(self, opportunity: Dict, rank: int = None):
        """
        Отправляет уведомление о найденной арбитражной возможности
        
        Args:
            opportunity: Словарь с данными возможности
            rank: Номер возможности (опционально)
        """
        if not self.enabled:
            return
        
        # Формируем сообщение
        message_parts = []
        
        if rank:
            message_parts.append(f"🎯 <b>Арбитражная возможность #{rank}</b>\n")
        else:
            message_parts.append(f"🎯 <b>Новая арбитражная возможность</b>\n")
        
        message_parts.append(f"📍 <b>Путь:</b> {opportunity.get('path', 'N/A')}\n")
        message_parts.append(f"📊 <b>Спред:</b> {opportunity.get('spread', 0):.4f}%\n")
        message_parts.append(f"💰 <b>Прибыль:</b> ${opportunity.get('profit', 0):.4f}\n")
        message_parts.append(f"💵 <b>Сумма:</b> ${opportunity.get('initial', 0):.2f} → ${opportunity.get('final', 0):.2f}\n")
        
        if 'exchanger' in opportunity:
            message_parts.append(f"🏦 <b>Обменник:</b> {opportunity['exchanger']}\n")
        
        if 'reserve' in opportunity:
            message_parts.append(f"💎 <b>Резерв:</b> ${opportunity['reserve']:,.0f}\n")
        
        if 'bybit_total_fee' in opportunity:
            message_parts.append(f"💳 <b>Комиссии Bybit:</b> ${opportunity['bybit_total_fee']:.4f}\n")
        
        # Добавляем ссылки
        links = []
        if 'bybit_url_a' in opportunity:
            coin_a = opportunity.get('coins', [''])[0] if opportunity.get('coins') else ''
            links.append(f"🔗 <a href='{opportunity['bybit_url_a']}'>Bybit {coin_a}/USDT</a>")
        
        if 'exchanger_url' in opportunity:
            links.append(f"🔗 <a href='{opportunity['exchanger_url']}'>Обменник</a>")
        
        if links:
            message_parts.append("\n" + " | ".join(links))
        
        message = "".join(message_parts)
        
        await self.send_message(message)
    
    async def send_statistics(self, stats: Dict):
        """
        Отправляет статистику работы бота
        
        Args:
            stats: Словарь со статистикой
        """
        if not self.enabled:
            return
        
        message_parts = []
        message_parts.append("📊 <b>Статистика работы бота</b>\n")
        message_parts.append(f"⏱️  <b>Время работы:</b> {stats.get('uptime_hours', 0):.1f} часов\n")
        message_parts.append(f"🎯 <b>Найдено связок:</b> {stats.get('total_opportunities', 0)}\n")
        
        if stats.get('best_spread', 0) > 0:
            message_parts.append(f"🏆 <b>Лучший спред:</b> {stats['best_spread']:.4f}%\n")
        
        message = "".join(message_parts)
        await self.send_message(message)
    
    async def send_error(self, error_message: str):
        """
        Отправляет уведомление об ошибке
        
        Args:
            error_message: Текст ошибки
        """
        if not self.enabled:
            return
        
        message = f"❌ <b>Ошибка в работе бота</b>\n\n{error_message}"
        await self.send_message(message)


# Глобальный экземпляр для удобства использования
_notifier_instance: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """Возвращает глобальный экземпляр уведомителя"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier()
    return _notifier_instance

