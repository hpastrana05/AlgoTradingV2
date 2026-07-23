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
        tp_price = entry * (1 + percentage)
        if data["Close"].iloc[-1] >= tp_price:
            _arm_exit(position, data, tp_price, "TP", is_stop=False)
            return True
        return False

    elif position.action == "SELL":
        tp_price = entry * (1 - percentage)
        if data["Close"].iloc[-1] <= tp_price:
            _arm_exit(position, data, tp_price, "TP", is_stop=False)
            return True
        return False

    else:
        return False


def sl_percentage(data, percentage, position, *_, **__):
    if position is None or position.entry_price is None:
        return False
    entry = position.entry_price

    percentage = percentage / 100

    if position.action == "BUY":
        stop_price = entry * (1 - percentage)
        if data["Close"].iloc[-1] <= stop_price:
            _arm_exit(position, data, stop_price, "SL", is_stop=True)
            return True
        return False

    elif position.action == "SELL":
        stop_price = entry * (1 + percentage)
        if data["Close"].iloc[-1] >= stop_price:
            _arm_exit(position, data, stop_price, "SL", is_stop=True)
            return True
        return False

    else:
        return False


def sl_lowest_value_last_candle(data, position, *_, **__):
    """Stop loss at the low (long) or high (short) of the entry candle."""
    if position is None or not position.is_open:
        return False

    if position.action == "BUY":
        if position.entry_candle_low is None:
            return False
        level = position.entry_candle_low
        if data["Low"].iloc[-1] <= level:
            _arm_exit(position, data, level, "SL", is_stop=True)
            return True
        return False

    if position.action == "SELL":
        if position.entry_candle_high is None:
            return False
        level = position.entry_candle_high
        if data["High"].iloc[-1] >= level:
            _arm_exit(position, data, level, "SL", is_stop=True)
            return True
        return False

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
        if data["High"].iloc[-1] >= tp_price:
            _arm_exit(position, data, tp_price, "TP", is_stop=False)
            return True
        return False

    if position.action == "SELL":
        if data["Low"].iloc[-1] <= tp_price:
            _arm_exit(position, data, tp_price, "TP", is_stop=False)
            return True
        return False

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


def _past_deadline(data, hour, minute):
    """True once the current Madrid bar is strictly after hour:minute."""
    return _local_bar_minutes(data.index) > hour * 60 + minute


def _resolve_session_deadlines(
    breakout_deadline_hour,
    breakout_deadline_minute,
    retest_deadline_hour,
    retest_deadline_minute,
    entry_deadline_hour=None,
    entry_deadline_minute=None,
):
    """
    Breakout window vs retest window (Europe/Madrid).

    Legacy entry_deadline_* maps to the breakout deadline.
    """
    if entry_deadline_hour is not None:
        breakout_deadline_hour = entry_deadline_hour
    if entry_deadline_minute is not None:
        breakout_deadline_minute = entry_deadline_minute
    return (
        breakout_deadline_hour,
        breakout_deadline_minute,
        retest_deadline_hour,
        retest_deadline_minute,
    )


def _check_session_windows(
    data,
    position,
    breakout_deadline_hour,
    breakout_deadline_minute,
    retest_deadline_hour,
    retest_deadline_minute,
):
    """
    Abandon the day when:
    - retest deadline has passed with no entry, or
    - breakout deadline has passed and there is still no active breakout.

    If a breakout is already marked, retest may continue until the retest deadline.
    Returns True when the setup is abandoned (caller should not enter).
    """
    if position.session_traded or position.session_abandoned:
        return position.session_abandoned

    if position.session_high is None:
        return False

    if _past_deadline(data, retest_deadline_hour, retest_deadline_minute):
        position.session_abandoned = True
        return True

    if (
        _past_deadline(data, breakout_deadline_hour, breakout_deadline_minute)
        and position.breakout_side is None
    ):
        position.session_abandoned = True
        return True

    return False


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


def _clear_breakout_state(position):
    position.breakout_side = None
    position.breakout_level = None
    position.breakout_bar_ts = None
    position.breakout_extended = False


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
        position.breakout_extended = False
    elif close < position.session_low - buffer and side in (None, "SELL"):
        position.breakout_side = "SELL"
        position.breakout_level = position.session_low
        position.breakout_bar_ts = current_ts
        position.breakout_extended = False


