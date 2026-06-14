import pandas_ta as ta


def ema_cross_above(data, fast, slow):
    """Checks when the fast crosses slow from below to above"""
    cross = ta.cross(data[f"EMA_{fast}"], data[f"EMA_{slow}"], above=True, equal=False)
    return cross.iloc[-2] == 1

def ema_cross_below(data, fast, slow):
    """Checks when the fast crosses slow from above to below"""
    cross = ta.cross(data[f"EMA_{fast}"], data[f"EMA_{slow}"], above=False, equal=False)
    return cross.iloc[-2] == 1

def price_over_ema(data, ema_value):
    """Checks if the current price is above the EMA"""
    return data["Close"].iloc[-1] > data[f"EMA_{ema_value}"].iloc[-1]

def ema_over_ema(data, ema1, ema2):
    """Checks if EMA1 is above EMA2"""
    return data[f"EMA_{ema1}"].iloc[-1] > data[f"EMA_{ema2}"].iloc[-1]

def rsi_between(data, rsi_value, lower, upper):
    """Checks if the RSI is between the lower and upper thresholds"""
    rsi = data[f"RSI_{rsi_value}"]
    return lower <= rsi.iloc[-1] <= upper

def bullish_MACD_cross(data, values):
    """Checks for a bullish MACD cross (MACD line crossing above signal line)"""
    macd_line = data[f"MACD_{values[0]}_{values[1]}_{values[2]}"]
    is_bullish = (macd_line.iloc[-1][0] > macd_line.iloc[-1][2] and 
                  macd_line.iloc[-2][0] <= macd_line.iloc[-2][2])
    return is_bullish

def bearish_MACD_cross(data, values):
    """Checks for a bearish MACD cross (MACD line crossing below signal line)"""
    macd_line = data[f"MACD_{values[0]}_{values[1]}_{values[2]}"]
    is_bearish = (macd_line.iloc[-1][0] < macd_line.iloc[-1][2] and 
                  macd_line.iloc[-2][0] >= macd_line.iloc[-2][2])
    return is_bearish

