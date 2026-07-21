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


# ---------------------------------------------------------------------------
# Anchor-candle breakout + retest (any instrument / session time)
# ---------------------------------------------------------------------------

# session_hour / session_minute in strategy JSON are interpreted in this zone.
SESSION_INPUT_TZ = "Europe/Madrid"


def _anchor_bar_mask(index, session_hour, session_minute):
    if not isinstance(index, pd.DatetimeIndex):
        return None

    if index.tz is None:
        local_index = index.tz_localize("UTC").tz_convert(SESSION_INPUT_TZ)
    else:
        local_index = index.tz_convert(SESSION_INPUT_TZ)
    return (local_index.hour == session_hour) & (local_index.minute == session_minute)


def _session_date_for_bar(index):
    current_ts = index[-1]
    if isinstance(index, pd.DatetimeIndex) and index.tz is not None:
        return current_ts.tz_convert(SESSION_INPUT_TZ).date()
    return current_ts.date()


def _sync_session_day(position, data):
    """Reset anchor state when the session calendar day changes."""
    current_date = _session_date_for_bar(data.index)
    if position.session_date != current_date:
        position.reset_session_state()
        position.session_date = current_date
        position.session_traded = False
    return current_date


def _local_bar_minutes(index):
    ts = index[-1]
    if isinstance(index, pd.DatetimeIndex) and index.tz is not None:
        ts = ts.tz_convert(SESSION_INPUT_TZ)
    return ts.hour * 60 + ts.minute


def _check_entry_deadline(
    data,
    position,
    entry_deadline_hour=16,
    entry_deadline_minute=15,
):
    """
    Abandon the setup for the day once the deadline bar has passed without entry.

    With 15m bars and deadline 16:15, entries are still allowed on the 16:00 and
    16:15 candles; from the 16:30 bar onward no new entries are taken.
    """
    if position.session_traded or position.session_abandoned:
        return position.session_abandoned

    if position.session_high is None:
        return False

    deadline = entry_deadline_hour * 60 + entry_deadline_minute
    if _local_bar_minutes(data.index) > deadline:
        position.session_abandoned = True

    return position.session_abandoned


def _update_anchor_levels(
    data, position, session_hour=15, session_minute=30
):
    """
    After the anchor candle (session_hour:session_minute) closes, store its
    high / low / mid on the position. Times are Europe/Madrid (SESSION_INPUT_TZ).
    """
    if len(data) < 2:
        return False

    index = data.index
    current_date = _sync_session_day(position, data)

    mask = _anchor_bar_mask(index, session_hour, session_minute)
    if mask is None:
        return False

    if index.tz is not None:
        day_index = index.tz_convert(SESSION_INPUT_TZ)
        day_mask = day_index.date == current_date
    else:
        day_mask = index.date == current_date

    anchor_bars = data.loc[mask & day_mask]
    if anchor_bars.empty:
        return position.session_high is not None

    anchor_bar = anchor_bars.iloc[-1]
    current_ts = index[-1]
    if current_ts <= anchor_bar.name:
        return position.session_high is not None

    if position.session_high is None:
        position.session_high = float(anchor_bar["High"])
        position.session_low = float(anchor_bar["Low"])
        position.session_mid = (position.session_high + position.session_low) / 2.0

    return position.session_high is not None


def _anchor_range(position):
    if position.session_high is None or position.session_low is None:
        return None
    return position.session_high - position.session_low


def _update_anchor_breakout(data, position, breakout_buffer_pct=0, side=None):
    """Mark breakout direction after a clear close beyond the anchor range."""
    if position.is_open or position.session_high is None:
        return

    if position.breakout_side is not None:
        return

    close = float(data["Close"].iloc[-1])
    rng = _anchor_range(position)
    if rng is None or rng <= 0:
        return

    buffer = rng * (breakout_buffer_pct / 100.0)
    current_ts = data.index[-1]

    if close > position.session_high + buffer and side in (None, "BUY"):
        position.breakout_side = "BUY"
        position.breakout_level = position.session_high
        position.breakout_bar_ts = current_ts
    elif close < position.session_low - buffer and side in (None, "SELL"):
        position.breakout_side = "SELL"
        position.breakout_level = position.session_low
        position.breakout_bar_ts = current_ts


