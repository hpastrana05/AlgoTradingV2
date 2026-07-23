import logging
import pandas as pd
import numpy as np
from .strategy_manager import StrategyManager

LOGGER = logging.getLogger("Backtesting")


class Backtesting:

    def __init__(
        self,
        strategy_path,
        initial_capital=10000.0,
        commission=0.0,
        ticker=None,
        period=None,
        interval=None,
        risk_pct=1.0,
        fill_on_next_open=True,
    ):
        self.strategy_manager = StrategyManager.from_json(
            strategy_path,
            ticker=ticker,
            period=period,
            interval=interval,
        )
        self.initial_capital = initial_capital
        self.commission = commission
        # Fraction of equity risked to the stop on each trade (e.g. 0.01 = 1%).
        # 1.0 = risk 100% of equity to the stop (caps at all-in) — matches TV
        # default_qty_type = percent_of_equity 100 for typical session stops.
        # When no stop is set, falls back to full capital.
        self.risk_pct = risk_pct
        # True → match TradingView process_orders_on_close=false (fill next open).
        # False → fill at signal-bar close (live-engine style).
        self.fill_on_next_open = fill_on_next_open

    def _size_shares(self, cash, price, stop_loss_price):
        """Risk-based size capped at available cash (1x)."""
        if price <= 0 or cash <= 0:
            return 0.0

        max_shares = (cash * (1.0 - self.commission)) / price
        if stop_loss_price is None:
            return max_shares

        risk_per_share = abs(price - float(stop_loss_price))
        if risk_per_share <= 0:
            return max_shares

        risk_budget = cash * self.risk_pct
        return min(risk_budget / risk_per_share, max_shares)

    @staticmethod
    def _exit_trade_type(position_side, exit_reason):
        is_long = position_side == "LONG"
        if exit_reason == "EOD":
            return "EOD_SELL" if is_long else "EOD_COVER"
        if exit_reason == "SL":
            return "SL_SELL" if is_long else "SL_COVER"
        if exit_reason == "TP":
            return "TP_SELL" if is_long else "TP_COVER"
        return "SELL" if is_long else "COVER"

    def run_backtest(self, data=None):
        """
        Runs the backtest on the provided data or the data fetched by the data manager.
        If data is a pandas DataFrame, we update the data manager's data.
        """
        if data is not None:
            from .data_manager import DataManager
            self.strategy_manager.data_manager.data = DataManager._ensure_madrid_timezone(data.copy())

        full_data = self.strategy_manager.data_manager.data
        if full_data is None or full_data.empty:
            LOGGER.error("No historical data available for backtesting.")
            return None

        # Reset position in strategy manager
        self.strategy_manager.position.close()

        cash = self.initial_capital
        shares = 0.0
        position_active = False
        position_side = None  # "LONG" or "SHORT"
        short_entry_price = None
        trades = []
        portfolio_value_history = []

        def _portfolio_value(market_price):
            if not position_active:
                return cash
            if position_side == "LONG":
                return cash + shares * market_price
            return cash + shares * (short_entry_price - market_price)

        def _equity_mark(market_price):
            return _portfolio_value(market_price)

        LOGGER.info(
            f"Starting backtest on {len(full_data)} data rows with initial "
            f"capital: {self.initial_capital}, risk_pct: {self.risk_pct}, "
            f"fill_on_next_open: {self.fill_on_next_open}"
        )

        # Queued entry from prior bar (TradingView next-bar open fill).
        pending_entry = None  # {"action": "BUY"|"SELL", "signal_time": ts}
        ticker = self.strategy_manager.position.ticker

        def _open_long(fill_price, fill_time, signal_time=None):
            nonlocal cash, shares, position_active, position_side
            sl = self.strategy_manager.position.stop_loss_price
            sized = self._size_shares(cash, fill_price, sl)
            if sized <= 0:
                LOGGER.warning(f"[{fill_time}] BUY skipped — zero size")
                self.strategy_manager.position.close()
                return False
            spend = sized * fill_price / (1.0 - self.commission)
            cash -= spend
            shares = sized
            position_active = True
            position_side = "LONG"
            self.strategy_manager.position.open(
                entry_price=fill_price,
                candle_low=float(current_row["Low"]),
                candle_high=float(current_row["High"]),
                action="BUY",
                entry_time=signal_time if signal_time is not None else fill_time,
            )
            self.strategy_manager.strategy.arm_exit_levels(
                self.strategy_manager.position
            )
            equity = _equity_mark(fill_price)
            trades.append({
                "type": "BUY",
                "side": "LONG",
                "timestamp": fill_time,
                "price": fill_price,
                "shares": shares,
                "portfolio_value": equity,
            })
            LOGGER.debug(
                f"[{fill_time}] BUY {shares:.4f} shares of {ticker} "
                f"at {fill_price:.2f} (spend={spend:.2f}, cash_left={cash:.2f})"
            )
            return True

        def _open_short(fill_price, fill_time, signal_time=None):
            nonlocal cash, shares, position_active, position_side, short_entry_price
            sl = self.strategy_manager.position.stop_loss_price
            sized = self._size_shares(cash, fill_price, sl)
            if sized <= 0:
                LOGGER.warning(f"[{fill_time}] SHORT skipped — zero size")
                self.strategy_manager.position.close()
                return False
            shares = sized
            short_entry_price = fill_price
            position_active = True
            position_side = "SHORT"
            self.strategy_manager.position.open(
                entry_price=fill_price,
                candle_low=float(current_row["Low"]),
                candle_high=float(current_row["High"]),
                action="SELL",
                entry_time=signal_time if signal_time is not None else fill_time,
            )
            self.strategy_manager.strategy.arm_exit_levels(
                self.strategy_manager.position
            )
            equity = _equity_mark(fill_price)
            trades.append({
                "type": "SHORT",
                "side": "SHORT",
                "timestamp": fill_time,
                "price": fill_price,
                "shares": shares,
                "portfolio_value": equity,
            })
            LOGGER.debug(
                f"[{fill_time}] SHORT {shares:.4f} shares of {ticker} "
                f"at {fill_price:.2f}"
            )
            return True

        for i in range(len(full_data)):
            # Slice the data so the strategy only sees up to index i (inclusive)
            # This simulates real-time data arriving bar-by-bar and prevents look-ahead bias.
            slice_df = full_data.iloc[:i+1]

            current_row = slice_df.iloc[-1]
            if pd.isna(current_row["Close"]):
                continue

            # Update the strategy manager's view of the data
            self.strategy_manager.data_manager.data = slice_df

            # 1) Fill a queued entry at this bar's Open (TV next-bar fill).
            if pending_entry is not None and not position_active:
                open_px = float(current_row["Open"])
                if pd.isna(open_px) or open_px <= 0:
                    LOGGER.warning(
                        f"[{current_row.name}] pending entry dropped — bad Open"
                    )
                    self.strategy_manager.position.close()
                    pending_entry = None
                else:
                    act = pending_entry["action"]
                    sig_ts = pending_entry["signal_time"]
                    if act == "BUY":
                        _open_long(open_px, current_row.name, signal_time=sig_ts)
                    else:
                        _open_short(open_px, current_row.name, signal_time=sig_ts)
                    pending_entry = None

            # 2) Evaluate strategy (exits can fire on the fill bar).
            # Always defer position.open in backtests — _open_long/_open_short own fills.
            ticker, action, price, exit_reason = self.strategy_manager.check_strategy(
                defer_position_open=True
            )
            mark_price = float(current_row["Close"]) if not pd.isna(current_row["Close"]) else price

            # 3) Execute based on action
            if action in ("BUY", "SELL") and not position_active:
                if self.fill_on_next_open:
                    # Arm levels already set by entry signal; fill next bar open.
                    pending_entry = {
                        "action": action,
                        "signal_time": current_row.name,
                    }
                elif action == "BUY":
                    _open_long(price, current_row.name)
                else:
                    _open_short(price, current_row.name)

            elif action == "SELL" and position_active and position_side == "LONG":
                proceeds = shares * price * (1.0 - self.commission)
                cash += proceeds
                old_shares = shares
                shares = 0.0
                position_active = False
                position_side = None
                exit_type = self._exit_trade_type("LONG", exit_reason)

                self.strategy_manager.position.close()
                equity = cash

                trades.append({
                    "type": exit_type,
                    "side": "LONG",
                    "timestamp": current_row.name,
                    "price": price,
                    "shares": old_shares,
                    "portfolio_value": equity,
                })
                LOGGER.debug(
                    f"[{current_row.name}] {exit_type} {old_shares:.4f} shares "
                    f"of {ticker} at {price:.2f}"
                )

            elif action == "BUY" and position_active and position_side == "SHORT":
                gross_pnl = shares * (short_entry_price - price)
                cash += gross_pnl * (1.0 - self.commission)
                old_shares = shares
                shares = 0.0
                short_entry_price = None
                position_active = False
                position_side = None
                exit_type = self._exit_trade_type("SHORT", exit_reason)

                self.strategy_manager.position.close()
                equity = cash

                trades.append({
                    "type": exit_type,
                    "side": "SHORT",
                    "timestamp": current_row.name,
                    "price": price,
                    "shares": old_shares,
                    "portfolio_value": equity,
                })
                LOGGER.debug(
                    f"[{current_row.name}] {exit_type} {old_shares:.4f} shares "
                    f"of {ticker} at {price:.2f}"
                )

            current_val = _portfolio_value(mark_price)
            portfolio_value_history.append({
                "timestamp": current_row.name,
                "portfolio_value": current_val,
                "close_price": mark_price,
            })

        if pending_entry is not None:
            LOGGER.warning("Dropping pending entry at end of data (never filled)")
            self.strategy_manager.position.close()
            pending_entry = None

        # Restore the full data to the data manager
        self.strategy_manager.data_manager.data = full_data

        # If a position is still open at the end, force close it to calculate final statistics
        if position_active:
            last_row = full_data.iloc[-1]
            last_price = last_row["Close"]

            if position_side == "LONG":
                cash += shares * last_price * (1.0 - self.commission)
                exit_type = "FORCE_SELL"
            else:
                gross_pnl = shares * (short_entry_price - last_price)
                cash += gross_pnl * (1.0 - self.commission)
                exit_type = "FORCE_COVER"

            old_shares = shares
            shares = 0.0
            position_active = False
            position_side = None
            self.strategy_manager.position.close()

            trades.append({
                "type": exit_type,
                "timestamp": last_row.name,
                "price": last_price,
                "shares": old_shares,
                "portfolio_value": cash,
            })
            LOGGER.info(
                f"[{last_row.name}] FORCE CLOSE open position of "
                f"{old_shares:.4f} shares at {last_price:.2f}"
            )

            if portfolio_value_history:
                portfolio_value_history[-1]["portfolio_value"] = cash

        # Calculate metrics
        history_df = pd.DataFrame(portfolio_value_history)
        if history_df.empty:
            LOGGER.warning("Backtest completed with no evaluation periods.")
            return {}

        final_value = cash
        total_pnl = final_value - self.initial_capital
        total_return_pct = (total_pnl / self.initial_capital) * 100

        # Group trades into pairs of Buy and Sell
        exit_types = (
            "SELL", "COVER", "FORCE_SELL", "FORCE_COVER",
            "EOD_SELL", "EOD_COVER", "SL_SELL", "SL_COVER", "TP_SELL", "TP_COVER",
        )
        trade_pairs = []
        open_trade = None
        for t in trades:
            if t["type"] in ("BUY", "SHORT"):
                open_trade = t
            elif t["type"] in exit_types and open_trade is not None:
                pnl = t["portfolio_value"] - open_trade["portfolio_value"]
                ret = (pnl / open_trade["portfolio_value"]) * 100
                trade_pairs.append({
                    "side": open_trade.get("side", "LONG"),
                    "buy_time": open_trade["timestamp"],
                    "buy_price": open_trade["price"],
                    "sell_time": t["timestamp"],
                    "sell_price": t["price"],
                    "shares": open_trade["shares"],
                    "pnl": pnl,
                    "return_pct": ret,
                    "exit_type": t["type"],
                })
                open_trade = None

        total_trades = len(trade_pairs)
        winning_trades = len([tp for tp in trade_pairs if tp["pnl"] > 0])
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate drawdown
        history_df["peak"] = history_df["portfolio_value"].cummax()
        history_df["drawdown"] = (history_df["portfolio_value"] - history_df["peak"]) / history_df["peak"]
        max_drawdown = history_df["drawdown"].min()
        max_drawdown_pct = max_drawdown * 100 if not pd.isna(max_drawdown) else 0.0

        summary = {
            "initial_capital": self.initial_capital,
            "final_value": final_value,
            "total_pnl": total_pnl,
            "total_return_pct": total_return_pct,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "max_drawdown_pct": max_drawdown_pct,
            "trade_pairs": trade_pairs,
            "portfolio_history": portfolio_value_history,
        }

        self.print_summary(summary)
        return summary

    def print_summary(self, summary):
        """Prints a clean summary of the backtesting results."""
        print("\n" + "="*70)
        print(f" BACKTESTING SUMMARY: {self.strategy_manager.name}")
        print("="*70)
        print(f"Initial Capital   : ${summary['initial_capital']:.2f}")
        print(f"Final Value       : ${summary['final_value']:.2f}")
        print(f"Net Profit/Loss   : ${summary['total_pnl']:.2f} ({summary['total_return_pct']:.2f}%)")
        print(f"Max Drawdown      : {summary['max_drawdown_pct']:.2f}%")
        print(f"Total Trades      : {summary['total_trades']}")
        if summary['total_trades'] > 0:
            print(f"  Winning Trades  : {summary['winning_trades']}")
            print(f"  Losing Trades   : {summary['losing_trades']}")
            print(f"  Win Rate        : {summary['win_rate']:.2f}%")
        print("="*70)
        if summary['trade_pairs']:
            print("\nTRADE LOG:")
            print(f"{'Entry Date':<20} | {'Side':<6} | {'Entry':<10} | {'Exit Date':<20} | {'Exit':<10} | {'PnL ($)':<10} | {'Return (%)':<10}")
            print("-"*95)
            for tp in summary['trade_pairs']:
                entry_time_str = str(tp['buy_time'])
                exit_time_str = str(tp['sell_time'])
                if len(entry_time_str) > 19:
                    entry_time_str = entry_time_str[:19]
                if len(exit_time_str) > 19:
                    exit_time_str = exit_time_str[:19]
                print(
                    f"{entry_time_str:<20} | {tp.get('side', 'LONG'):<6} | "
                    f"{tp['buy_price']:<10.2f} | {exit_time_str:<20} | "
                    f"{tp['sell_price']:<10.2f} | {tp['pnl']:<10.2f} | {tp['return_pct']:<10.2f}%"
                )
            print("="*95)
