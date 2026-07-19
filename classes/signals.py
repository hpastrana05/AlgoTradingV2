import logging
import numpy
import inspect
import signals.entry_exit_signals as entry_exit_signals
from signals.entry_exit_signals import *

# Dynamically populate SIGNAL_REGISTRY with all functions defined in signals.entry_exit_signals
SIGNAL_REGISTRY = {
    name: obj
    for name, obj in inspect.getmembers(entry_exit_signals, inspect.isfunction)
    if obj.__module__ == entry_exit_signals.__name__
}


LOGGER = logging.getLogger("Signals")



class FunctionSignal:
    def __init__(self, fn, params: dict):
        self.fn = fn
        self.params = params
    
    def evaluate(self, data, position = None) -> bool:
        result = self.fn(data, **self.params, position = position)

        if not isinstance(result, (numpy.bool, bool)):
            LOGGER.fatal(f"Evaluation error of: {self.fn}. Result and result type: {result}, {type(result)}")

        return result


class AND:
    def __init__(self, *signals):
        self.signals = signals
    
    def evaluate(self, data, position=None) -> bool:
        return all(s.evaluate(data, position) for s in self.signals)

class OR:
    def __init__(self, *signals):
        self.signals = signals
    
    def evaluate(self, data, position = None) -> bool:
        return any(s.evaluate(data, position) for s in self.signals)
    

def build_signal(config: dict):
    t = config["type"]

    if t == "AND":
        return AND(*[build_signal(s) for s in config["signals"]])
    if t == "OR":
        return OR(*[build_signal(s) for s in config["signals"]])

    if t in SIGNAL_REGISTRY:
        params = {k: v for k, v in config.items() if k != "type"}
        return FunctionSignal(SIGNAL_REGISTRY[t], params)

    LOGGER.error(f"Unknown signal type: {t}")
    raise ValueError(f"Unknown signal type: {t}")


def _add_indicator(indicators: dict, name: str, value):
    values = indicators.setdefault(name, [])
    if value not in values:
        values.append(value)


def _extract_indicators_from_node(node: dict, indicators: dict):
    """Walk a rule tree and collect indicator specs required by leaf signals."""
    t = node.get("type")
    if t in ("AND", "OR"):
        for child in node.get("signals", []):
            _extract_indicators_from_node(child, indicators)
        return

    params = {k: v for k, v in node.items() if k != "type"}

    if t in ("ema_cross_above", "ema_cross_below"):
        _add_indicator(indicators, "EMA", params["fast"])
        _add_indicator(indicators, "EMA", params["slow"])
    elif t in ("sma_cross_above", "sma_cross_below"):
        _add_indicator(indicators, "SMA", params["fast"])
        _add_indicator(indicators, "SMA", params["slow"])
    elif t in ("ema_sma_cross_above", "ema_sma_cross_below", "ema_over_sma"):
        _add_indicator(indicators, "EMA", params["ema_value"])
        _add_indicator(indicators, "SMA", params["sma_value"])
    elif t == "price_over_ema":
        _add_indicator(indicators, "EMA", params["ema_value"])
    elif t in ("price_over_sma", "candle_above_sma", "candle_below_sma"):
        _add_indicator(indicators, "SMA", params["sma_value"])
    elif t == "ema_over_ema":
        _add_indicator(indicators, "EMA", params["ema1"])
        _add_indicator(indicators, "EMA", params["ema2"])
    elif t == "rsi_between":
        _add_indicator(indicators, "RSI", params["rsi_value"])
    elif t in ("bullish_MACD_cross", "bearish_MACD_cross"):
        _add_indicator(indicators, "MACD", list(params["values"]))
    # tp_percentage / sl_percentage need no indicators


def derive_indicators(*rule_configs) -> dict:
    """
    Build the indicators dict DataManager needs from entry/exit rule trees.
    Removes the need to declare indicators separately in strategy JSON.
    """
    indicators = {}
    for rule in rule_configs:
        if rule:
            _extract_indicators_from_node(rule, indicators)
    return indicators
