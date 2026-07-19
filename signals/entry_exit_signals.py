import pandas_ta as ta


def ema_cross_above(data, fast, slow, *_, **__):
    """Checks when the fast crosses slow from below to above"""
    cross = ta.cross(data[f"EMA_{fast}"], data[f"EMA_{slow}"], above=True, equal=False)
    return cross.iloc[-2] == 1

def ema_cross_below(data, fast, slow, *_, **__):
    """Checks when the fast crosses slow from above to below"""
    cross = ta.cross(data[f"EMA_{fast}"], data[f"EMA_{slow}"], above=False, equal=False)
    return cross.iloc[-2] == 1

def sma_cross_above(data, fast, slow, *_, **__):
    """Checks when the fast SMA crosses the slow SMA from below to above"""
    cross = ta.cross(data[f"SMA_{fast}"], data[f"SMA_{slow}"], above=True, equal=False)
    return cross.iloc[-2] == 1

def sma_cross_below(data, fast, slow, *_, **__):
    """Checks when the fast SMA crosses the slow SMA from above to below"""
    cross = ta.cross(data[f"SMA_{fast}"], data[f"SMA_{slow}"], above=False, equal=False)
    return cross.iloc[-2] == 1

def ema_sma_cross_above(data, ema_value, sma_value, *_, **__):
    """Checks when EMA crosses SMA from below to above"""
    cross = ta.cross(data[f"EMA_{ema_value}"], data[f"SMA_{sma_value}"], above=True, equal=False)
    return cross.iloc[-2] == 1

def ema_sma_cross_below(data, ema_value, sma_value, *_, **__):
    """Checks when EMA crosses SMA from above to below"""
    cross = ta.cross(data[f"EMA_{ema_value}"], data[f"SMA_{sma_value}"], above=False, equal=False)
    return cross.iloc[-2] == 1

def price_over_ema(data, ema_value, *_, **__):
    """Checks if the current price is above the EMA"""
    return data["Close"].iloc[-1] > data[f"EMA_{ema_value}"].iloc[-1]

def price_over_sma(data, sma_value, *_, **__):
    """Checks if the current close is above the SMA"""
    return data["Close"].iloc[-1] > data[f"SMA_{sma_value}"].iloc[-1]

def candle_above_sma(data, sma_value, *_, **__):
    """Checks if the entire candle (low included) closed above the SMA"""
    sma = data[f"SMA_{sma_value}"].iloc[-1]
    return data["Low"].iloc[-1] > sma

def candle_below_sma(data, sma_value, *_, **__):
    """Checks if the entire candle (high included) closed below the SMA"""
    sma = data[f"SMA_{sma_value}"].iloc[-1]
    return data["High"].iloc[-1] < sma

def ema_over_ema(data, ema1, ema2, *_, **__):
    """Checks if EMA1 is above EMA2"""
    return data[f"EMA_{ema1}"].iloc[-1] > data[f"EMA_{ema2}"].iloc[-1]

def ema_over_sma(data, ema_value, sma_value, *_, **__):
    """Checks if EMA is above SMA"""
    return data[f"EMA_{ema_value}"].iloc[-1] > data[f"SMA_{sma_value}"].iloc[-1]

def rsi_between(data, rsi_value, lower, upper, *_, **__):
    """Checks if the RSI is between the lower and upper thresholds"""
    rsi = data[f"RSI_{rsi_value}"]
    return lower <= rsi.iloc[-1] <= upper

def bullish_MACD_cross(data, values, *_, **__):
    """Checks for a bullish MACD cross (MACD line crossing above signal line)"""
    macd_line = data[f"MACD_{values[0]}_{values[1]}_{values[2]}"]
    is_bullish = (macd_line.iloc[-1][0] > macd_line.iloc[-1][2] and 
                  macd_line.iloc[-2][0] <= macd_line.iloc[-2][2])
    return is_bullish

def bearish_MACD_cross(data, values, *_, **__):
    """Checks for a bearish MACD cross (MACD line crossing below signal line)"""
    macd_line = data[f"MACD_{values[0]}_{values[1]}_{values[2]}"]
    is_bearish = (macd_line.iloc[-1][0] < macd_line.iloc[-1][2] and 
                  macd_line.iloc[-2][0] >= macd_line.iloc[-2][2])
    return is_bearish

def tp_percentage(data, percentage, position,  *_, **__):
    if position is None or position.entry_price is None:
        return False
    entry = position.entry_price

    percentage = percentage / 100

    if position.action == "BUY":
        stop_price = entry * (1 + percentage)
        return data["Close"].iloc[-1] >= stop_price
    
    elif position.action == "SELL":
        stop_price = entry * (1 - percentage)
        return data["Close"].iloc[-1] <= stop_price
    
    else:
        return False

def sl_percentage(data, percentage, position, *_, **__):
    if position is None or position.entry_price is None:
        return False
    entry = position.entry_price

    percentage = percentage / 100

    if position.action == "BUY":
        stop_price = entry * (1 - percentage)
        return data["Close"].iloc[-1] <= stop_price
    
    elif position.action == "SELL":
        stop_price = entry * (1 + percentage)
        return data["Close"].iloc[-1] >= stop_price
    
    else:
        return False