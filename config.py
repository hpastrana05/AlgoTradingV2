import os
from dotenv import load_dotenv

load_dotenv()

IS_DEMO = True

API_VER = "api/v0/"
# LINKS
DEMO_LINK = f"https://demo.trading212.com/{API_VER}"
LIVE_LINK = f"https://live.trading212.com/{API_VER}"

# API KEYS (resolved by mode)
API_KEY = None
API_SECRET = None
API_LINK = DEMO_LINK


def _resolve_credentials(is_demo: bool):
    if is_demo:
        return (
            os.getenv("API_KEY_DEMO"),
            os.getenv("API_SECRET_DEMO"),
            DEMO_LINK,
        )
    return (
        os.getenv("API_KEY_LIVE"),
        os.getenv("API_SECRET_LIVE"),
        LIVE_LINK,
    )


def set_trading_mode(is_demo: bool, require_credentials: bool = True) -> dict:
    """
    Switch between Trading212 demo and live endpoints/keys at runtime.
    """
    global IS_DEMO, API_KEY, API_SECRET, API_LINK

    IS_DEMO = bool(is_demo)
    API_KEY, API_SECRET, API_LINK = _resolve_credentials(IS_DEMO)

    if require_credentials and (not API_KEY or not API_SECRET):
        mode = "demo" if IS_DEMO else "live"
        raise ValueError(
            f"Missing API credentials for {mode} mode. "
            f"Set API_KEY_{mode.upper()} and API_SECRET_{mode.upper()} in .env"
        )

    return get_trading_mode()


def get_trading_mode() -> dict:
    return {
        "is_demo": IS_DEMO,
        "mode": "demo" if IS_DEMO else "live",
        "api_link": API_LINK,
        "has_credentials": bool(API_KEY and API_SECRET),
    }


# Initialize from default IS_DEMO without failing hard if .env is incomplete
# (live panel / start will validate credentials explicitly).
API_KEY, API_SECRET, API_LINK = _resolve_credentials(IS_DEMO)