def _invalidate_failed_breakout(data, position):
    """
    Clear a breakout if price closes back through the broken level.

    Without this, a failed breakout (close back inside the anchor range) can
    still produce a later 'retest' entry — which is not a valid setup.
    """
    if position.breakout_side is None or position.session_high is None:
        return

    # Never invalidate on the breakout bar itself
    current_ts = data.index[-1]
    if position.breakout_bar_ts is not None and current_ts <= position.breakout_bar_ts:
        return

    close = float(data["Close"].iloc[-1])
    if position.breakout_side == "BUY" and close <= position.session_high:
        _clear_breakout_state(position)
    elif position.breakout_side == "SELL" and close >= position.session_low:
        _clear_breakout_state(position)


def _update_breakout_extension(data, position):
    """
    Mark that price has held beyond the broken level after the breakout bar.

    Extension = at least one later bar that still closes beyond the level
    (acceptance outside the range). A retest wick on that same bar is allowed —
    e.g. short breakout, next bar wicks back up to the broken low and closes below.
    """
    if position.breakout_side is None or position.breakout_extended:
        return
    if position.breakout_bar_ts is None:
        return

    current_ts = data.index[-1]
    if current_ts <= position.breakout_bar_ts:
        return

    close = float(data["Close"].iloc[-1])
    if position.breakout_side == "BUY" and close > position.session_high:
        position.breakout_extended = True
    elif position.breakout_side == "SELL" and close < position.session_low:
        position.breakout_extended = True


def _prepare_anchor_trade(position, side, entry):
    """
    Arm entry side + SL at the opposite extreme of the anchor candle:
      BUY  → SL at session_low
      SELL → SL at session_high
    Take-profit is NOT set here — configure win_units/loss_units on tp_session_ratio.
    """
    if side == "BUY":
        sl = position.session_low
        if sl is None:
            return False
        if entry - sl <= 0:
            return False
    elif side == "SELL":
        sl = position.session_high
        if sl is None:
            return False
        if sl - entry <= 0:
            return False
    else:
        return False

    position.intended_action = side
    position.stop_loss_price = sl
    position.take_profit_price = None
    _clear_breakout_state(position)
    position.session_traded = True
    return True


def _long_retest_ok(bar, level, sl_level, rng, retest_tolerance_pct):
    """
    Chart-style long retest: pullback from above that wicks the broken high
    and closes back above it, without stabbing through the SL (anchor low).
    """
    open_px = float(bar["Open"])
    high = float(bar["High"])
    low = float(bar["Low"])
    close = float(bar["Close"])

    if sl_level is None or rng is None or rng <= 0:
        return False
    if low < sl_level:
        return False
    # Must approach from above the broken level
    if open_px <= level:
        return False
    # Still trading above during the bar (not a close-only spike)
    if high <= level:
        return False

    tolerance = rng * (retest_tolerance_pct / 100.0)
    touched = low <= level + tolerance
    held = close > level
    return touched and held


def _short_retest_ok(bar, level, sl_level, rng, retest_tolerance_pct):
    """Chart-style short retest: pullback from below that wicks the broken low,
    without stabbing through the SL (anchor high)."""
    open_px = float(bar["Open"])
    high = float(bar["High"])
    low = float(bar["Low"])
    close = float(bar["Close"])

    if sl_level is None or rng is None or rng <= 0:
        return False
    if high > sl_level:
        return False
    if open_px >= level:
        return False
    if low >= level:
        return False

    tolerance = rng * (retest_tolerance_pct / 100.0)
    touched = high >= level - tolerance
    held = close < level
    return touched and held


