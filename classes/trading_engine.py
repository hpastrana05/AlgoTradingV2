import logging
from datetime import datetime, timedelta
import time

from .strategy_manager import StrategyManager
from .broker_sync_manager import BrokerSyncManager

LOGGER = logging.getLogger("TradingEngine")


class TradingEngine:

    def __init__(self, strategy_path):
        self.strategy_manager = StrategyManager.from_json(strategy_path)
        self.broker_sync_manager = BrokerSyncManager()
    
    def update_market_data(self):
        self.strategy_manager.update_market_data()
    
    def check_trading_strategy(self):
        ticker, action, price = self.strategy_manager.check_strategy()
        self.broker_sync_manager.process_actions(ticker, action, price)
    

    def run(self, stop_event=None):
        # Optional stop_event lets the Live Trading panel stop this loop.
        while True:
            if stop_event is not None and stop_event.is_set():
                break

            sleep_until_next_interval(minutes=1, offset_seconds=1)

            if stop_event is not None and stop_event.is_set():
                break

            LOGGER.debug(f"Running Strategy at {datetime.now()}")
            self.update_market_data()
            self.check_trading_strategy()
    


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
