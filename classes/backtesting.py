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
    ):
        self.strategy_manager = StrategyManager.from_json(
            strategy_path,
            ticker=ticker,
            period=period,
            interval=interval,
        )
        self.initial_capital = initial_capital
        self.commission = commission

    def run_backtest(self, data=None):
        """
        Runs the backtest on the provided data or the data fetched by the data manager.
        If data is a pandas DataFrame, we update the data manager's data.
        """
        if data is not None:
            self.strategy_manager.data_manager.data = data.copy()

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
        entry_capital = 0.0
        short_entry_price = None
        trades = []
        portfolio_value_history = []

        def _portfolio_value(market_price):
            if not position_active:
                return cash
            if position_side == "LONG":
                return shares * market_price
            return entry_capital + shares * (short_entry_price - market_price)

        LOGGER.info(f"Starting backtest on {len(full_data)} data rows with initial capital: {self.initial_capital}")

        for i in range(len(full_data)):
            # Slice the data so the strategy only sees up to index i (inclusive)
            # This simulates real-time data arriving bar-by-bar and prevents look-ahead bias.
            slice_df = full_data.iloc[:i+1]
            
            current_row = slice_df.iloc[-1]
            if pd.isna(current_row["Close"]):
                continue

            # Update the strategy manager's view of the data
            self.strategy_manager.data_manager.data = slice_df

            # Evaluate strategy signals for this step
            ticker, action, price = self.strategy_manager.check_strategy()

            # Execute trade simulation based on strategy action
            if action == "BUY" and not position_active:
                entry_capital = cash
                buy_cost = cash * (1.0 - self.commission)
                shares = buy_cost / price
                cash = 0.0
                position_active = True
                position_side = "LONG"

                trades.append({
                    "type": "BUY",
                    "side": "LONG",
                    "timestamp": current_row.name,
                    "price": price,
                    "shares": shares,
                    "portfolio_value": entry_capital,
                })
                LOGGER.debug(f"[{current_row.name}] BUY {shares:.4f} shares of {ticker} at {price:.2f}")

            elif action == "SELL" and not position_active:
                entry_capital = cash
                shares = cash * (1.0 - self.commission) / price
                short_entry_price = price
                position_active = True
                position_side = "SHORT"

                trades.append({
                    "type": "SHORT",
                    "side": "SHORT",
                    "timestamp": current_row.name,
                    "price": price,
                    "shares": shares,
                    "portfolio_value": entry_capital,
                })
                LOGGER.debug(f"[{current_row.name}] SHORT {shares:.4f} shares of {ticker} at {price:.2f}")

            elif action == "SELL" and position_active and position_side == "LONG":
                cash = shares * price * (1.0 - self.commission)
                old_shares = shares
                shares = 0.0
                position_active = False
                position_side = None

                self.strategy_manager.position.close()

                trades.append({
                    "type": "SELL",
                    "side": "LONG",
                    "timestamp": current_row.name,
                    "price": price,
                    "shares": old_shares,
                    "portfolio_value": cash,
                })
                LOGGER.debug(f"[{current_row.name}] SELL {old_shares:.4f} shares of {ticker} at {price:.2f}")

            elif action == "BUY" and position_active and position_side == "SHORT":
                gross_pnl = shares * (short_entry_price - price)
                cash = entry_capital + gross_pnl * (1.0 - self.commission)
                old_shares = shares
                shares = 0.0
                short_entry_price = None
                position_active = False
                position_side = None

                self.strategy_manager.position.close()

                trades.append({
                    "type": "COVER",
                    "side": "SHORT",
                    "timestamp": current_row.name,
                    "price": price,
                    "shares": old_shares,
                    "portfolio_value": cash,
                })
                LOGGER.debug(f"[{current_row.name}] COVER {old_shares:.4f} shares of {ticker} at {price:.2f}")

            current_val = _portfolio_value(price)
            portfolio_value_history.append({
                "timestamp": current_row.name,
                "portfolio_value": current_val,
                "close_price": price
            })

        # Restore the full data to the data manager
        self.strategy_manager.data_manager.data = full_data

        # If a position is still open at the end, force close it to calculate final statistics
        if position_active:
            last_row = full_data.iloc[-1]
            last_price = last_row["Close"]

            if position_side == "LONG":
                cash = shares * last_price * (1.0 - self.commission)
                exit_type = "FORCE_SELL"
            else:
                gross_pnl = shares * (short_entry_price - last_price)
                cash = entry_capital + gross_pnl * (1.0 - self.commission)
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
        trade_pairs = []
        open_trade = None
        for t in trades:
            if t["type"] in ("BUY", "SHORT"):
                open_trade = t
            elif t["type"] in ("SELL", "COVER", "FORCE_SELL", "FORCE_COVER") and open_trade is not None:
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
                    "exit_type": t["type"]
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
            "portfolio_history": portfolio_value_history
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