def session_retest_long(
    data,
    position,
    session_hour=15,
    session_minute=30,
    breakout_deadline_hour=16,
    breakout_deadline_minute=15,
    retest_deadline_hour=23,
    retest_deadline_minute=0,
    entry_deadline_hour=None,
    entry_deadline_minute=None,
    breakout_buffer_pct=0,
    retest_tolerance_pct=0,
    *_,
    **__,
):
    """
    Long breakout + retest of the Madrid-session anchor candle (see chart pattern):

    1) Breakout: candle closes above the anchor high (before breakout_deadline).
    2) Extension: later a full candle trades entirely above that high.
    3) Retest: pullback from above that wicks the broken high and closes back
       above it (allowed until retest_deadline, default 23:00 Madrid).
    4) Invalidation: close back at/below the high clears the breakout.
    5) Retest must not stab through the opposite extreme (SL = anchor low).

    SL at anchor low. Configure TP ratio on tp_session_ratio (win_units/loss_units).
    """
    if position.is_open:
        return False

    (
        breakout_deadline_hour,
        breakout_deadline_minute,
        retest_deadline_hour,
        retest_deadline_minute,
    ) = _resolve_session_deadlines(
        breakout_deadline_hour,
        breakout_deadline_minute,
        retest_deadline_hour,
        retest_deadline_minute,
        entry_deadline_hour,
        entry_deadline_minute,
    )

    _sync_session_day(position, data)

    if position.session_traded or position.session_abandoned:
        return False

    if not _update_anchor_levels(data, position, session_hour, session_minute):
        return False

    _invalidate_failed_breakout(data, position)

    if _check_session_windows(
        data,
        position,
        breakout_deadline_hour,
        breakout_deadline_minute,
        retest_deadline_hour,
        retest_deadline_minute,
    ):
        return False

    # New breakouts only inside the breakout window
    if not _past_deadline(data, breakout_deadline_hour, breakout_deadline_minute):
        _update_anchor_breakout(data, position, breakout_buffer_pct, side="BUY")

    if position.breakout_side != "BUY":
        return False

    current_ts = data.index[-1]
    if position.breakout_bar_ts is not None and current_ts <= position.breakout_bar_ts:
        return False

    _update_breakout_extension(data, position)
    if not position.breakout_extended:
        return False

    bar = data.iloc[-1]
    level = position.session_high
    sl_level = position.session_low
    rng = _anchor_range(position)
    if not _long_retest_ok(bar, level, sl_level, rng, retest_tolerance_pct):
        return False

    return _prepare_anchor_trade(position, "BUY", float(bar["Close"]))


def session_retest_short(
    data,
    position,
    session_hour=15,
    session_minute=30,
    breakout_deadline_hour=16,
    breakout_deadline_minute=15,
    retest_deadline_hour=23,
    retest_deadline_minute=0,
    entry_deadline_hour=None,
    entry_deadline_minute=None,
    breakout_buffer_pct=0,
    retest_tolerance_pct=0,
    *_,
    **__,
):
    """
    Short breakout + retest of the Madrid-session anchor candle (mirror of long):

    1) Breakout: candle closes below the anchor low (before breakout_deadline).
    2) Extension: later a full candle trades entirely below that low.
    3) Retest: pullback from below that wicks the broken low and closes back
       below it (allowed until retest_deadline, default 23:00 Madrid).
    4) Invalidation: close back at/above the low clears the breakout.
    5) Retest must not stab through the opposite extreme (SL = anchor high).

    SL at anchor high. Configure TP ratio on tp_session_ratio (win_units/loss_units).
    """
    if position.is_open:
        return False

    (
        breakout_deadline_hour,
        breakout_deadline_minute,
        retest_deadline_hour,
        retest_deadline_minute,
    ) = _resolve_session_deadlines(
        breakout_deadline_hour,
        breakout_deadline_minute,
        retest_deadline_hour,
        retest_deadline_minute,
        entry_deadline_hour,
        entry_deadline_minute,
    )

    _sync_session_day(position, data)

    if position.session_traded or position.session_abandoned:
        return False

    if not _update_anchor_levels(data, position, session_hour, session_minute):
        return False

    _invalidate_failed_breakout(data, position)

    if _check_session_windows(
        data,
        position,
        breakout_deadline_hour,
        breakout_deadline_minute,
        retest_deadline_hour,
        retest_deadline_minute,
    ):
        return False

    if not _past_deadline(data, breakout_deadline_hour, breakout_deadline_minute):
        _update_anchor_breakout(data, position, breakout_buffer_pct, side="SELL")

    if position.breakout_side != "SELL":
        return False

    current_ts = data.index[-1]
    if position.breakout_bar_ts is not None and current_ts <= position.breakout_bar_ts:
        return False

    _update_breakout_extension(data, position)
    if not position.breakout_extended:
        return False

    bar = data.iloc[-1]
    level = position.session_low
    sl_level = position.session_high
    rng = _anchor_range(position)
    if not _short_retest_ok(bar, level, sl_level, rng, retest_tolerance_pct):
        return False

    return _prepare_anchor_trade(position, "SELL", float(bar["Close"]))


