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
    
    args = parser.parse_args()

    print(f"Loading strategy from: {args.strategy}")
    backtester = Backtesting(
        strategy_path=args.strategy, 
        initial_capital=args.capital, 
        commission=args.commission
    )

    data = None
    if args.period:
        # Fetch via DataManager so resampled intervals (e.g. 4h) work
        dm = backtester.strategy_manager.data_manager
        print(
            f"Downloading custom historical data: {dm.ticker} | "
            f"Interval: {dm.interval} | Period: {args.period}..."
        )
        data = dm.fetch_data(dm.ticker, dm.interval, args.period)
        if data.empty:
            print("Failed to download custom data. Falling back to strategy default data.")
            data = None
        else:
            print(f"Successfully downloaded {len(data)} rows of data.")

    # Run the backtester
    backtester.run_backtest(data=data)

if __name__ == "__main__":
    main()
