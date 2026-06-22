from .signals import build_signal

class Strategy:

    def __init__(self, entry_signal:dict, exit_signal:dict):
        self.entry_signal = build_signal(entry_signal)
        self.exit_signal = build_signal(exit_signal)

    def check_entry(self, data, position) -> bool:
        return self.entry_signal.evaluate(data, position)

    def check_exit(self, data, position) -> bool:
        return self.exit_signal.evaluate(data, position)