import logging
from datetime import datetime, timedelta
import time

from classes.trading_engine import TradingEngine

logging.basicConfig(
    filename="logs/algoTrading.log",
    format='%(asctime)s | %(name)s | %(levelname)s -> %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S',
    level=logging.INFO
)

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

logging.getLogger("StrategyManager").setLevel(logging.DEBUG)
logging.getLogger("DataManager").setLevel(logging.DEBUG)
logging.getLogger("Signals").setLevel(logging.DEBUG)

LOGGER = logging.getLogger("Main")

def sleep_until_next_interval(hours=0, minutes=0, seconds=0, offset_seconds=0):
    interval = timedelta(hours=hours, minutes=minutes, seconds=seconds)

    if interval.total_seconds() <= 0:
        LOGGER.error("Interval must be greater than 0 seconds.")
        raise ValueError("Interval must be greater than 0 seconds.")

    now = datetime.now()
    interval_seconds = int(interval.total_seconds())

    current_ts = now.timestamp()
    next_ts = ((int(current_ts) // interval_seconds) + 1) * interval_seconds + offset_seconds

    next_run = datetime.fromtimestamp(next_ts)

    if next_run <= now:
        next_run += interval

    sleep_seconds = (next_run - now).total_seconds()
    time.sleep(max(sleep_seconds, 0))


def main():
    LOGGER.info("Starting the trading engine...")

    strat_path = "strategies/strat_2.json"

    trading_engine = TradingEngine(strat_path)
    
    while True:
        
        sleep_until_next_interval(minutes=1, offset_seconds=1)

        LOGGER.debug(f"Running Strategy at {datetime.now()}")
        trading_engine.update_market_data()
        trading_engine.check_trading_strategy()


if __name__ == "__main__":
    main()
    