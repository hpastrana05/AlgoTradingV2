
from datetime import datetime
import logging

from trading_api import *

LOGGER = logging.getLogger("BrokerSyncManager")

class BrokerSyncManager:
    def __init__(self):
        self.account = None
        self.position = None
        self.pending_orders = None

        self.is_synchronized = False
        self.last_sync_time = None

    def _sync_account_info(self):
        response = get_account_summary()

        if response:
            self.account = response
            return 0
        elif response == "ERROR":
            LOGGER.error("Failed to fetch account summary.")
            return 1

    def _sync_position(self, ticker):
        response = get_all_open_positions(ticker)

        if response:
            self.position = response[0]
            return 0
        elif response == "ERROR":
            self.position = None
            LOGGER.error("Failed to fetch open positions.")
            return 1
        else:
            self.position = None
            return 0
    
    def _sync_pending_orders(self):
        response = get_pending_orders()

        if response:
            self.pending_orders = response
            return 0
        elif response == "ERROR":
            self.pending_orders = None
            LOGGER.error("Failed to fetch pending orders.")
            return 1
        else:
            self.pending_orders = response
            return 0

    def sync(self, ticker):
        errors = 0
        errors += self._sync_account_info()
        errors += self._sync_position(ticker)
        errors += self._sync_pending_orders()

        if errors == 0:
            LOGGER.info("Synchronization completed successfully.")
            self.is_synchronized = True
        else:
            LOGGER.error(f"Synchronization completed with {errors} errors.")
            self.is_synchronized = False
        
        self.last_sync_time = datetime.now()

    def check_ticker_availability(self, ticker):
        response = get_available_instruments()

        if response:
            for instrument in response:
                if instrument["ticker"] == ticker:
                    return True  
            return False
        
        elif response == "ERROR":
            LOGGER.error("Failed to fetch available instruments.")
            return False

        

    def process_actions(self, ticker, action, price):
        self.sync(ticker)

        if not self.check_ticker_availability(ticker):
            LOGGER.info(f"Ticker {ticker} is not available for trading now.")
            return


        if not self.is_synchronized:
            LOGGER.error("Cannot process actions due to synchronization errors.")
            return
        
        if action == "BUY":
            self.execute_buy(ticker, price)
        elif action == "SELL":
            self.execute_sell(ticker)
    
    def execute_buy(self, ticker, price):
        open_position = self.check_open_position(ticker)
        pending_order = self.check_pending_order("BUY")

        cash_available = self.account["cash"]["availableToTrade"]

        if not open_position and not pending_order and cash_available > 1:
            quantity_to_buy = cash_available / price * 0.99
            post_place_market_order(quantity=quantity_to_buy, ticker=ticker)
        

    def execute_sell(self, ticker):
        open_position = self.check_open_position(ticker)
        pending_order = self.check_pending_order("SELL")

        if open_position and not pending_order:
            quantity_to_sell = self.position["quantityAvailableForTrading"]
            post_place_market_order(quantity=-quantity_to_sell, ticker=ticker)

    def check_open_position(self, ticker):
        if self.position is None:
            return False
        else:
            if self.position["instrument"]["ticker"] == ticker:
                return True
    
    def check_pending_order(self, action):
        if self.pending_orders is None:
            return False
        
        for order in self.pending_orders:
            if order["initiatedFrom"] == "API" and order["side"] == action:
                return True
        
        return False


        
        

