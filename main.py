import logging
import argparse
from classes.trading_engine import TradingEngine
import config

logging.basicConfig(
    filename="logs/algoTrading.log",
    format='%(asctime)s | %(name)s | %(levelname)s -> %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S',
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


def main():
    parser = argparse.ArgumentParser(description="Run a trading strategy live.")
    parser.add_argument(
        "--strategy",
        type=str,
        default="strategies/strat_2.json",
        help="Path to the strategy configuration JSON file.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="Use Trading212 demo.")
    mode.add_argument("--live", action="store_true", help="Use Trading212 live.")
    args = parser.parse_args()

    is_demo = not args.live
    config.set_trading_mode(is_demo, require_credentials=True)

    LOGGER.info("Starting the trading engine...")
    trading_engine = TradingEngine(args.strategy)
    trading_engine.run()


if __name__ == "__main__":
    main()
