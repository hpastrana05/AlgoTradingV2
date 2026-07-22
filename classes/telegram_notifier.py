import json
import logging
from pathlib import Path
from typing import Optional

import requests

import config

LOGGER = logging.getLogger("TelegramNotifier")

ALERTS_DIR = Path(__file__).resolve().parent.parent / "alerts"
TELEGRAM_CONFIG_PATH = ALERTS_DIR / "telegram.json"


def _ensure_alerts_dir():
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)


def load_telegram_config() -> dict:
    """
    Merge UI-saved config with .env defaults.
    UI file wins when present; secrets are never returned in full to the client.
    """
    _ensure_alerts_dir()
    env = config.get_telegram_env()
    stored = {}
    if TELEGRAM_CONFIG_PATH.exists():
        try:
            with open(TELEGRAM_CONFIG_PATH, "r", encoding="utf-8") as f:
                stored = json.load(f) or {}
        except Exception as e:
            LOGGER.warning(f"Failed to read telegram config: {e}")

    bot_token = (stored.get("bot_token") or env.get("bot_token") or "").strip()
    chat_id = (stored.get("chat_id") or env.get("chat_id") or "").strip()
    return {
        "bot_token": bot_token,
        "chat_id": chat_id,
        "configured": bool(bot_token and chat_id),
        "source": "file" if stored.get("bot_token") or stored.get("chat_id") else "env",
    }


def save_telegram_config(bot_token: str = None, chat_id: str = None) -> dict:
    """Update telegram.json. Empty strings clear; None leaves existing value."""
    _ensure_alerts_dir()
    current = {}
    if TELEGRAM_CONFIG_PATH.exists():
        try:
            with open(TELEGRAM_CONFIG_PATH, "r", encoding="utf-8") as f:
                current = json.load(f) or {}
        except Exception:
            current = {}

    if bot_token is not None:
        current["bot_token"] = bot_token.strip()
    if chat_id is not None:
        current["chat_id"] = str(chat_id).strip()

    with open(TELEGRAM_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

    return public_telegram_status()


def public_telegram_status() -> dict:
    """Safe status for the UI (token masked)."""
    cfg = load_telegram_config()
    token = cfg["bot_token"]
    masked = ""
    if token:
        masked = token[:6] + "…" + token[-4:] if len(token) > 12 else "••••"
    return {
        "configured": cfg["configured"],
        "has_token": bool(token),
        "has_chat_id": bool(cfg["chat_id"]),
        "chat_id": cfg["chat_id"],
        "token_masked": masked,
        "source": cfg["source"],
    }


def send_telegram_message(text: str, parse_mode: Optional[str] = "HTML") -> dict:
    """
    Send a message to the configured Telegram chat.
    Returns {"ok": bool, "error": optional str, "result": optional dict}.
    """
    cfg = load_telegram_config()
    if not cfg["bot_token"] or not cfg["chat_id"]:
        return {
            "ok": False,
            "error": "Telegram is not configured. Set bot token and chat id in Alerts or .env.",
        }

    url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
    payload = {
        "chat_id": cfg["chat_id"],
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=15)
        data = response.json() if response.content else {}
        if response.ok and data.get("ok"):
            LOGGER.info("Telegram message sent.")
            return {"ok": True, "result": data.get("result")}
        description = data.get("description") or response.text or f"HTTP {response.status_code}"
        LOGGER.error(f"Telegram send failed: {description}")
        return {"ok": False, "error": description}
    except Exception as e:
        LOGGER.error(f"Telegram send error: {e}")
        return {"ok": False, "error": str(e)}
