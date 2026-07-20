import pandas as pd
import pandas_ta as ta


def _ema(close, length):
    series = ta.ema(close, length=length)
    if series is None:
        return pd.Series(dtype=float, index=close.index)
    return series


def _sma(close, length):
    series = ta.sma(close, length=length)
    if series is None:
        return pd.Series(dtype=float, index=close.index)
    return series


def _ma(close, length):
    """Simple moving average (standard MA)."""
    series = ta.sma(close, length=length)
    if series is None:
        return pd.Series(dtype=float, index=close.index)
    return series


def _rsi(close, length):
    series = ta.rsi(close, length=length)
    if series is None:
        return pd.Series(dtype=float, index=close.index)
    return series


def _macd(close, fast, slow, signal):
    return ta.macd(close, fast, slow, signal)


def _cross_above(fast_series, slow_series):
    if fast_series is None or slow_series is None or len(fast_series) < 2:
        return False
    cross = ta.cross(fast_series, slow_series, above=True, equal=False)
    if cross is None or len(cross) < 2 or pd.isna(cross.iloc[-2]):
        return False
    return cross.iloc[-2] == 1


def _cross_below(fast_series, slow_series):
    if fast_series is None or slow_series is None or len(fast_series) < 2:
        return False
    cross = ta.cross(fast_series, slow_series, above=False, equal=False)
    if cross is None or len(cross) < 2 or pd.isna(cross.iloc[-2]):
        return False
    return cross.iloc[-2] == 1


def ema_cross_above(data, fast, slow, *_, **__):
    """Checks when the fast EMA crosses the slow EMA from below to above"""
    close = data["Close"]
    return _cross_above(_ema(close, fast), _ema(close, slow))


def ema_cross_below(data, fast, slow, *_, **__):
    """Checks when the fast EMA crosses the slow EMA from above to below"""
    close = data["Close"]
    return _cross_below(_ema(close, fast), _ema(close, slow))


def sma_cross_above(data, fast, slow, *_, **__):
    """Checks when the fast SMA crosses the slow SMA from below to above"""
    close = data["Close"]
    return _cross_above(_sma(close, fast), _sma(close, slow))


def sma_cross_below(data, fast, slow, *_, **__):
    """Checks when the fast SMA crosses the slow SMA from above to below"""
    close = data["Close"]
    return _cross_below(_sma(close, fast), _sma(close, slow))


def ema_sma_cross_above(data, ema_value, sma_value, *_, **__):
    """Checks when EMA crosses SMA from below to above"""
    close = data["Close"]
    return _cross_above(_ema(close, ema_value), _sma(close, sma_value))


def ema_sma_cross_below(data, ema_value, sma_value, *_, **__):
    """Checks when EMA crosses SMA from above to below"""
    close = data["Close"]
    return _cross_below(_ema(close, ema_value), _sma(close, sma_value))


def ema_ma_cross_above(data, ema_value, ma_value, *_, **__):
    """Checks when EMA crosses the moving average from below to above"""
    close = data["Close"]
    return _cross_above(_ema(close, ema_value), _ma(close, ma_value))


def ema_ma_cross_below(data, ema_value, ma_value, *_, **__):
    """Checks when EMA crosses the moving average from above to below"""
    close = data["Close"]
    return _cross_below(_ema(close, ema_value), _ma(close, ma_value))


def _last_value(series):
    if series is None or len(series) == 0:
        return None
    value = series.iloc[-1]
    if pd.isna(value):
        return None
    return value


def price_over_ema(data, ema_value, *_, **__):
    """Checks if the current price is above the EMA"""
    ema = _last_value(_ema(data["Close"], ema_value))
    if ema is None:
        return False
    return data["Close"].iloc[-1] > ema


def price_over_sma(data, sma_value, *_, **__):
    """Checks if the current close is above the SMA"""
    sma = _last_value(_sma(data["Close"], sma_value))
    if sma is None:
        return False
    return data["Close"].iloc[-1] > sma


def candle_above_sma(data, sma_value, *_, **__):
    """Checks if the entire candle (low included) closed above the SMA"""
    sma = _last_value(_sma(data["Close"], sma_value))
    if sma is None:
        return False
    return data["Low"].iloc[-1] > sma


