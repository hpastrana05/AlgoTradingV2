import yfinance as yf
import pandas as pd
import pandas_ta as ta
import logging

LOGGER = logging.getLogger("DataManager")


class DataManager:
    def __init__(self, ticker, indicators, interval, period=None):
        self.ticker = ticker
        self.indicators = indicators
        self.interval = interval
        self.period = period
        self.data = self.fetch_data(ticker, interval, period)
        self.update_indicators()


    def fetch_data(self, ticker, interval, period):
        data = yf.download(ticker, interval=interval, period=period, progress=False)
        # Only one entry not two
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        if data.empty:
            LOGGER.error(f"No data fetched for {ticker} with interval {interval} and period {period}")
        
        return data

    def update_data(self):
        """Will update the data and remove old data rows to maintain a fixed window size."""
        data_len = len(self.data)
        new_data = self.fetch_data(self.ticker, self.interval, self.period)
        self.data = pd.concat([self.data, new_data]).drop_duplicates().reset_index(drop=True)
        self.update_indicators()
        while len(self.data) > data_len:
            self.data = self.data[1:]

    def get_current_price(self):
        return self.data["Close"].iloc[-1]
    
    def update_indicators(self):
        """Add technical indicators to the data."""
        indicators = self.indicators
        for name, values in indicators.items():
            for value in values:
                
                if name == "EMA":               
                    self.data[f"EMA_{value}"] = ta.ema(self.data["Close"], length=value)

                elif name == "RSI":
                    self.data[f"RSI_{value}"] = ta.rsi(self.data["Close"], length=value)

                elif name == "SMA":
                    self.data[f"SMA_{value}"] = ta.sma(self.data["Close"], length=value)

                elif name == "WMA":
                    self.data[f"WMA_{value}"] = ta.wma(self.data["Close"], length=value)

                elif name == "BBands":
                    bbands = ta.bbands(self.data["Close"], length=value[0], std=value[1])
                    bbands = bbands.values.tolist()
                    self.data[f'BBands_{value}'] = bbands

                elif name == "EMA_CROSS":
                    self.data[f"EMA_CROSS_{value}"] = ta.cross(self.data[f"EMA_{value[0]}"], self.data[f"EMA_{value[1]}"],above=True, equal=False)

                elif name == "ATR":
                    self.data[f"ATR_{value}"] = ta.atr(self.data["High"], self.data["Low"], self.data["Close"], length=value)

                elif name == "MACD":
                    macd = ta.macd(self.data["Close"], value[0], value[1], value[2])
                    self.data[f"MACD_{value[0]}_{value[1]}_{value[2]}"] = macd.values.tolist()

                else:
                    LOGGER.warning(f"Indicator {name} is not supported.")



'''
indicators = {
    "EMA": [10, 20],
    "RSI": [14],
    "SMA": [50],
    "WMA": [30],
    "BBands": [(20, 2)] # BBand col has (LowBand, MidBand, UpperBand, BandWidth, Percentage)
}
dm = DataManager("AAPL", indicators, "1m", "1D")

print(dm.data.columns)
print(dm.data.tail())

'''
"""
This function will download and save the data taking into account this:
1m	                   ->   7 days
2m, 5m, 15m, 30m, 90m  ->   60 days
1h	                   ->   2 years
1d, 1wk, 1mo           ->   MAX
"""
