import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

LOGGER = logging.getLogger("AlertStore")

ALERTS_DIR = Path(__file__).resolve().parent.parent / "alerts"
ALERTS_FILE = ALERTS_DIR / "alerts.json"


def _ensure_dir():
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_alerts() -> List[dict]:
    _ensure_dir()
    if not ALERTS_FILE.exists():
        return []
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        LOGGER.error(f"Failed to load alerts: {e}")
        return []


def save_alerts(alerts: List[dict]) -> None:
    _ensure_dir()
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2)


def get_alert(alert_id: str) -> Optional[dict]:
    for alert in load_alerts():
        if alert.get("id") == alert_id:
            return alert
    return None


def _normalize_tickers(*sources) -> List[str]:
    """
    Accept tickers from a list, a comma/space-separated string, or mixed sources.
    Returns unique uppercase symbols preserving order.
    """
    raw_items = []
    for source in sources:
        if source is None:
            continue
        if isinstance(source, str):
            parts = source.replace(";", ",").replace(" ", ",").split(",")
            raw_items.extend(parts)
        elif isinstance(source, (list, tuple)):
            for item in source:
                if item is None:
                    continue
                if isinstance(item, str):
                    parts = item.replace(";", ",").replace(" ", ",").split(",")
                    raw_items.extend(parts)
                else:
                    raw_items.append(str(item))
        else:
            raw_items.append(str(source))

    seen = set()
    tickers = []
    for item in raw_items:
        symbol = str(item).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        tickers.append(symbol)
    return tickers


def create_alert(payload: dict) -> dict:
    alerts = load_alerts()
    alert_type = payload.get("type")
    if alert_type not in ("strategy", "price"):
        raise ValueError("type must be 'strategy' or 'price'")

    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")

    alert = {
        "id": str(uuid.uuid4()),
        "name": name,
        "type": alert_type,
        "enabled": bool(payload.get("enabled", True)),
        "created_at": _now(),
        "updated_at": _now(),
        "last_triggered_at": None,
        "last_message": None,
        "last_error": None,
        "trigger_count": 0,
    }

    if alert_type == "strategy":
        strategy_file = (payload.get("strategy_file") or "").strip()
        if not strategy_file:
            raise ValueError("strategy_file is required for strategy alerts")
        notify_on = payload.get("notify_on") or ["entry", "exit"]
        if not isinstance(notify_on, list) or not notify_on:
            notify_on = ["entry", "exit"]
        tickers = _normalize_tickers(payload.get("tickers"), payload.get("ticker"))
        alert.update(
            {
                "strategy_file": strategy_file,
                "notify_on": [x for x in notify_on if x in ("entry", "exit")],
                "tickers": tickers,  # empty => use strategy default ticker
            }
        )
    else:
        tickers = _normalize_tickers(payload.get("tickers"), payload.get("ticker"))
        if not tickers:
            raise ValueError("At least one ticker is required for price alerts")
        condition = (payload.get("condition") or "above").lower()
        if condition not in ("above", "below"):
            raise ValueError("condition must be 'above' or 'below'")
        try:
            price = float(payload.get("price"))
        except (TypeError, ValueError) as e:
            raise ValueError("price must be a number") from e
        interval = (payload.get("interval") or "15m").strip() or "15m"
        period = (payload.get("period") or "5d").strip() or "5d"
        once = bool(payload.get("once", True))
        alert.update(
            {
                "tickers": tickers,
                "ticker": tickers[0],  # backward compatible
                "condition": condition,
                "price": price,
                "interval": interval,
                "period": period,
                "once": once,
                "triggered_tickers": [],
            }
        )

    alerts.append(alert)
    save_alerts(alerts)
    return alert


def update_alert(alert_id: str, payload: dict) -> dict:
    alerts = load_alerts()
    for i, alert in enumerate(alerts):
        if alert.get("id") != alert_id:
            continue

        if "name" in payload and payload["name"] is not None:
            name = str(payload["name"]).strip()
            if not name:
                raise ValueError("name cannot be empty")
            alert["name"] = name

        if "enabled" in payload and payload["enabled"] is not None:
            alert["enabled"] = bool(payload["enabled"])

        if alert["type"] == "strategy":
            if payload.get("strategy_file"):
                alert["strategy_file"] = str(payload["strategy_file"]).strip()
            if payload.get("notify_on") is not None:
                notify_on = payload["notify_on"]
                if isinstance(notify_on, list):
                    alert["notify_on"] = [x for x in notify_on if x in ("entry", "exit")]
            if "tickers" in payload or "ticker" in payload:
                alert["tickers"] = _normalize_tickers(
                    payload.get("tickers"), payload.get("ticker")
                )
        else:
            if "tickers" in payload or "ticker" in payload:
                tickers = _normalize_tickers(payload.get("tickers"), payload.get("ticker"))
                if not tickers:
                    raise ValueError("At least one ticker is required")
                alert["tickers"] = tickers
                alert["ticker"] = tickers[0]
            if payload.get("condition") in ("above", "below"):
                alert["condition"] = payload["condition"]
            if payload.get("price") is not None:
                alert["price"] = float(payload["price"])
            if payload.get("interval"):
                alert["interval"] = str(payload["interval"]).strip()
            if payload.get("period"):
                alert["period"] = str(payload["period"]).strip()
            if "once" in payload and payload["once"] is not None:
                alert["once"] = bool(payload["once"])

        alert["updated_at"] = _now()
        alerts[i] = alert
        save_alerts(alerts)
        return alert

    raise KeyError(f"Alert '{alert_id}' not found")


def delete_alert(alert_id: str) -> None:
    alerts = load_alerts()
    new_alerts = [a for a in alerts if a.get("id") != alert_id]
    if len(new_alerts) == len(alerts):
        raise KeyError(f"Alert '{alert_id}' not found")
    save_alerts(new_alerts)


def mark_triggered(
    alert_id: str,
    message: str,
    disable: bool = False,
    error: str = None,
    triggered_ticker: str = None,
) -> None:
    alerts = load_alerts()
    for i, alert in enumerate(alerts):
        if alert.get("id") != alert_id:
            continue
        if error:
            alert["last_error"] = error
        else:
            alert["last_triggered_at"] = _now()
            alert["last_message"] = message
            alert["trigger_count"] = int(alert.get("trigger_count") or 0) + 1
            alert["last_error"] = None
            if triggered_ticker:
                done = list(alert.get("triggered_tickers") or [])
                symbol = str(triggered_ticker).strip().upper()
                if symbol and symbol not in done:
                    done.append(symbol)
                alert["triggered_tickers"] = done
                # For multi-ticker + once: disable only when every ticker has fired
                if disable and alert.get("type") == "price":
                    watched = alert.get("tickers") or ([alert.get("ticker")] if alert.get("ticker") else [])
                    watched = [t for t in watched if t]
                    if watched and all(t in done for t in watched):
                        alert["enabled"] = False
                    elif not watched:
                        alert["enabled"] = False
                    else:
                        disable = False
            if disable:
                alert["enabled"] = False
        alert["updated_at"] = _now()
        alerts[i] = alert
        save_alerts(alerts)
        return
