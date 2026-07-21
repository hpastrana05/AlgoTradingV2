import logging
import threading
import traceback
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional

import config
from classes.trading_engine import TradingEngine

LOGGER = logging.getLogger("LiveRunner")


class _RingLogHandler(logging.Handler):
    """Keeps recent log lines for the Live Trading UI."""

    def __init__(self, buffer: Deque[dict], capacity: int = 200):
        super().__init__(level=logging.INFO)
        self.buffer = buffer
        self.capacity = capacity
        self.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s -> %(message)s", "%H:%M:%S")
        )

    def emit(self, record):
        try:
            line = self.format(record)
            self.buffer.append(
                {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "line": line,
                }
            )
            while len(self.buffer) > self.capacity:
                self.buffer.popleft()
        except Exception:
            self.handleError(record)


class LiveRunner:
    """
    Runs at most one TradingEngine in a background thread.
    Used by the FastAPI Live Trading panel on the Raspberry Pi.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._engine: Optional[TradingEngine] = None
        self._log_buffer: Deque[dict] = deque(maxlen=200)
        self._log_handler = _RingLogHandler(self._log_buffer)
        self._status: Dict = {
            "running": False,
            "strategy_file": None,
            "strategy_name": None,
            "ticker": None,
            "interval": None,
            "mode": config.get_trading_mode()["mode"],
            "is_demo": config.get_trading_mode()["is_demo"],
            "started_at": None,
            "stopped_at": None,
            "last_error": None,
            "last_tick_at": None,
        }

    def _attach_logs(self):
        for name in (
            "LiveRunner",
            "TradingEngine",
            "StrategyManager",
            "BrokerSyncManager",
            "DataManager",
            "Signals",
        ):
            logging.getLogger(name).addHandler(self._log_handler)

    def _detach_logs(self):
        for name in (
            "LiveRunner",
            "TradingEngine",
            "StrategyManager",
            "BrokerSyncManager",
            "DataManager",
            "Signals",
        ):
            logger = logging.getLogger(name)
            if self._log_handler in logger.handlers:
                logger.removeHandler(self._log_handler)

    def status(self) -> dict:
        with self._lock:
            return self._status_unlocked()

    def _status_unlocked(self) -> dict:
        mode = config.get_trading_mode()
        payload = {
            **self._status,
            "mode": mode["mode"],
            "is_demo": mode["is_demo"],
            "has_credentials": mode["has_credentials"],
            "api_link": mode["api_link"],
            "thread_alive": bool(self._thread and self._thread.is_alive()),
        }
        if payload["running"] and not payload["thread_alive"]:
            payload["running"] = False
            if not payload["last_error"]:
                payload["last_error"] = "Engine thread exited unexpectedly"
        return payload

    def logs(self, limit: int = 100) -> List[dict]:
        items = list(self._log_buffer)
        if limit > 0:
            return items[-limit:]
        return items

    def start(self, strategy_path: str, is_demo: bool) -> dict:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError(
                    "A strategy is already running. Stop it before starting another."
                )

            mode_info = config.set_trading_mode(is_demo, require_credentials=True)
            self._stop_event.clear()
            self._log_buffer.clear()
            self._attach_logs()

            try:
                engine = TradingEngine(strategy_path)
            except Exception as e:
                self._detach_logs()
                raise RuntimeError(f"Failed to load strategy: {e}") from e

            sm = engine.strategy_manager
            self._engine = engine
            self._status.update(
                {
                    "running": True,
                    "strategy_file": strategy_path.split("\\")[-1].split("/")[-1],
                    "strategy_name": sm.name,
                    "ticker": sm.position.ticker,
                    "ticker_api": sm.position.ticker_api,
                    "interval": sm.data_manager.interval,
                    "mode": mode_info["mode"],
                    "is_demo": mode_info["is_demo"],
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                    "stopped_at": None,
                    "last_error": None,
                    "last_tick_at": None,
                }
            )

            self._thread = threading.Thread(
                target=self._run_loop,
                name="LiveTradingEngine",
                daemon=True,
            )
            self._thread.start()
            api_label = sm.position.ticker_api or "None"
            LOGGER.info(
                f"Started live engine: {sm.name} | data={sm.position.ticker} | "
                f"api={api_label} | mode={mode_info['mode']}"
            )
            if sm.position.ticker_api is None:
                LOGGER.warning(
                    "ticker_API is None — signals will run on Yahoo data but "
                    "no Trading212 orders will be placed."
                )
            return self._status_unlocked()

    def stop(self) -> dict:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                self._status["running"] = False
                self._status["stopped_at"] = datetime.now().isoformat(timespec="seconds")
                return self._status_unlocked()

            LOGGER.info("Stop requested for live engine...")
            self._stop_event.set()
            thread = self._thread

        thread.join(timeout=15)

        with self._lock:
            self._status["running"] = False
            self._status["stopped_at"] = datetime.now().isoformat(timespec="seconds")
            if thread.is_alive():
                self._status["last_error"] = "Engine did not stop within timeout"
                LOGGER.warning(self._status["last_error"])
            else:
                LOGGER.info("Live engine stopped.")
            self._detach_logs()
            return self._status_unlocked()

    def _run_loop(self):
        try:
            assert self._engine is not None
            self._engine.run(stop_event=self._stop_event)
        except Exception as e:
            LOGGER.error(f"Live engine crashed: {e}")
            LOGGER.debug(traceback.format_exc())
            with self._lock:
                self._status["last_error"] = str(e)
                self._status["running"] = False
                self._status["stopped_at"] = datetime.now().isoformat(timespec="seconds")
        finally:
            with self._lock:
                self._status["running"] = False
                if not self._status.get("stopped_at"):
                    self._status["stopped_at"] = datetime.now().isoformat(timespec="seconds")


# Process-wide singleton for the UI
live_runner = LiveRunner()
