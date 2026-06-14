from .strategy_manager import StrategyManager

class TradingEngine:

    def __init__(self, strategy_path):
        self.strategy_manager = StrategyManager.from_json(strategy_path)
        self.broker_sync_manager = BrokerSyncManager()
    
    def update_market_data(self):
        self.strategy_manager.update_market_data()
    
    def check_trading_strategy(self):
        ticker, action, price = self.strategy_manager.check_strategy()
        self.broker_sync_manager.process_actions(ticker, action, price)