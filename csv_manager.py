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
        if not self.opportunities_path.exists():
            with open(self.opportunities_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "id", "timestamp", "path", "profit_percent",
                    "min_volume_usdt", "prices", "directions",
                    "execution_time", "spread_cost"
                ])
        if not self.executed_trades_path.exists():
            with open(self.executed_trades_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "id", "timestamp", "path", "profit_percent",
                    "min_volume_usdt", "prices", "directions",
                    "execution_time", "spread_cost"
                ])

    def save_opportunity(self, opportunity: ArbitrageOpportunity):
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

    def save_executed_trade(self, opportunity: ArbitrageOpportunity):
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

    def _get_next_id(self):
        try:
            with open(self.opportunities_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                return sum(1 for row in reader) + 1
        except FileNotFoundError:
            return 1

    def _get_next_trade_id(self):
        try:
            with open(self.executed_trades_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                return sum(1 for row in reader) + 1
        except FileNotFoundError:
            return 1
