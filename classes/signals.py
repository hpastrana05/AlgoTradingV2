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
    and not name.startswith("_")
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
