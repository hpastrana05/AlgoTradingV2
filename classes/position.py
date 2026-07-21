

class Position:

    def __init__(self, ticker: str, action: str, ticker_api: str = None):
        # ticker      -> Yahoo / data feed symbol (e.g. QQQ, ^NDX)
        # ticker_api  -> Trading212 instrument id (e.g. AAPL_US_EQ), or None
        self.ticker = ticker
        self.ticker_api = ticker_api
        self.action = action

        # Active trade
        self.entry_price = None
        self.entry_candle_low = None
        self.entry_candle_high = None
        self.stop_loss_price = None
        self.take_profit_price = None

        # Set by entry signals before open() (e.g. long vs short retest)
        self.intended_action = None

        # Anchor-candle breakout + retest strategy state
        self.reset_session_state()

    def reset_session_state(self):
        """Levels and breakout state for the current session day."""
        self.session_date = None
        self.session_high = None
        self.session_low = None
        self.session_mid = None
        self.breakout_side = None  # "BUY" (break above) or "SELL" (break below)
        self.breakout_level = None
        self.breakout_bar_ts = None  # bar that confirmed breakout (retest must be later)
        self.session_traded = False  # one entry per anchor session day
        self.session_abandoned = False  # deadline passed with no entry

    def reset_trade_levels(self):
        self.stop_loss_price = None
        self.take_profit_price = None
        self.intended_action = None

    def open(self, entry_price, candle_low, candle_high, action=None):
        if action:
            self.action = action
        elif self.intended_action:
            self.action = self.intended_action

        self.entry_price = entry_price
        self.entry_candle_low = candle_low
        self.entry_candle_high = candle_high
        self.intended_action = None

    def close(self):
        self.entry_price = None
        self.entry_candle_low = None
        self.entry_candle_high = None
        self.reset_trade_levels()
        # After a trade, allow a new breakout/retest setup the same day
        self.breakout_side = None
        self.breakout_level = None
        self.breakout_bar_ts = None

    @property
    def is_open(self):
        return self.entry_price is not None
