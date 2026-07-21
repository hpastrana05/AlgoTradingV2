import logging
import argparse
from classes.backtesting import Backtesting

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s -> %(message)s'
)
# Suppress noisy library logs
logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

def main():
    parser = argparse.ArgumentParser(description="Backtest a trading strategy.")
    parser.add_argument(
        "--strategy", 
        type=str, 
        default="strategies/strat_2.json", 
        help="Path to the strategy configuration JSON file."
    )
    parser.add_argument(
        "--capital", 
        type=float, 
        default=10000.0, 
        help="Initial capital for backtesting."
    )
    parser.add_argument(
        "--commission", 
        type=float, 
        default=0.001, 
        help="Commission rate per trade (e.g. 0.001 for 0.1%)."
    )
    parser.add_argument(
        "--period", 
        type=str, 
        default=None, 
        help="Custom historical data period (e.g., '5d', '1mo', '1y'). If not provided, uses the strategy's default."
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Override Yahoo ticker for this backtest (e.g. AAPL, EURUSD=X)."
    )
    parser.add_argument(
        "--interval",
        type=str,
        default=None,
        help="Override candle interval for this backtest (e.g. 1h, 4h, 1d)."
    )
    
    args = parser.parse_args()

    ticker = (args.ticker or "").strip() or None
    period = (args.period or "").strip() or None
    interval = (args.interval or "").strip() or None

    print(f"Loading strategy from: {args.strategy}")
    if ticker:
        print(f"Ticker override: {ticker}")
    if period:
        print(f"Period override: {period}")
    if interval:
        print(f"Interval override: {interval}")

    # Overrides are applied before the first Yahoo download.
    backtester = Backtesting(
        strategy_path=args.strategy,
        initial_capital=args.capital,
        commission=args.commission,
        ticker=ticker,
        period=period,
        interval=interval,
    )

    dm = backtester.strategy_manager.data_manager
    if dm.data is None or dm.data.empty:
        print(
            f"Failed to download data for {dm.ticker} "
            f"(interval={dm.interval}, period={dm.period}). Aborting."
        )
        return

    print(f"Using {len(dm.data)} rows: {dm.ticker} | {dm.interval} | {dm.period}")
    backtester.run_backtest()

if __name__ == "__main__":
    main()
