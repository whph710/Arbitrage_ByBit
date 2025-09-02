from enum import Enum
from dataclasses import dataclass
from typing import List, NamedTuple

class TradeDirection(Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass
class OrderBookData:
    bid_price: float
    ask_price: float
    bid_qty: float
    ask_qty: float
    spread_percent: float = 0.0

    def __post_init__(self):
        if self.ask_price > 0 and self.bid_price > 0:
            self.spread_percent = ((self.ask_price - self.bid_price) / self.bid_price) * 100

class ArbitrageOpportunity(NamedTuple):
    path: List[str]
    directions: List[TradeDirection]
    prices: List[float]
    profit_percent: float
    min_volume_usdt: float
    execution_time: float
    spread_cost: float