def _gap_aware_fill(data, level, action, is_stop):
    """
    Fill at the level unless the bar opened through it (gap), then use Open.
    action is the position side: BUY (long) or SELL (short).
    """
    open_px = float(data["Open"].iloc[-1])
    if action == "BUY":
        if is_stop:
            return open_px if open_px < level else level
        return open_px if open_px > level else level
    if action == "SELL":
        if is_stop:
            return open_px if open_px > level else level
        return open_px if open_px < level else level
    return float(data["Close"].iloc[-1])


def _arm_exit(position, data, level, reason, is_stop):
    position.exit_fill_price = _gap_aware_fill(data, level, position.action, is_stop)
    position.exit_reason = reason


def sl_session_mid(data, position, *_, **__):
    """Stop loss at the level stored on entry (legacy name; uses stop_loss_price)."""
    return sl_session_extreme(data, position)


def sl_session_extreme(data, position, *_, **__):
    """
    Stop loss at the opposite extreme of the session/anchor candle:
      long  → session low
      short → session high
    Level is set on entry in stop_loss_price.
    """
    if position is None or not position.is_open or position.stop_loss_price is None:
        return False

    sl = position.stop_loss_price

    if position.action == "BUY":
        if float(data["Low"].iloc[-1]) <= sl:
            _arm_exit(position, data, sl, "SL", is_stop=True)
            return True
        return False

    if position.action == "SELL":
        if float(data["High"].iloc[-1]) >= sl:
            _arm_exit(position, data, sl, "SL", is_stop=True)
            return True
        return False

    return False


def _session_tp_from_ratio(position, win_units, loss_units):
    """TP from entry + SL distance × (win_units / loss_units)."""
    entry = position.entry_price
    sl = position.stop_loss_price
    if entry is None or sl is None:
        return None
    if loss_units is None or float(loss_units) <= 0:
        return None

    ratio = float(win_units) / float(loss_units)
    if position.action == "BUY":
        risk = float(entry) - float(sl)
        if risk <= 0:
            return None
        return float(entry) + ratio * risk
    if position.action == "SELL":
        risk = float(sl) - float(entry)
        if risk <= 0:
            return None
        return float(entry) - ratio * risk
    return None


def tp_session_ratio(
    data,
    position,
    win_units=1.75,
    loss_units=1,
    *_,
    **__,
):
    """
    Take profit sized from the session SL distance.
    Example: loss_units=1, win_units=1.75 → target 1.75R from entry.
    Put win_units / loss_units here (not on the entry signals).
    """
    if position is None or not position.is_open:
        return False

    tp = _session_tp_from_ratio(position, win_units, loss_units)
    if tp is None:
        return False

    position.take_profit_price = tp

    if position.action == "BUY":
        if float(data["High"].iloc[-1]) >= tp:
            _arm_exit(position, data, tp, "TP", is_stop=False)
            return True
        return False

    if position.action == "SELL":
        if float(data["Low"].iloc[-1]) <= tp:
            _arm_exit(position, data, tp, "TP", is_stop=False)
            return True
        return False

    return False


def flatten_session_eod(
    data,
    position,
    flatten_hour=23,
    flatten_minute=0,
    *_,
    **__,
):
    """
    Force-close any open position at/after flatten time the SAME Madrid day.

    Default 23:00. Use this for same-day-only trades.
    For overnight holds until before the next session, use
    flatten_before_next_session instead.
    """
    if position is None or not position.is_open:
        return False

    if _local_bar_minutes(data.index) < flatten_hour * 60 + flatten_minute:
        return False

    position.exit_fill_price = float(data["Close"].iloc[-1])
    position.exit_reason = "EOD"
    return True


