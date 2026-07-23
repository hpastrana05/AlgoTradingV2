from .signals import AND, OR, FunctionSignal, build_signal
from signals.entry_exit_signals import _session_tp_from_ratio, _tp_from_fixed_points


class Strategy:

    def __init__(self, entry_signal: dict, exit_signal: dict):
        self.entry_signal = build_signal(entry_signal)
        self.exit_signal = build_signal(exit_signal)

    def check_entry(self, data, position) -> bool:
        return self.entry_signal.evaluate(data, position)

    def check_exit(self, data, position) -> bool:
        return self.exit_signal.evaluate(data, position)

    def arm_exit_levels(self, position) -> None:
        """
        Derive SL/TP prices from exit-rule params without triggering an exit.
        Used right after entry so take_profit_price is available for alerts/UI.
        """
        self._arm_exit_levels(self.exit_signal, position)

    @staticmethod
    def _arm_exit_levels(signal, position) -> None:
        if isinstance(signal, (AND, OR)):
            for child in signal.signals:
                Strategy._arm_exit_levels(child, position)
            return
        if not isinstance(signal, FunctionSignal):
            return
        name = getattr(signal.fn, "__name__", "")
        if name == "tp_session_ratio":
            tp = _session_tp_from_ratio(
                position,
                signal.params.get("win_units", 1.75),
                signal.params.get("loss_units", 1),
            )
            if tp is not None:
                position.take_profit_price = tp
        elif name == "tp_fixed_points":
            tp = _tp_from_fixed_points(
                position,
                signal.params.get("points", 10),
            )
            if tp is not None:
                position.take_profit_price = tp
