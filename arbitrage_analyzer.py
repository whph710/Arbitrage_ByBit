import asyncio
from typing import List, Dict, Optional
from datetime import datetime


class ArbitrageAnalyzerAsync:
    """Асинхронный анализатор кругового арбитража"""

    def __init__(self, bybit_client, bestchange_client):
        self.bybit = bybit_client
        self.bestchange = bestchange_client

    async def find_circular_opportunities(
        self,
        initial_amount: float = 100.0,
        min_spread: float = 0.5,
        top_count: int = 10
    ) -> List[Dict]:

        bybit_prices = await self.bybit.get_usdt_tickers()
        common_coins = set(bybit_prices.keys()) & set(self.bestchange.crypto_currencies.keys())
        rates = await self.bestchange.get_rates_for_pairs(common_coins)

        opportunities = []

        for coin_a in common_coins:
            for coin_b, exch_list in rates.get(coin_a, {}).items():
                for coin_c in common_coins:
                    if coin_c == coin_a:
                        continue

                    # USDT -> coin_a -> coin_b -> coin_c -> USDT
                    try:
                        amount_a = initial_amount / bybit_prices[coin_a]
                        amount_b = amount_a * exch_list[0]['rate']
                        amount_c = amount_b / bybit_prices[coin_b]
                        final_usdt = amount_c * bybit_prices[coin_c]
                        spread = ((final_usdt - initial_amount) / initial_amount) * 100

                        if spread >= min_spread:
                            opportunities.append({
                                'path': [coin_a, coin_b, coin_c],
                                'initial': initial_amount,
                                'final': final_usdt,
                                'spread': spread
                            })
                    except KeyError:
                        continue

        opportunities.sort(key=lambda x: x['spread'], reverse=True)
        return opportunities[:top_count]