def _prepare_anchor_trade(position, side, entry, win_units, loss_units):
    """SL at anchor mid, TP by risk-reward ratio."""
    sl = position.session_mid
    if sl is None:
        return False

    if side == "BUY":
        risk = entry - sl
        if risk <= 0:
            return False
        tp = entry + (win_units / loss_units) * risk
    elif side == "SELL":
        risk = sl - entry
        if risk <= 0:
            return False
        tp = entry - (win_units / loss_units) * risk
    else:
        return False

    position.intended_action = side
    position.stop_loss_price = sl
    position.take_profit_price = tp
    position.breakout_side = None
    position.breakout_level = None
    position.breakout_bar_ts = None
    position.session_traded = True
    return True


def session_retest_long(
    data,
    position,
    session_hour=15,
    session_minute=30,
    entry_deadline_hour=16,
    entry_deadline_minute=15,
    breakout_buffer_pct=0,
    retest_tolerance_pct=15,
    win_units=2,
    loss_units=1,
    *_,
    **__,
):
    """
    Long after breakout above the anchor candle high:
    1) A candle must close clearly above the anchor high (breakout).
    2) Later, price retests that high and closes back above it.

    SL: midpoint of the anchor range. TP: win_units:loss_units (default 1:2).
    All clock times are Europe/Madrid. Abandons after entry_deadline.
    """
    if position.is_open:
        return False

    _sync_session_day(position, data)

    if position.session_traded or position.session_abandoned:
        return False

    if not _update_anchor_levels(data, position, session_hour, session_minute):
        return False

    if _check_entry_deadline(data, position, entry_deadline_hour, entry_deadline_minute):
        return False

    _update_anchor_breakout(data, position, breakout_buffer_pct, side="BUY")

    if position.breakout_side != "BUY":
        return False

    current_ts = data.index[-1]
    if position.breakout_bar_ts is not None and current_ts <= position.breakout_bar_ts:
        return False

    bar = data.iloc[-1]
    close = float(bar["Close"])
    low = float(bar["Low"])
    level = position.session_high
    rng = _anchor_range(position)
    if rng is None:
        return False

    tolerance = rng * (retest_tolerance_pct / 100.0)
    retest_touch = low <= level + tolerance
    retest_confirm = close > level

    if not (retest_touch and retest_confirm):
        return False

    return _prepare_anchor_trade(position, "BUY", close, win_units, loss_units)


def session_retest_short(
    data,
    position,
    session_hour=15,
    session_minute=30,
    entry_deadline_hour=16,
    entry_deadline_minute=15,
    breakout_buffer_pct=0,
    retest_tolerance_pct=15,
    win_units=2,
    loss_units=1,
    *_,
    **__,
):
    """
    Short after breakout below the anchor candle low:
    1) A candle must close clearly below the anchor low (breakout).
    2) Later, price retests that low and closes back below it.

    SL: midpoint of the anchor range. TP: win_units:loss_units (default 1:2).
    All clock times are Europe/Madrid. Abandons after entry_deadline.
    """
    if position.is_open:
        return False

    _sync_session_day(position, data)

    if position.session_traded or position.session_abandoned:
        return False

    if not _update_anchor_levels(data, position, session_hour, session_minute):
        return False

    if _check_entry_deadline(data, position, entry_deadline_hour, entry_deadline_minute):
        return False

    _update_anchor_breakout(data, position, breakout_buffer_pct, side="SELL")

    if position.breakout_side != "SELL":
        return False

    current_ts = data.index[-1]
    if position.breakout_bar_ts is not None and current_ts <= position.breakout_bar_ts:
        return False

    bar = data.iloc[-1]
    close = float(bar["Close"])
    high = float(bar["High"])
    level = position.session_low
    rng = _anchor_range(position)
    if rng is None:
        return False

    tolerance = rng * (retest_tolerance_pct / 100.0)
    retest_touch = high >= level - tolerance
    retest_confirm = close < level

    if not (retest_touch and retest_confirm):
        return False

    return _prepare_anchor_trade(position, "SELL", close, win_units, loss_units)


def sl_session_mid(data, position, *_, **__):
    """Stop loss at the anchor range midpoint (set on entry)."""
    if position is None or not position.is_open or position.stop_loss_price is None:
        return False

    sl = position.stop_loss_price

    if position.action == "BUY":
        return float(data["Low"].iloc[-1]) <= sl

    if position.action == "SELL":
        return float(data["High"].iloc[-1]) >= sl

    return False


def tp_session_ratio(data, position, *_, **__):
    """Take profit at the price computed on entry (1:1.5, 1:2, etc.)."""
    if position is None or not position.is_open or position.take_profit_price is None:
        return False

    tp = position.take_profit_price

    if position.action == "BUY":
        return float(data["High"].iloc[-1]) >= tp

    if position.action == "SELL":
        return float(data["Low"].iloc[-1]) <= tp

    return False

