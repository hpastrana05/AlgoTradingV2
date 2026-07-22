import logging
import os
import threading
import time
import traceback
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional

from classes.alert_store import load_alerts, mark_triggered
from classes.data_manager import DataManager
from classes.strategy_manager import StrategyManager
from classes.telegram_notifier import send_telegram_message

LOGGER = logging.getLogger("AlertRunner")

STRATEGIES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "strategies",
)


class _RingLogHandler(logging.Handler):
    def __init__(self, buffer: Deque[dict], capacity: int = 200):
        super().__init__(level=logging.INFO)
        self.buffer = buffer
        self.capacity = capacity
        self.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s -> %(message)s", "%H:%M:%S")
        )

    def emit(self, record):
        try:
            self.buffer.append(
                {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "line": self.format(record),
                }
            )
            while len(self.buffer) > self.capacity:
                self.buffer.popleft()
        except Exception:
            self.handleError(record)


class AlertRunner:
    """
    Background monitor: evaluates enabled alerts and sends Telegram messages.
    Strategy alerts watch entry/exit signals (no broker orders).
    Price alerts watch Yahoo prices against a threshold.
    """

    def __init__(self, poll_seconds: int = 60):
        self.poll_seconds = max(15, int(poll_seconds))
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._log_buffer: Deque[dict] = deque(maxlen=200)
        self._log_handler = _RingLogHandler(self._log_buffer)
        # strategy_file -> StrategyManager (notify-only)
        self._strategy_managers: Dict[str, StrategyManager] = {}
        # alert_id -> last known price (for edge detection)
        self._price_state: Dict[str, float] = {}
        self._status: Dict = {
            "running": False,
            "started_at": None,
            "stopped_at": None,
            "last_error": None,
            "last_tick_at": None,
            "alerts_checked": 0,
            "messages_sent": 0,
            "poll_seconds": self.poll_seconds,
        }

    def _attach_logs(self):
        for name in ("AlertRunner", "TelegramNotifier", "DataManager", "StrategyManager", "Signals"):
            logging.getLogger(name).addHandler(self._log_handler)

    def _detach_logs(self):
        for name in ("AlertRunner", "TelegramNotifier", "DataManager", "StrategyManager", "Signals"):
            logger = logging.getLogger(name)
            if self._log_handler in logger.handlers:
                logger.removeHandler(self._log_handler)

    def status(self) -> dict:
        with self._lock:
            payload = {
                **self._status,
                "thread_alive": bool(self._thread and self._thread.is_alive()),
                "active_strategy_monitors": len(self._strategy_managers),
                "enabled_alerts": sum(1 for a in load_alerts() if a.get("enabled")),
                "total_alerts": len(load_alerts()),
            }
            if payload["running"] and not payload["thread_alive"]:
                payload["running"] = False
                if not payload["last_error"]:
                    payload["last_error"] = "Alert monitor thread exited unexpectedly"
            return payload

    def logs(self, limit: int = 100) -> List[dict]:
        items = list(self._log_buffer)
        return items[-limit:] if limit > 0 else items

    def start(self) -> dict:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("Alert monitor is already running.")

            self._stop_event.clear()
            self._log_buffer.clear()
            self._strategy_managers.clear()
            self._price_state.clear()
            self._attach_logs()
            self._status.update(
                {
                    "running": True,
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                    "stopped_at": None,
                    "last_error": None,
                    "last_tick_at": None,
                    "alerts_checked": 0,
                    "messages_sent": 0,
                    "poll_seconds": self.poll_seconds,
                }
            )
            self._thread = threading.Thread(
                target=self._run_loop,
                name="AlertRunner",
                daemon=True,
            )
            self._thread.start()
            LOGGER.info(f"Alert monitor started (poll every {self.poll_seconds}s).")
            return self.status()

    def stop(self) -> dict:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                self._status["running"] = False
                self._status["stopped_at"] = datetime.now().isoformat(timespec="seconds")
                return self.status()
            LOGGER.info("Stop requested for alert monitor...")
            self._stop_event.set()
            thread = self._thread

        thread.join(timeout=20)

        with self._lock:
            self._status["running"] = False
            self._status["stopped_at"] = datetime.now().isoformat(timespec="seconds")
            self._strategy_managers.clear()
            if thread.is_alive():
                self._status["last_error"] = "Alert monitor did not stop within timeout"
            else:
                LOGGER.info("Alert monitor stopped.")
            self._detach_logs()
            return self.status()

    def _run_loop(self):
        try:
            while not self._stop_event.is_set():
                self._tick()
                self._stop_event.wait(self.poll_seconds)
        except Exception as e:
            LOGGER.error(f"Alert monitor crashed: {e}")
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

    def _tick(self):
        alerts = [a for a in load_alerts() if a.get("enabled")]
        with self._lock:
            self._status["last_tick_at"] = datetime.now().isoformat(timespec="seconds")
            self._status["alerts_checked"] = len(alerts)

        # Drop strategy managers no longer needed
        needed = set()
        for a in alerts:
            if a.get("type") != "strategy" or not a.get("strategy_file"):
                continue
            tickers = a.get("tickers") or [None]
            if not tickers:
                tickers = [None]
            for ticker in tickers:
                needed.add(f"{a['strategy_file']}::{ticker or '__default__'}")
        for key in list(self._strategy_managers.keys()):
            if key not in needed:
                del self._strategy_managers[key]

        for alert in alerts:
            if self._stop_event.is_set():
                break
            try:
                if alert.get("type") == "strategy":
                    self._check_strategy_alert(alert)
                elif alert.get("type") == "price":
                    self._check_price_alert(alert)
            except Exception as e:
                LOGGER.error(f"Alert '{alert.get('name')}' failed: {e}")
                mark_triggered(alert["id"], "", error=str(e))

    def _get_strategy_manager(self, strategy_file: str, ticker: str = None) -> StrategyManager:
        key = f"{strategy_file}::{ticker or '__default__'}"
        if key not in self._strategy_managers:
            path = os.path.join(STRATEGIES_DIR, strategy_file)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Strategy file not found: {strategy_file}")
            self._strategy_managers[key] = StrategyManager.from_json(
                path, ticker=ticker
            )
            label = ticker or "default"
            LOGGER.info(f"Loaded strategy monitor: {strategy_file} [{label}]")
        return self._strategy_managers[key]

    def _check_strategy_alert(self, alert: dict):
        tickers = alert.get("tickers") or []
        # Empty tickers => run once with strategy default symbol
        targets = tickers if tickers else [None]
        for ticker in targets:
            if self._stop_event.is_set():
                break
            self._check_strategy_alert_for_ticker(alert, ticker)

    def _check_strategy_alert_for_ticker(self, alert: dict, ticker: str = None):
        sm = self._get_strategy_manager(alert["strategy_file"], ticker=ticker)
        was_open = sm.position.is_open
        previous_action = sm.position.action
        previous_entry = sm.position.entry_price
        previous_sl = sm.position.stop_loss_price
        previous_tp = sm.position.take_profit_price

        sm.update_market_data()
        _broker_ticker, action, price = sm.check_strategy()
        price = float(price)

        notify_on = alert.get("notify_on") or ["entry", "exit"]
        messages = []

        # Entry: was flat, now open
        if not was_open and sm.position.is_open and "entry" in notify_on:
            messages.append(
                self._format_strategy_message(
                    alert=alert,
                    event="ENTRY",
                    side=sm.position.action,
                    price=price,
                    strategy_name=sm.name,
                    ticker=sm.position.ticker,
                    sl=sm.position.stop_loss_price,
                    tp=sm.position.take_profit_price,
                )
            )

        # Exit: was open, now flat — check_strategy already closed position
        if was_open and not sm.position.is_open and action in ("BUY", "SELL") and "exit" in notify_on:
            messages.append(
                self._format_strategy_message(
                    alert=alert,
                    event="EXIT",
                    side=previous_action,
                    price=price,
                    strategy_name=sm.name,
                    ticker=sm.position.ticker,
                    sl=previous_sl,
                    tp=previous_tp,
                    entry_price=previous_entry,
                )
            )

        for text in messages:
            result = send_telegram_message(text, parse_mode=None)
            if result.get("ok"):
                with self._lock:
                    self._status["messages_sent"] = int(self._status.get("messages_sent") or 0) + 1
                mark_triggered(alert["id"], text, triggered_ticker=sm.position.ticker)
                LOGGER.info(
                    f"Strategy alert '{alert['name']}' notified ({sm.position.ticker})."
                )
            else:
                mark_triggered(alert["id"], text, error=result.get("error"))
                LOGGER.error(f"Failed to notify '{alert['name']}': {result.get('error')}")

    def _format_strategy_message(
        self,
        alert,
        event,
        side,
        price,
        strategy_name,
        ticker,
        sl=None,
        tp=None,
        entry_price=None,
    ) -> str:
        name = alert.get("name") or strategy_name
        direction = "LONG" if side == "BUY" else "SHORT" if side == "SELL" else str(side or "—")

        def _fmt(value):
            if value is None:
                return "—"
            value = float(value)
            if abs(value) >= 100:
                return f"{value:.1f}"
            if abs(value) >= 1:
                return f"{value:.2f}"
            return f"{value:.6f}".rstrip("0").rstrip(".")

        ref_entry = float(price) if event == "ENTRY" else (
            float(entry_price) if entry_price is not None else None
        )
        tp2 = None
        rr1 = None
        rr2 = None
        if ref_entry is not None and sl is not None:
            risk = abs(ref_entry - float(sl))
            if risk > 0:
                tp2 = ref_entry + (2.0 * risk if direction == "LONG" else -2.0 * risk)
                if tp is not None:
                    reward1 = abs(float(tp) - ref_entry)
                    rr1 = reward1 / risk
                if tp2 is not None:
                    reward2 = abs(float(tp2) - ref_entry)
                    rr2 = reward2 / risk

        lines = [
            f"Estrategia: {name}",
            "",
            f"Activo: {ticker}",
            "",
            f"Dirección: {direction}",
            "",
        ]

        if event == "ENTRY":
            lines.append(f"Entrada: {_fmt(price)}")
        else:
            if entry_price is not None:
                lines.append(f"Entrada: {_fmt(entry_price)}")
                lines.append("")
            lines.append(f"Salida: {_fmt(price)}")

        lines.extend(
            [
                "",
                "📌 Niveles Clave:",
                "",
                f"• Stop Loss (SL): {_fmt(sl)}",
                f"• Take Profit 1 (TP1): {_fmt(tp)}",
                f"• Take Profit 2 (TP2): {_fmt(tp2)}",
            ]
        )

        if rr1 is not None or rr2 is not None:
            lines.append("")
            if rr1 is not None and rr2 is not None:
                lines.append(f"R:R → TP1 1:{rr1:.2f} | TP2 1:{rr2:.2f}")
            elif rr1 is not None:
                lines.append(f"R:R → 1:{rr1:.2f}")
            else:
                lines.append(f"R:R → TP2 1:{rr2:.2f}")

        return "\n".join(lines)

    def _check_price_alert(self, alert: dict):
        tickers = alert.get("tickers") or []
        if not tickers and alert.get("ticker"):
            tickers = [alert["ticker"]]
        if not tickers:
            raise ValueError("Price alert has no tickers")

        already = {str(t).upper() for t in (alert.get("triggered_tickers") or [])}
        once = bool(alert.get("once", True))

        for ticker in tickers:
            if self._stop_event.is_set():
                break
            symbol = str(ticker).strip().upper()
            if once and symbol in already:
                continue
            self._check_price_alert_for_ticker(alert, symbol)

    def _check_price_alert_for_ticker(self, alert: dict, ticker: str):
        alert_id = alert["id"]
        state_key = f"{alert_id}:{ticker}"
        interval = alert.get("interval") or "15m"
        period = alert.get("period") or "5d"
        threshold = float(alert["price"])
        condition = alert.get("condition") or "above"

        dm = DataManager(ticker=ticker, interval=interval, period=period)
        if dm.data is None or dm.data.empty:
            raise RuntimeError(f"No data for {ticker}")

        current = float(dm.get_current_price())
        previous = self._price_state.get(state_key)

        # Seed state on first observation — only fire on a later cross
        if previous is None:
            self._price_state[state_key] = current
            return

        triggered = False
        if condition == "above" and previous < threshold <= current:
            triggered = True
        elif condition == "below" and previous > threshold >= current:
            triggered = True

        self._price_state[state_key] = current

        if not triggered:
            return

        text = "\n".join(
            [
                f"Alerta de precio: {alert.get('name')}",
                "",
                f"Activo: {ticker}",
                "",
                f"Condición: precio {condition} {threshold:.2f}",
                f"Actual: {current:.2f}",
                f"Intervalo: {interval}",
            ]
        )
        result = send_telegram_message(text, parse_mode=None)
        disable = bool(alert.get("once", True))
        if result.get("ok"):
            with self._lock:
                self._status["messages_sent"] = int(self._status.get("messages_sent") or 0) + 1
            mark_triggered(
                alert_id,
                text,
                disable=disable,
                triggered_ticker=ticker,
            )
            LOGGER.info(f"Price alert '{alert['name']}' triggered on {ticker} at {current:.2f}.")
        else:
            mark_triggered(alert_id, text, error=result.get("error"))
            LOGGER.error(f"Failed to notify '{alert['name']}': {result.get('error')}")


# Process-wide singleton
alert_runner = AlertRunner(poll_seconds=60)
