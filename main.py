import asyncio
import logging
from func import BybitAPI, calculate_profit

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    api = BybitAPI()
    count = 1
    money = 10
    try:
        await api.start()
        while True:
            try:
                trading_pairs = await api.get_trading_pairs()
                for base, pairs in trading_pairs.items():
                    for pair in pairs:
                        result = await api.process_pair(pair, base)
                        if result:
                            if calculate_profit(*result) > 0.3:
                                logger.info(f"Transaction No.: {count}")
                                logger.info(f"Pair: {pair}")
                                calc = calculate_profit(*result)
                                logger.info(f"Profit: {calc}%")
                                money += money * (0.01 * calc)
                                logger.info(f"Money: {money}")
                                count += 1

                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
