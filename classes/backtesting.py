import logging
import pandas as pd
import numpy as np
from .strategy_manager import StrategyManager

LOGGER = logging.getLogger("Backtesting")


class Backtesting:

    def __init__(self, strategy_path, initial_capital=10000.0, commission=0.0):
        self.strategy_manager = StrategyManager.from_json(strategy_path)
        self.initial_capital = initial_capital
        self.commission = commission

    def run_backtest(self, data=None):
        """
        Runs the backtest on the provided data or the data fetched by the data manager.
        If data is a pandas DataFrame, we update the data manager's data and update indicators.
        """
        # If external data is provided, set it and calculate indicators
        if data is not None:
            # We copy data to avoid mutating original
            self.strategy_manager.data_manager.data = data.copy()
            self.strategy_manager.data_manager.update_indicators()

        # Get full data with indicators calculated
        full_data = self.strategy_manager.data_manager.data
        if full_data is None or full_data.empty:
            LOGGER.error("No historical data available for backtesting.")
            return None

        # Reset position in strategy manager
        self.strategy_manager.position.entry_price = None

        cash = self.initial_capital
        shares = 0.0
        position_active = False
        trades = []
        portfolio_value_history = []

        LOGGER.info(f"Starting backtest on {len(full_data)} data rows with initial capital: {self.initial_capital}")

        for i in range(len(full_data)):
            # Slice the data so the strategy only sees up to index i (inclusive)
            # This simulates real-time data arriving bar-by-bar and prevents look-ahead bias.
            slice_df = full_data.iloc[:i+1]
            
            # Skip rows where there are NaNs in indicators (warming up period)
            current_row = slice_df.iloc[-1]
            if current_row.isna().any():
                continue

            # Update the strategy manager's view of the data
            self.strategy_manager.data_manager.data = slice_df

            # Evaluate strategy signals for this step
            ticker, action, price = self.strategy_manager.check_strategy()

            # Execute trade simulation based on strategy action
            if action == "BUY" and not position_active:
                # Buy position
                buy_cost = cash * (1.0 - self.commission)
                shares = buy_cost / price
                portfolio_val_before = cash
                cash = 0.0
                position_active = True
                
                # Make sure the strategy manager knows the entry price
                self.strategy_manager.position.entry_price = price
                
                trades.append({
                    "type": "BUY",
                    "timestamp": current_row.name,
                    "price": price,
                    "shares": shares,
                    "cash": cash,
                    "portfolio_value": portfolio_val_before
                })
                LOGGER.debug(f"[{current_row.name}] BUY {shares:.4f} shares of {ticker} at {price:.2f}")

            elif action == "SELL" and position_active:
                # Sell position
                sell_revenue = shares * price * (1.0 - self.commission)
                cash = sell_revenue
                old_shares = shares
                shares = 0.0
                position_active = False
                
                # Reset entry price in strategy manager
                self.strategy_manager.position.entry_price = None
                
                trades.append({
                    "type": "SELL",
                    "timestamp": current_row.name,
                    "price": price,
                    "shares": old_shares,
                    "cash": cash,
                    "portfolio_value": sell_revenue
                })
                LOGGER.debug(f"[{current_row.name}] SELL {old_shares:.4f} shares of {ticker} at {price:.2f}")

            # Keep track of portfolio value at each step
            current_val = cash + (shares * price if position_active else 0.0)
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
            sell_revenue = shares * last_price * (1.0 - self.commission)
            cash = sell_revenue
            old_shares = shares
            shares = 0.0
            position_active = False
            self.strategy_manager.position.entry_price = None
            
            trades.append({
                "type": "FORCE_SELL",
                "timestamp": last_row.name,
                "price": last_price,
                "shares": old_shares,
                "cash": cash,
                "portfolio_value": sell_revenue
            })
            LOGGER.info(f"[{last_row.name}] FORCE CLOSE open position of {old_shares:.4f} shares at {last_price:.2f}")
            
            # Update the last history entry
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
        buy_trade = None
        for t in trades:
            if t["type"] == "BUY":
                buy_trade = t
            elif t["type"] in ["SELL", "FORCE_SELL"] and buy_trade is not None:
                pnl = t["portfolio_value"] - buy_trade["portfolio_value"]
                ret = (pnl / buy_trade["portfolio_value"]) * 100
                trade_pairs.append({
                    "buy_time": buy_trade["timestamp"],
                    "buy_price": buy_trade["price"],
                    "sell_time": t["timestamp"],
                    "sell_price": t["price"],
                    "shares": buy_trade["shares"],
                    "pnl": pnl,
                    "return_pct": ret,
                    "exit_type": t["type"]
                })
                buy_trade = None

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
            print(f"{'Buy Date':<20} | {'Buy Price':<10} | {'Sell Date':<20} | {'Sell Price':<10} | {'PnL ($)':<10} | {'Return (%)':<10}")
            print("-"*85)
            for tp in summary['trade_pairs']:
                buy_time_str = str(tp['buy_time'])
                sell_time_str = str(tp['sell_time'])
                # Shorten date format if too long
                if len(buy_time_str) > 19: buy_time_str = buy_time_str[:19]
                if len(sell_time_str) > 19: sell_time_str = sell_time_str[:19]
                print(f"{buy_time_str:<20} | {tp['buy_price']:<10.2f} | {sell_time_str:<20} | {tp['sell_price']:<10.2f} | {tp['pnl']:<10.2f} | {tp['return_pct']:<10.2f}%")
            print("="*85)