def flatten_before_next_session(
    data,
    position,
    flatten_hour=14,
    flatten_minute=0,
    *_,
    **__,
):
    """
    Allow overnight holds; flatten the next Madrid calendar day at/after
    flatten_hour:flatten_minute (default 14:00), before the next 15:30 setup.

    Does nothing on the entry day — only starting the following Madrid date.
    """
    if position is None or not position.is_open or position.entry_time is None:
        return False

    entry_ts = position.entry_time
    try:
        import pandas as pd
        entry_ts = pd.Timestamp(entry_ts)
        if entry_ts.tzinfo is not None:
            entry_date = entry_ts.tz_convert(SESSION_INPUT_TZ).date()
        else:
            entry_date = entry_ts.date()
    except Exception:
        entry_date = entry_ts.date() if hasattr(entry_ts, "date") else None

    if entry_date is None:
        return False

    current_date = _session_date_for_bar(data.index)
    if current_date <= entry_date:
        return False

    if _local_bar_minutes(data.index) < flatten_hour * 60 + flatten_minute:
        return False

    position.exit_fill_price = float(data["Close"].iloc[-1])
    position.exit_reason = "EOD"
    return True


# ---------------------------------------------------------------------------
# Opening-range breakout (first N session bars, e.g. 15:30 + 15:45 on 15m)
# ---------------------------------------------------------------------------

def _opening_range_bar_minutes(session_hour, session_minute, range_bars, bar_minutes):
    """Madrid minute-of-day for each bar in the opening range."""
    start = int(session_hour) * 60 + int(session_minute)
    step = int(bar_minutes)
    n = int(range_bars)
    return [start + i * step for i in range(n)]


def _day_local_index(index, current_date):
    if index.tz is not None:
        day_index = index.tz_convert(SESSION_INPUT_TZ)
        day_mask = day_index.date == current_date
        return day_index, day_mask
    return index, index.date == current_date


def _update_opening_range_levels(
    data,
    position,
    session_hour=15,
    session_minute=30,
    range_bars=2,
    bar_minutes=15,
):
    """
    After the opening-range bars have closed, store combined high/low on the
    position (max high / min low across those bars).

    Default: 15:30 and 15:45 Madrid on a 15m chart.
    Levels are only active once the current bar is strictly after the last
    range bar (entries happen on subsequent candles).
    """
    if len(data) < int(range_bars) + 1:
        return False

    index = data.index
    current_date = _sync_session_day(position, data)
    day_index, day_mask = _day_local_index(index, current_date)

    expected = _opening_range_bar_minutes(
        session_hour, session_minute, range_bars, bar_minutes
    )
    minutes = day_index.hour * 60 + day_index.minute
    range_mask = day_mask & minutes.isin(expected)
    range_bars_df = data.loc[range_mask]

    if len(range_bars_df) < int(range_bars):
        return position.session_high is not None

    # Use the first N matching bars in chronological order
    range_bars_df = range_bars_df.iloc[: int(range_bars)]
    last_range_ts = range_bars_df.index[-1]
    current_ts = index[-1]
    if current_ts <= last_range_ts:
        return position.session_high is not None

    if position.session_high is None:
        position.session_high = float(range_bars_df["High"].max())
        position.session_low = float(range_bars_df["Low"].min())
        position.session_mid = (position.session_high + position.session_low) / 2.0

    return position.session_high is not None


def _prepare_opening_range_trade(position, side, entry):
    """
    Arm entry + SL at the opposite side of the opening range:
      BUY  → SL at range low
      SELL → SL at range high
    TP is configured on tp_fixed_points (or another exit signal).
    """
    if side == "BUY":
        sl = position.session_low
        if sl is None or entry - sl <= 0:
            return False
    elif side == "SELL":
        sl = position.session_high
        if sl is None or sl - entry <= 0:
            return False
    else:
        return False

    position.intended_action = side
    position.stop_loss_price = sl
    position.take_profit_price = None
    _clear_breakout_state(position)
    position.session_traded = True
    return True


