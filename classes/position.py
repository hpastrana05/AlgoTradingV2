

class Position:

    def __init__(self, ticker: str, action: str):
        self.ticker = ticker
        self.action = action
        self.entry_price = None
        self.entry_candle_low = None
        self.entry_candle_high = None

    def open(self, entry_price, candle_low, candle_high):
        self.entry_price = entry_price
        self.entry_candle_low = candle_low
        self.entry_candle_high = candle_high

    def close(self):
        self.entry_price = None
        self.entry_candle_low = None
        self.entry_candle_high = None

    @property
    def is_open(self):
        return self.entry_price is not None
