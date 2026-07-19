import logging
import argparse
import pandas as pd
import yfinance as yf
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
        # Fetch custom historical data based on strategy configuration
        ticker = backtester.strategy_manager.position.ticker
        interval = backtester.strategy_manager.data_manager.interval
        print(f"Downloading custom historical data: {ticker} | Interval: {interval} | Period: {args.period}...")
        
        data = yf.download(ticker, interval=interval, period=args.period, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
            
        if data.empty:
            print("Failed to download custom data. Falling back to strategy default data.")
            data = None
        else:
            print(f"Successfully downloaded {len(data)} rows of data.")

    # Run the backtester
    backtester.run_backtest(data=data)

if __name__ == "__main__":
    main()
