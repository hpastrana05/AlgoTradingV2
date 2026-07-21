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

# Longest period Yahoo typically accepts for each download interval.
# "max" is remapped through this table instead of being sent literally.
MAX_PERIOD_BY_INTERVAL = {
    "1m": "7d",
    "2m": "60d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "2y",
    "90m": "60d",
    "1h": "2y",
    "1d": "max",
    "5d": "max",
    "1wk": "max",
    "1mo": "max",
    "3mo": "max",
}

# Used to clamp oversized periods (e.g. 5y on 1h -> 2y).
_PERIOD_RANK = {
    "1d": 1,
    "5d": 2,
    "7d": 3,
    "1mo": 4,
    "60d": 5,
    "3mo": 6,
    "6mo": 7,
    "ytd": 8,
    "1y": 9,
    "2y": 10,
    "5y": 11,
    "10y": 12,
    "max": 99,
}


class DataManager:
    def __init__(self, ticker, interval, period=None):
        self.ticker = ticker
        self.interval = interval
        self.period = period
        self.data = self.fetch_data(ticker, interval, period)

    @staticmethod
    def resolve_period(interval, period, fetch_interval=None):
        """
        Map period='max' (and oversized periods) to what Yahoo allows
        for the actual download interval.
        """
        source_interval = fetch_interval or interval
        max_period = MAX_PERIOD_BY_INTERVAL.get(source_interval, "max")

        if period is None:
            return max_period

        period = str(period).lower()

        if period == "max":
            if max_period != "max":
                LOGGER.info(
                    f"Period 'max' for interval '{interval}' "
                    f"(fetch '{source_interval}') resolved to '{max_period}'"
                )
            return max_period

        # Clamp periods longer than the interval allows
        requested_rank = _PERIOD_RANK.get(period)
        max_rank = _PERIOD_RANK.get(max_period, 99)
        if requested_rank is not None and requested_rank > max_rank:
            LOGGER.warning(
                f"Period '{period}' exceeds Yahoo limit for interval "
                f"'{source_interval}'. Using '{max_period}' instead."
            )
            return max_period

        return period

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

        resolved_period = self.resolve_period(interval, period, fetch_interval)

        data = yf.download(
            ticker,
            interval=fetch_interval,
            period=resolved_period,
            progress=False,
        )
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        if data.empty:
            LOGGER.error(
                f"No data fetched for {ticker} with interval {interval} "
                f"and period {resolved_period} (requested {period})"
            )
            return data

        data = self._ensure_madrid_timezone(data)

        if resample_rule is not None:
            data = self._resample_ohlcv(data, resample_rule)
            if data.empty:
                LOGGER.error(
                    f"Resampling to {interval} produced empty data for {ticker} "
                    f"(source interval {fetch_interval}, period {resolved_period})"
                )
            else:
                data = self._ensure_madrid_timezone(data)

        return data

    @staticmethod
    def _ensure_madrid_timezone(data):
        """
        Normalize bar timestamps to Europe/Madrid so session strategies
        (15:30 open candle, deadlines, EOD flatten) operate in Madrid time.
        """
        if data is None or data.empty:
            return data
        df = data.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            # yfinance occasionally returns naive stamps; treat as UTC then convert.
            df.index = df.index.tz_localize("UTC").tz_convert("Europe/Madrid")
        else:
            df.index = df.index.tz_convert("Europe/Madrid")
        return df

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
        combined = pd.concat([self.data, new_data])
        if isinstance(combined.index, pd.DatetimeIndex):
            self.data = combined[~combined.index.duplicated(keep="last")]
        else:
            self.data = combined.drop_duplicates().reset_index(drop=True)
        while len(self.data) > data_len:
            self.data = self.data.iloc[1:]

    def get_current_price(self):
        return self.data["Close"].iloc[-1]


"""
Yahoo Finance interval / period limits (approximate):
1m                     -> max ~7 days   (resolved from 'max' -> 7d)
2m, 5m, 15m, 30m, 90m  -> max ~60 days  (resolved from 'max' -> 60d)
60m / 1h               -> max ~2 years  (resolved from 'max' -> 2y)
4h (resampled from 1h) -> same as 1h    (resolved from 'max' -> 2y)
1d, 5d, 1wk, 1mo, 3mo  -> max history   (keeps 'max')
Valid periods: 1d, 5d, 7d, 1mo, 60d, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
"""