def _session_two_bar_breakout(
    data,
    position,
    side,
    session_hour=15,
    session_minute=30,
    range_bars=2,
    bar_minutes=15,
    entry_deadline_hour=23,
    entry_deadline_minute=0,
    breakout_buffer_pct=0,
):
    if position.is_open:
        return False

    _sync_session_day(position, data)

    if position.session_traded or position.session_abandoned:
        return False

    if not _update_opening_range_levels(
        data,
        position,
        session_hour=session_hour,
        session_minute=session_minute,
        range_bars=range_bars,
        bar_minutes=bar_minutes,
    ):
        return False

    if _past_deadline(data, entry_deadline_hour, entry_deadline_minute):
        position.session_abandoned = True
        return False

    close = float(data["Close"].iloc[-1])
    rng = _anchor_range(position)
    if rng is None or rng <= 0:
        return False

    buffer = rng * (float(breakout_buffer_pct) / 100.0)

    if side == "BUY":
        if close <= position.session_high + buffer:
            return False
        return _prepare_opening_range_trade(position, "BUY", close)

    if side == "SELL":
        if close >= position.session_low - buffer:
            return False
        return _prepare_opening_range_trade(position, "SELL", close)

    return False


def session_two_bar_breakout_long(
    data,
    position,
    session_hour=15,
    session_minute=30,
    range_bars=2,
    bar_minutes=15,
    entry_deadline_hour=23,
    entry_deadline_minute=0,
    breakout_buffer_pct=0,
    *_,
    **__,
):
    """
    Long breakout of the opening range (default: first two 15m bars from 15:30 Madrid).

    Range high/low = max high / min low of those bars. Entry when a later candle
    closes above the range high. SL at range low; set TP on tp_fixed_points.
    """
    return _session_two_bar_breakout(
        data,
        position,
        "BUY",
        session_hour=session_hour,
        session_minute=session_minute,
        range_bars=range_bars,
        bar_minutes=bar_minutes,
        entry_deadline_hour=entry_deadline_hour,
        entry_deadline_minute=entry_deadline_minute,
        breakout_buffer_pct=breakout_buffer_pct,
    )


def session_two_bar_breakout_short(
    data,
    position,
    session_hour=15,
    session_minute=30,
    range_bars=2,
    bar_minutes=15,
    entry_deadline_hour=23,
    entry_deadline_minute=0,
    breakout_buffer_pct=0,
    *_,
    **__,
):
    """
    Short breakout of the opening range (default: first two 15m bars from 15:30 Madrid).

    Entry when a later candle closes below the range low. SL at range high;
    set TP on tp_fixed_points.
    """
    return _session_two_bar_breakout(
        data,
        position,
        "SELL",
        session_hour=session_hour,
        session_minute=session_minute,
        range_bars=range_bars,
        bar_minutes=bar_minutes,
        entry_deadline_hour=entry_deadline_hour,
        entry_deadline_minute=entry_deadline_minute,
        breakout_buffer_pct=breakout_buffer_pct,
    )


def _tp_from_fixed_points(position, points):
    """TP = entry ± points (BUY above, SELL below)."""
    entry = position.entry_price
    if entry is None or points is None:
        return None
    pts = float(points)
    if pts <= 0:
        return None
    if position.action == "BUY":
        return float(entry) + pts
    if position.action == "SELL":
        return float(entry) - pts
    return None


def tp_fixed_points(
    data,
    position,
    points=10,
    *_,
    **__,
):
    """
    Take profit a fixed number of price points from entry.
    Example: points=10 → long TP = entry+10, short TP = entry-10.
    """
    if position is None or not position.is_open:
        return False

    tp = _tp_from_fixed_points(position, points)
    if tp is None:
        return False

    position.take_profit_price = tp

    if position.action == "BUY":
        if float(data["High"].iloc[-1]) >= tp:
            _arm_exit(position, data, tp, "TP", is_stop=False)
            return True
        return False

    if position.action == "SELL":
        if float(data["Low"].iloc[-1]) <= tp:
            _arm_exit(position, data, tp, "TP", is_stop=False)
            return True
        return False

    return False

