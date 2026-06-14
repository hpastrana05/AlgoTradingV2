import logging
from signals.entry_exit_signals import *


SIGNAL_REGISTRY = {
    "ema_cross_above": ema_cross_above,
    "ema_cross_below": ema_cross_below,
    "price_over_ema": price_over_ema,
    "ema_over_ema": ema_over_ema,
    "rsi_between": rsi_between,
    "bullish_MACD_cross": bullish_MACD_cross,
    "bearish_MACD_cross": bearish_MACD_cross,
}


LOGGER = logging.getLogger("Signals")



class FunctionSignal:
    def __init__(self, fn, params: dict):
        self.fn = fn
        self.params = params
    
    def evaluate(self, data) -> bool:
        return self.fn(data, **self.params)


class AND:
    def __init__(self, *signals):
        self.signals = signals
    
    def evaluate(self, data) -> bool:
        return all(s.evaluate(data) for s in self.signals)

class OR:
    def __init__(self, *signals):
        self.signals = signals
    
    def evaluate(self, data) -> bool:
        return any(s.evaluate(data) for s in self.signals)
    

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