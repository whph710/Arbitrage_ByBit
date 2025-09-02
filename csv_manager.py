import csv
import json
import time
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, List, Tuple, Optional, NamedTuple, Set
from models import ArbitrageOpportunity

logger = logging.getLogger(__name__)


class CSVManager:
    def __init__(self):
        self.opportunities_path = Path("opportunities.csv")
        self.executed_trades_path = Path("executed_trades.csv")
        self._init_csv_files()

    def _init_csv_files(self):
        """ИСПРАВЛЕНО: Добавлена обработка ошибок при создании CSV файлов"""
        try:
            if not self.opportunities_path.exists():
                with open(self.opportunities_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "id", "timestamp", "path", "profit_percent",
                        "min_volume_usdt", "prices", "directions",
                        "execution_time", "spread_cost"
                    ])
                logger.debug(f"Создан файл: {self.opportunities_path}")
        except Exception as e:
            logger.error(f"Ошибка создания файла opportunities.csv: {e}")

        try:
            if not self.executed_trades_path.exists():
                with open(self.executed_trades_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "id", "timestamp", "path", "profit_percent",
                        "min_volume_usdt", "prices", "directions",
                        "execution_time", "spread_cost"
                    ])
                logger.debug(f"Создан файл: {self.executed_trades_path}")
        except Exception as e:
            logger.error(f"Ошибка создания файла executed_trades.csv: {e}")

    def save_opportunity(self, opportunity: ArbitrageOpportunity):
        """ИСПРАВЛЕНО: Добавлена обработка ошибок при сохранении"""
        try:
            with open(self.opportunities_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    self._get_next_id(),
                    datetime.now().isoformat(),
                    json.dumps(opportunity.path),
                    opportunity.profit_percent,
                    opportunity.min_volume_usdt,
                    json.dumps(opportunity.prices),
                    json.dumps([d.value for d in opportunity.directions]),
                    opportunity.execution_time,
                    opportunity.spread_cost
                ])
        except Exception as e:
            logger.error(f"Ошибка сохранения возможности в CSV: {e}")
            # Не прерываем выполнение, просто логируем ошибку

    def save_executed_trade(self, opportunity: ArbitrageOpportunity):
        """ИСПРАВЛЕНО: Добавлена обработка ошибок при сохранении"""
        try:
            with open(self.executed_trades_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    self._get_next_trade_id(),
                    datetime.now().isoformat(),
                    json.dumps(opportunity.path),
                    opportunity.profit_percent,
                    opportunity.min_volume_usdt,
                    json.dumps(opportunity.prices),
                    json.dumps([d.value for d in opportunity.directions]),
                    opportunity.execution_time,
                    opportunity.spread_cost
                ])
            logger.debug(f"Сделка сохранена в {self.executed_trades_path}")
        except Exception as e:
            logger.error(f"Ошибка сохранения сделки в CSV: {e}")

    def _get_next_id(self):
        """ИСПРАВЛЕНО: Улучшена обработка ошибок при получении ID"""
        try:
            if not self.opportunities_path.exists():
                return 1

            with open(self.opportunities_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    next(reader)  # Skip header
                except StopIteration:
                    return 1  # Файл пустой, возвращаем первый ID

                count = sum(1 for row in reader)
                return count + 1
        except Exception as e:
            logger.debug(f"Ошибка получения следующего ID: {e}")
            return 1  # Возвращаем 1 в случае любых ошибок

    def _get_next_trade_id(self):
        """ИСПРАВЛЕНО: Улучшена обработка ошибок при получении ID сделки"""
        try:
            if not self.executed_trades_path.exists():
                return 1

            with open(self.executed_trades_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    next(reader)  # Skip header
                except StopIteration:
                    return 1  # Файл пустой, возвращаем первый ID

                count = sum(1 for row in reader)
                return count + 1
        except Exception as e:
            logger.debug(f"Ошибка получения следующего ID сделки: {e}")
            return 1  # Возвращаем 1 в случае любых ошибок

    def get_opportunities_count(self) -> int:
        """ДОБАВЛЕНО: Возвращает количество сохраненных возможностей"""
        try:
            if not self.opportunities_path.exists():
                return 0
            with open(self.opportunities_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                return sum(1 for row in reader)
        except Exception as e:
            logger.debug(f"Ошибка подсчета возможностей: {e}")
            return 0

    def get_trades_count(self) -> int:
        """ДОБАВЛЕНО: Возвращает количество выполненных сделок"""
        try:
            if not self.executed_trades_path.exists():
                return 0
            with open(self.executed_trades_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                return sum(1 for row in reader)
        except Exception as e:
            logger.debug(f"Ошибка подсчета сделок: {e}")
            return 0