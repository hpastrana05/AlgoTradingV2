import os
import sys
import logging
import inspect
import json
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
from classes.live_runner import live_runner
import config
import signals.entry_exit_signals as entry_exit_signals

# Setup logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("FrontendAPI")

app = FastAPI(title="AlgoTrading V2 Control Center")

STRATEGIES_DIR = os.path.join(parent_dir, "strategies")

# Not exposed in the strategy builder UI (handled internally by the engine).
HIDDEN_SIGNAL_PARAMS = {"session_tz"}


def _sanitize_rule(rule: dict) -> dict:
    """Remove deprecated/internal keys from entry/exit rule trees."""
    if not rule:
        return rule

    cleaned = dict(rule)
    cleaned.pop("session_tz", None)

    if cleaned.get("type") in ("AND", "OR") and "signals" in cleaned:
        cleaned["signals"] = [
            _sanitize_rule(s) for s in cleaned["signals"] if s is not None
        ]
    else:
        for key in list(cleaned.keys()):
            if key in HIDDEN_SIGNAL_PARAMS:
                cleaned.pop(key, None)

    return cleaned


def _ensure_strategies_dir():
    if not os.path.exists(STRATEGIES_DIR):
        os.makedirs(STRATEGIES_DIR)


def _sanitize_file_name(name: str) -> str:
    clean = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in name.lower()])
    return f"{clean}.json"


def _strategy_to_dict(strategy: "StrategyConfig") -> dict:
    return {
        "name": strategy.name,
        "ticker_API": strategy.ticker_API,
        "ticker_data": strategy.ticker_data,
        "interval": strategy.interval,
        "period": strategy.period,
        "action": strategy.action,
        "entry_rule": _sanitize_rule(strategy.entry_rule),
        "exit_rule": _sanitize_rule(strategy.exit_rule),
    }


# Dynamic Signal Inspector Helper
def get_signal_metadata() -> List[Dict[str, Any]]:
    signals_list = []
    for name, obj in inspect.getmembers(entry_exit_signals, inspect.isfunction):
        if obj.__module__ == entry_exit_signals.__name__ and not name.startswith("_"):
            sig = inspect.signature(obj)
            params = []
            for param_name, param in sig.parameters.items():
                if param_name in ('data', 'position') or param_name in HIDDEN_SIGNAL_PARAMS:
                    continue
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                
                default_val = param.default if param.default is not inspect.Parameter.empty else None
                input_type = "number"
                description = f"Value for {param_name}"
                required = default_val is None
                
                if param_name == "values":
                    input_type = "array"
                    description = "Fast, Slow, Signal values (comma-separated, e.g. 12,26,9)"
                elif param_name == "percentage":
                    description = "Percentage value (e.g. 2.5 for 2.5%)"
                elif param_name == "loss_units":
                    description = "Risk units in the ratio (e.g. 1 for 1:3 risk-reward)"
                elif param_name == "win_units":
                    description = "Reward units in the ratio (e.g. 3 for 1:3 risk-reward)"
                elif param_name in ("session_hour", "session_minute"):
                    description = f"Anchor candle time ({param_name}), Europe/Madrid"
                elif param_name in ("entry_deadline_hour", "entry_deadline_minute"):
                    description = f"Last entry time ({param_name}), Europe/Madrid"
                elif param_name in (
                    "fast", "slow", "ema_value", "sma_value", "ma_value",
                    "ema1", "ema2", "rsi_value", "lower", "upper",
                ):
                    description = f"Indicator period or limit for {param_name}"
                elif param_name == "breakout_buffer_pct":
                    description = "Extra % of the anchor candle range required beyond high/low for breakout"
                elif param_name == "retest_tolerance_pct":
                    description = "% of the anchor candle range allowed when retesting the broken level"
                elif param_name in ("flatten_hour", "flatten_minute"):
                    description = f"Same-day flatten time ({param_name}), Europe/Madrid"
                
                params.append({
                    "name": param_name,
                    "type": input_type,
                    "default": default_val,
                    "description": description,
                    "required": required,
                })
            
            signals_list.append({
                "name": name,
                "parameters": params,
                "doc": obj.__doc__ or "No description available."
            })
    return signals_list

# API Request Models
class StrategyConfig(BaseModel):
    name: str
    ticker_API: str
    ticker_data: str
    interval: str
    period: str
    action: str = "BUY"
    entry_rule: Dict[str, Any]
    exit_rule: Dict[str, Any]

class BacktestRequest(BaseModel):
    strategy_file: str
    capital: float = Field(default=10000.0, ge=1.0)
    commission: float = Field(default=0.001, ge=0.0, le=1.0)
    risk_pct: float = Field(default=1.0, ge=0.01, le=100.0)
    period: Optional[str] = None
    ticker: Optional[str] = None
    interval: Optional[str] = None


