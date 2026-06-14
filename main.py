import logging

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