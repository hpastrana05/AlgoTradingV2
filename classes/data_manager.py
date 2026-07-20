import yfinance as yf
import pandas as pd
import logging

LOGGER = logging.getLogger("DataManager")

# Intervals Yahoo supports natively. "4h" is built by resampling 1h bars.
YF_INTERVALS = {
    "1m", "2m", "5m", "15m", "30m", "60m", "90m",
    "1h", "1d", "5d", "1wk", "1mo", "3mo",
}
RESAMPLE_FROM = {
    "4h": ("1h", "4h"),
}


class DataManager:
    def __init__(self, ticker, interval, period=None):
        self.ticker = ticker
        self.interval = interval
        self.period = period
        self.data = self.fetch_data(ticker, interval, period)

    def fetch_data(self, ticker, interval, period):
        fetch_interval = interval
        resample_rule = None

        if interval in RESAMPLE_FROM:
            fetch_interval, resample_rule = RESAMPLE_FROM[interval]
        elif interval not in YF_INTERVALS:
            LOGGER.warning(
                f"Interval '{interval}' is not a known yfinance interval; "
                "download may fail."
            )

        data = yf.download(ticker, interval=fetch_interval, period=period, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        if data.empty:
            LOGGER.error(f"No data fetched for {ticker} with interval {interval} and period {period}")
            return data

        if resample_rule is not None:
            data = self._resample_ohlcv(data, resample_rule)
            if data.empty:
                LOGGER.error(
                    f"Resampling to {interval} produced empty data for {ticker} "
                    f"(source interval {fetch_interval}, period {period})"
                )

        return data

    @staticmethod
    def _resample_ohlcv(data, rule):
        """Aggregate OHLCV bars to a coarser interval (e.g. 1h -> 4h)."""
        df = data.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        agg = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
        }
        if "Volume" in df.columns:
            agg["Volume"] = "sum"

        return df.resample(rule).agg(agg).dropna(how="any")

    def update_data(self):
        """Refresh market data while keeping a fixed window size."""
        data_len = len(self.data)
        new_data = self.fetch_data(self.ticker, self.interval, self.period)
        self.data = pd.concat([self.data, new_data]).drop_duplicates().reset_index(drop=True)
        while len(self.data) > data_len:
            self.data = self.data[1:]

    def get_current_price(self):
        return self.data["Close"].iloc[-1]


"""
Yahoo Finance interval / period limits (approximate):
1m                     -> max ~7 days
2m, 5m, 15m, 30m, 90m  -> max ~60 days
60m / 1h               -> max ~2 years
4h (resampled from 1h) -> same as 1h (~2 years)
1d, 5d, 1wk, 1mo, 3mo  -> max
Valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
"""