class LiveStartRequest(BaseModel):
    strategy_file: str
    is_demo: bool = True

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
    _ensure_strategies_dir()
        
    strategies = []
    for file_name in os.listdir(STRATEGIES_DIR):
        if file_name.endswith(".json"):
            file_path = os.path.join(STRATEGIES_DIR, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    strategies.append({
                        "file_name": file_name,
                        "config": config,
                    })
            except Exception as e:
                LOGGER.warning(f"Failed to load strategy file {file_name}: {e}")
    return strategies

@app.post("/api/strategies")
def api_save_strategy(strategy: StrategyConfig):
    """Saves a new strategy to the strategies/ directory."""
    _ensure_strategies_dir()
         
    file_name = _sanitize_file_name(strategy.name)
    file_path = os.path.join(STRATEGIES_DIR, file_name)

    if os.path.exists(file_path):
        raise HTTPException(
            status_code=409,
            detail=f"Strategy file '{file_name}' already exists. Edit it from Saved Strategies, or choose another name.",
        )
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(_strategy_to_dict(strategy), f, indent=4)
        return {"status": "success", "file_name": file_name}
    except Exception as e:
        LOGGER.error(f"Error saving strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/strategies/{file_name}")
def api_update_strategy(file_name: str, strategy: StrategyConfig):
    """Updates an existing strategy file in place."""
    _ensure_strategies_dir()

    if not file_name.endswith(".json") or "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="Invalid strategy file name")

    file_path = os.path.join(STRATEGIES_DIR, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Strategy file not found")

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(_strategy_to_dict(strategy), f, indent=4)
        return {"status": "success", "file_name": file_name}
    except Exception as e:
        LOGGER.error(f"Error updating strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backtest")
def api_run_backtest(req: BacktestRequest):
    """Runs a backtest on the specified strategy file with parameters."""
    strat_path = os.path.join(STRATEGIES_DIR, req.strategy_file)
    
    if not os.path.exists(strat_path):
        raise HTTPException(status_code=404, detail="Strategy file not found")
        
    try:
        ticker_override = (req.ticker or "").strip() or None
        period_override = (req.period or "").strip() or None
        interval_override = (req.interval or "").strip() or None

        if ticker_override:
            LOGGER.info(f"Ticker override: {ticker_override}")
        if period_override:
            LOGGER.info(f"Period override: {period_override}")
        if interval_override:
            LOGGER.info(f"Interval override: {interval_override}")

        # Apply overrides before the first Yahoo download (no wasted fetch).
        backtester = Backtesting(
            strategy_path=strat_path,
            initial_capital=req.capital,
            commission=req.commission,
            risk_pct=req.risk_pct / 100.0,
            ticker=ticker_override,
            period=period_override,
            interval=interval_override,
        )
        sm = backtester.strategy_manager
        dm = sm.data_manager
        used_ticker = dm.ticker
        used_period = dm.period

        if dm.data is None or dm.data.empty:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No data for ticker '{used_ticker}' "
                    f"(interval={dm.interval}, period={used_period})"
                ),
            )

        results = backtester.run_backtest()

        if not results:
             raise HTTPException(status_code=500, detail="Backtest completed with no results")

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
            "strategy_name": results["strategy_name"] if "strategy_name" in results else sm.name,
            "ticker": used_ticker,
            "interval": dm.interval,
            "period": used_period,
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
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.exception("Backtest execution failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/live/status")
def api_live_status():
    """Current live engine status and trading mode."""
    return live_runner.status()


@app.get("/api/live/logs")
def api_live_logs(limit: int = 100):
    """Recent live engine log lines."""
    return {"logs": live_runner.logs(limit=limit)}


@app.post("/api/live/start")
def api_live_start(req: LiveStartRequest):
    """Start the trading engine for a strategy in demo or live mode."""
    strat_path = os.path.join(STRATEGIES_DIR, req.strategy_file)
    if not os.path.exists(strat_path):
        raise HTTPException(status_code=404, detail="Strategy file not found")

    if not req.is_demo:
        LOGGER.warning("LIVE mode start requested — real money orders may be placed.")

    try:
        return live_runner.start(strat_path, is_demo=req.is_demo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        LOGGER.exception("Failed to start live engine")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/live/stop")
def api_live_stop():
    """Stop the running trading engine."""
    try:
        return live_runner.stop()
    except Exception as e:
        LOGGER.exception("Failed to stop live engine")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/live/mode")
def api_live_mode():
    """Return current Trading212 mode without starting the engine."""
    return config.get_trading_mode()


# Setup Static files mounting
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))
