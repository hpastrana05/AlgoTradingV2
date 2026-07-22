import json
import logging
from typing import Optional

from .position import Position
from .data_manager import DataManager
from .strategy import Strategy

LOGGER = logging.getLogger("StrategyManager")


def _normalize_broker_ticker(raw) -> Optional[str]:
    """Trading212 ticker, or None when unset / explicitly 'None'."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value or value.lower() in ("none", "null", "-"):
        return None
    return value


class StrategyManager:
    def __init__(self, name: str, strategy: Strategy, position: Position, data_manager: DataManager):
        self.name = name
        self.strategy = strategy
        self.position = position
        self.data_manager = data_manager

    @classmethod
    def from_json(
        cls,
        file_path: str,
        ticker: str = None,
        period: str = None,
        interval: str = None,
    ):
        """
        Load a strategy. Optional ticker/period/interval override the JSON config
        so backtests can swap instruments/timeframes without a wasted first download.

        ticker override only affects the Yahoo/data ticker (ticker_data).
        Broker symbol always comes from ticker_API in the strategy file.
        """
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)

                entry_rule = config["entry_rule"]
                exit_rule = config["exit_rule"]

                strategy = Strategy(
                    entry_signal=entry_rule,
                    exit_signal=exit_rule,
                )

                data_ticker = (ticker or "").strip() or config["ticker_data"]
                broker_ticker = _normalize_broker_ticker(config.get("ticker_API"))
                used_period = (period or "").strip() or config.get("period")
                used_interval = (interval or "").strip() or config["interval"]

                dm = DataManager(
                    ticker=data_ticker,
                    interval=used_interval,
                    period=used_period,
                )

                position = Position(
                    ticker=data_ticker,
                    action=config["action"],
                    ticker_api=broker_ticker,
                )

                return cls(name=config["name"], strategy=strategy, position=position, data_manager=dm)

        except Exception as e:
            LOGGER.error(f"Error loading strategy from {file_path}: {e}")
            raise

    def update_market_data(self):
        self.data_manager.update_data()

    def check_strategy(self, defer_position_open=False):
        """
        Evaluate entry/exit for the current bar.

        defer_position_open: when True (backtest matching TradingView with
        process_orders_on_close=false), entry signals arm SL/TP / session state
        but do not call position.open() — the backtester fills at the next bar open.
        """
        current_price = self.data_manager.get_current_price()
        # Broker calls must use Trading212 ticker_API (may be None).
        broker_ticker = self.position.ticker_api

        # If we have an active position, only check for exit
        if self.position.is_open:
            if self.strategy.check_exit(self.data_manager.data, self.position):
                LOGGER.info(f"Exit signal triggered for: {self.name}")
                fill_price = self.position.exit_fill_price
                if fill_price is None:
                    fill_price = current_price
                exit_reason = self.position.exit_reason
                close_action = "SELL" if self.position.action == "BUY" else "BUY"
                self.position.close()
                return broker_ticker, close_action, float(fill_price), exit_reason
            return broker_ticker, "HOLD", current_price, None

        # If we do not have an active position, only check for entry
        else:
            if self.strategy.check_entry(self.data_manager.data, self.position):
                LOGGER.info(f"Entry signal triggered for: {self.name}")
                bar = self.data_manager.data.iloc[-1]
                # Prefer direction set by the entry signal (long vs short).
                # Do not silently fall back to the JSON default "action" when the
                # signal already chose a side — that default is only for
                # single-direction strategies that never set intended_action.
                entry_action = self.position.intended_action
                if not entry_action:
                    entry_action = self.position.action
                    LOGGER.warning(
                        f"{self.name}: entry without intended_action; "
                        f"using strategy default action={entry_action}"
                    )
                if entry_action not in ("BUY", "SELL"):
                    LOGGER.error(
                        f"{self.name}: invalid entry_action={entry_action!r}; skipping"
                    )
                    return broker_ticker, "HOLD", current_price, None
                if not defer_position_open:
                    self.position.open(
                        entry_price=current_price,
                        candle_low=bar["Low"],
                        candle_high=bar["High"],
                        action=entry_action,
                        entry_time=self.data_manager.data.index[-1],
                    )
                return broker_ticker, entry_action, current_price, None
            return broker_ticker, "HOLD", current_price, None