def candle_below_sma(data, sma_value, *_, **__):
    """Checks if the entire candle (high included) closed below the SMA"""
    sma = _last_value(_sma(data["Close"], sma_value))
    if sma is None:
        return False
    return data["High"].iloc[-1] < sma


def ema_over_ema(data, ema1, ema2, *_, **__):
    """Checks if EMA1 is above EMA2"""
    close = data["Close"]
    e1 = _last_value(_ema(close, ema1))
    e2 = _last_value(_ema(close, ema2))
    if e1 is None or e2 is None:
        return False
    return e1 > e2


def ema_over_sma(data, ema_value, sma_value, *_, **__):
    """Checks if EMA is above SMA"""
    close = data["Close"]
    ema = _last_value(_ema(close, ema_value))
    sma = _last_value(_sma(close, sma_value))
    if ema is None or sma is None:
        return False
    return ema > sma


def rsi_between(data, rsi_value, lower, upper, *_, **__):
    """Checks if the RSI is between the lower and upper thresholds"""
    rsi = _last_value(_rsi(data["Close"], rsi_value))
    if rsi is None:
        return False
    return lower <= rsi <= upper


def bullish_MACD_cross(data, values, *_, **__):
    """Checks for a bullish MACD cross (MACD line crossing above signal line)"""
    macd_df = _macd(data["Close"], values[0], values[1], values[2])
    if macd_df is None or len(macd_df) < 2:
        return False

    macd_line = macd_df.iloc[:, 0]
    signal_line = macd_df.iloc[:, 2]
    if pd.isna(macd_line.iloc[-1]) or pd.isna(signal_line.iloc[-1]):
        return False

    return (
        macd_line.iloc[-1] > signal_line.iloc[-1]
        and macd_line.iloc[-2] <= signal_line.iloc[-2]
    )


def bearish_MACD_cross(data, values, *_, **__):
    """Checks for a bearish MACD cross (MACD line crossing below signal line)"""
    macd_df = _macd(data["Close"], values[0], values[1], values[2])
    if macd_df is None or len(macd_df) < 2:
        return False

    macd_line = macd_df.iloc[:, 0]
    signal_line = macd_df.iloc[:, 2]
    if pd.isna(macd_line.iloc[-1]) or pd.isna(signal_line.iloc[-1]):
        return False

    return (
        macd_line.iloc[-1] < signal_line.iloc[-1]
        and macd_line.iloc[-2] >= signal_line.iloc[-2]
    )


def tp_percentage(data, percentage, position, *_, **__):
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


def sl_lowest_value_last_candle(data, position, *_, **__):
    """Stop loss at the low (long) or high (short) of the entry candle."""
    if position is None or not position.is_open:
        return False

    if position.action == "BUY":
        if position.entry_candle_low is None:
            return False
        return data["Low"].iloc[-1] <= position.entry_candle_low

    if position.action == "SELL":
        if position.entry_candle_high is None:
            return False
        return data["High"].iloc[-1] >= position.entry_candle_high

    return False


def _risk_reward_prices(position, loss_units, win_units):
    """Return (sl_price, tp_price) from entry and entry-candle extremes."""
    entry = position.entry_price
    ratio = win_units / loss_units

    if position.action == "BUY":
        sl = position.entry_candle_low
        if sl is None:
            return None, None
        risk = entry - sl
        if risk <= 0:
            return None, None
        return sl, entry + ratio * risk

    if position.action == "SELL":
        sl = position.entry_candle_high
        if sl is None:
            return None, None
        risk = sl - entry
        if risk <= 0:
            return None, None
        return sl, entry - ratio * risk

    return None, None


def tp_by_ratio(data, loss_units=1, win_units=3, position=None, *_, **__):
    """
    Take profit sized from the entry-candle stop distance.
    Example: loss_units=1, win_units=3 -> risk 1R, target 3R (1:3).
    SL reference is the entry candle low (long) or high (short).
    """
    if position is None or not position.is_open:
        return False

    _, tp_price = _risk_reward_prices(position, loss_units, win_units)
    if tp_price is None:
        return False

    if position.action == "BUY":
        return data["High"].iloc[-1] >= tp_price

    if position.action == "SELL":
        return data["Low"].iloc[-1] <= tp_price

    return False
