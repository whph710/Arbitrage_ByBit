import aiohttp
import asyncio
import logging
import time
from typing import Dict, List, Tuple, Optional, Set
from models import OrderBookData, TradeDirection
from config import *

logger = logging.getLogger(__name__)

class BybitAPIClient:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.tickers_set: Set[str] = set()
        self.orderbook_cache: Dict[str, Tuple[OrderBookData, float]] = {}
        self._rate_limit = API_RATE_LIMIT
        self._rate_window: List[float] = []
        self._rate_lock = asyncio.Lock()
        self._http_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._shutdown_event = asyncio.Event()

    async def start(self):
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, ssl=SSL_VERIFY)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        logger.info("API клиент запущен")

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("API клиент остановлен")

    async def _acquire_rate_slot(self):
        async with self._rate_lock:
            now = time.time()
            self._rate_window = [t for t in self._rate_window if now - t < 60]
            while len(self._rate_window) >= self._rate_limit:
                await asyncio.sleep(0.1)
                now = time.time()
                self._rate_window = [t for t in self._rate_window if now - t < 60]
            self._rate_window.append(now)

    async def get_tickers(self) -> Set[str]:
        url = f"{BYBIT_BASE_URL}/market/tickers"
        params = {"category": "spot"}
        for attempt in range(API_RETRY_ATTEMPTS):
            try:
                await self._acquire_rate_slot()
                async with self._http_semaphore:
                    async with self.session.get(url, params=params) as response:
                        if response.status != 200:
                            logger.warning(f"API вернул статус {response.status}")
                            continue
                        data = await response.json()
                if not data.get("result") or not data["result"].get("list"):
                    logger.warning("Некорректный формат ответа API")
                    continue
                all_tickers = [pair["symbol"] for pair in data["result"]["list"]]
                filtered_tickers = self._filter_tickers(all_tickers)
                self.tickers_set = set(filtered_tickers)
                logger.info(f"Загружено {len(self.tickers_set)} торговых пар")
                return self.tickers_set
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Ошибка получения тикеров (попытка {attempt + 1}): {e}")
                if attempt < API_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(API_RETRY_DELAY)
                    return None
                else:
                    return set()
        return None

    def _filter_tickers(self, tickers: List[str]) -> List[str]:
        filtered = []
        for ticker in tickers:
            excluded = any(exc == ticker or ticker.endswith(exc) or ticker.startswith(exc) for exc in EXCLUDED_CURRENCIES)
            if excluded:
                continue
            base_currency_found = any(ticker.endswith(base) for base in CROSS_CURRENCIES)
            if base_currency_found:
                filtered.append(ticker)
        return filtered

    async def get_orderbook(self, symbol: str) -> Optional[OrderBookData]:
        if self._shutdown_event.is_set():
            return None

        if USE_ORDERBOOK_CACHE and symbol in self.orderbook_cache:
            data, timestamp = self.orderbook_cache[symbol]
            if time.time() - timestamp < ORDERBOOK_CACHE_TTL:
                return data
        url = f"{BYBIT_BASE_URL}/market/orderbook"
        params = {
            "category": "spot",
            "symbol": symbol,
            "limit": ORDERBOOK_LEVELS if ORDERBOOK_DEPTH_ANALYSIS else 1
        }
        try:
            await self._acquire_rate_slot()
            async with self._http_semaphore:
                async with self.session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.debug(f"Orderbook {symbol} returned status {response.status}")
                        return None
                    data = await response.json()
            result = data.get("result", {})
            bids = result.get("b", [])
            asks = result.get("a", [])
            if not bids or not asks:
                return None
            orderbook = OrderBookData(
                bid_price=float(bids[0][0]),
                ask_price=float(asks[0][0]),
                bid_qty=float(bids[0][1]),
                ask_qty=float(asks[0][1])
            )
            if FILTER_LOW_LIQUIDITY and orderbook.spread_percent > MAX_SPREAD_PERCENT:
                return None
            if USE_ORDERBOOK_CACHE:
                self.orderbook_cache[symbol] = (orderbook, time.time())
            return orderbook
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"Ошибка получения стакана для {symbol}: {e}")
            return None

    async def close_session(self):
        self._shutdown_event.set()
        if self.session:
            await self.session.close()
            self.session = None
