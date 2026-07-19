import os
import sys
import logging
import inspect
import json
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional

# Ensure parent directory is in sys.path to import classes and signals
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from classes.backtesting import Backtesting
import signals.entry_exit_signals as entry_exit_signals

# Setup logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("FrontendAPI")

app = FastAPI(title="AlgoTrading V2 Control Center")

# Dynamic Signal Inspector Helper
def get_signal_metadata() -> List[Dict[str, Any]]:
    signals_list = []
    for name, obj in inspect.getmembers(entry_exit_signals, inspect.isfunction):
        if obj.__module__ == entry_exit_signals.__name__:
            sig = inspect.signature(obj)
            params = []
            for param_name, param in sig.parameters.items():
                if param_name in ('data', 'position') or param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                
                # Determine standard defaults and type hints
                default_val = param.default if param.default is not inspect.Parameter.empty else None
                # Custom parameter metadata mapping for frontend UI rendering
                input_type = "number"
                description = f"Value for {param_name}"
                
                if param_name == "values":
                    input_type = "array"
                    description = "Fast, Slow, Signal values (comma-separated, e.g. 12,26,9)"
                elif param_name == "percentage":
                    description = "Percentage value (e.g. 2.5 for 2.5%)"
                elif param_name in ("fast", "slow", "ema_value", "ema1", "ema2", "rsi_value", "lower", "upper"):
                    description = f"Indicator period or limit for {param_name}"
                
                params.append({
                    "name": param_name,
                    "type": input_type,
                    "default": default_val,
                    "description": description
                })
            
            signals_list.append({
                "name": name,
                "parameters": params,
                "doc": obj.__doc__ or "No description available."
            })
    return signals_list

# API Request Models
class RuleConfig(BaseModel):
    type: str
    signals: Optional[List[Dict[str, Any]]] = None
    # For individual rules, we allow arbitrary extra fields
    # to support the dynamic signals fields
    class Config:
        extra = "allow"

class StrategyConfig(BaseModel):
    name: str
    ticker_API: str
    ticker_data: str
    indicators: Dict[str, List[Any]]
    interval: str
    period: str
    action: str = "BUY"
    entry_rule: Dict[str, Any]
    exit_rule: Dict[str, Any]

class BacktestRequest(BaseModel):
    strategy_file: str
    capital: float = Field(default=10000.0, ge=1.0)
    commission: float = Field(default=0.001, ge=0.0, le=1.0)
    period: Optional[str] = None

# Endpoints
@app.get("/api/signals")
def api_get_signals():
    """Returns all available entry-exit signal functions and their parameters."""
    try:
        return get_signal_metadata()
    except Exception as e:
        LOGGER.error(f"Error inspecting signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategies")
def api_get_strategies():
    """Scans strategies directory and returns strategy configurations."""
    strategies_dir = os.path.join(parent_dir, "strategies")
    if not os.path.exists(strategies_dir):
        os.makedirs(strategies_dir)
        
    strategies = []
    for file_name in os.listdir(strategies_dir):
        if file_name.endswith(".json"):
            file_path = os.path.join(strategies_dir, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    strategies.append({
                        "file_name": file_name,
                        "config": config
                    })
            except Exception as e:
                LOGGER.warning(f"Failed to load strategy file {file_name}: {e}")
    return strategies

@app.post("/api/strategies")
def api_save_strategy(strategy: StrategyConfig):
    """Saves a new strategy to the strategies/ directory."""
    strategies_dir = os.path.join(parent_dir, "strategies")
    if not os.path.exists(strategies_dir):
         os.makedirs(strategies_dir)
         
    # Clean up name for file name
    clean_name = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in strategy.name.lower()])
    file_name = f"{clean_name}.json"
    file_path = os.path.join(strategies_dir, file_name)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(strategy.dict(), f, indent=4)
        return {"status": "success", "file_name": file_name}
    except Exception as e:
        LOGGER.error(f"Error saving strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backtest")
def api_run_backtest(req: BacktestRequest):
    """Runs a backtest on the specified strategy file with parameters."""
    strategies_dir = os.path.join(parent_dir, "strategies")
    strat_path = os.path.join(strategies_dir, req.strategy_file)
    
    if not os.path.exists(strat_path):
        raise HTTPException(status_code=404, detail="Strategy file not found")
        
    try:
        # Initialize backtester
        backtester = Backtesting(
            strategy_path=strat_path,
            initial_capital=req.capital,
            commission=req.commission
        )
        
        # Determine data period
        data = None
        if req.period:
            ticker = backtester.strategy_manager.position.ticker
            interval = backtester.strategy_manager.data_manager.interval
            LOGGER.info(f"Downloading custom backtest data: {ticker} | {interval} | {req.period}")
            
            data = yf.download(ticker, interval=interval, period=req.period, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)
            
            if data.empty:
                LOGGER.warning("Downloaded custom data was empty, falling back to config default")
                data = None
                
        # Run Backtest
        results = backtester.run_backtest(data=data)
        
        if not results:
             raise HTTPException(status_code=500, detail="Backtest completed with no results")
             
        # Format timestamps to string to make JSON serializable
        formatted_trade_pairs = []
        for tp in results["trade_pairs"]:
            formatted_trade_pairs.append({
                **tp,
                "buy_time": str(tp["buy_time"]),
                "sell_time": str(tp["sell_time"])
            })
            
        formatted_history = []
        for h in results["portfolio_history"]:
            formatted_history.append({
                "timestamp": str(h["timestamp"]),
                "portfolio_value": float(h["portfolio_value"]),
                "close_price": float(h["close_price"])
            })
            
        return {
            "strategy_name": results["strategy_name"] if "strategy_name" in results else backtester.strategy_manager.name,
            "initial_capital": results["initial_capital"],
            "final_value": results["final_value"],
            "total_pnl": results["total_pnl"],
            "total_return_pct": results["total_return_pct"],
            "total_trades": results["total_trades"],
            "winning_trades": results["winning_trades"],
            "losing_trades": results["losing_trades"],
            "win_rate": results["win_rate"],
            "max_drawdown_pct": results["max_drawdown_pct"],
            "trade_pairs": formatted_trade_pairs,
            "portfolio_history": formatted_history
        }
        
    except Exception as e:
        LOGGER.exception("Backtest execution failed")
        raise HTTPException(status_code=500, detail=str(e))

# Setup Static files mounting
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))
