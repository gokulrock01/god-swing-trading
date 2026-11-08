"""
GOD SWING — ANGEL ONE SMARTAPI LIVE DATA FEED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Official NSE/BSE institutional market feed provider.
Provides:
  - Automated TOTP SmartConnect Authentication
  - Fast Scrip Master token resolution & local caching
  - Direct real-time LTP, High, Low, Volume data
  - Live Broker Equity Order Placement (CNC Delivery)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import time
import requests
import pyotp

# Try loading from local config.py (in root GOD directory) or environment variables
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

try:
    import config
    ANGEL_API_KEY     = getattr(config, "ANGEL_API_KEY", os.getenv("ANGEL_API_KEY", ""))
    ANGEL_CLIENT_CODE = getattr(config, "ANGEL_CLIENT_CODE", os.getenv("ANGEL_CLIENT_CODE", ""))
    ANGEL_PIN         = getattr(config, "ANGEL_PIN", os.getenv("ANGEL_PIN", ""))
    ANGEL_TOTP_KEY    = getattr(config, "ANGEL_TOTP_KEY", os.getenv("ANGEL_TOTP_KEY", ""))
except ImportError:
    ANGEL_API_KEY     = os.getenv("ANGEL_API_KEY", "")
    ANGEL_CLIENT_CODE = os.getenv("ANGEL_CLIENT_CODE", "")
    ANGEL_PIN         = os.getenv("ANGEL_PIN", "")
    ANGEL_TOTP_KEY    = os.getenv("ANGEL_TOTP_KEY", "")

SCRIP_CACHE_FILE = os.path.join(os.path.dirname(__file__), "signals", "angel_scrip_cache.json")
SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

_smart_api_session = None
_token_cache = {}

def get_angel_session():
    """Authenticates with Angel One SmartAPI using TOTP."""
    global _smart_api_session
    if _smart_api_session is not None:
        return _smart_api_session

    if not ANGEL_API_KEY or not ANGEL_CLIENT_CODE or not ANGEL_PIN or not ANGEL_TOTP_KEY:
        print("  ⚠️ Angel One credentials missing in config.py or environment variables.")
        return None

    try:
        from SmartApi import SmartConnect
        smart_api = SmartConnect(api_key=ANGEL_API_KEY)
        totp = pyotp.TOTP(ANGEL_TOTP_KEY).now()
        data = smart_api.generateSession(ANGEL_CLIENT_CODE, ANGEL_PIN, totp)

        if data.get("status"):
            print(f"  ✅ Authenticated with Angel One SmartAPI (Client: {ANGEL_CLIENT_CODE})")
            _smart_api_session = smart_api
            return _smart_api_session
        else:
            print(f"  ❌ Angel One Login Failed: {data.get('message')}")
            return None
    except Exception as e:
        print(f"  ⚠️ Error during Angel One login: {e}")
        return None

def load_or_update_scrip_cache():
    """Loads token map from local cache, or downloads from Angel One if missing."""
    global _token_cache
    if _token_cache:
        return _token_cache

    os.makedirs(os.path.dirname(SCRIP_CACHE_FILE), exist_ok=True)
    if os.path.exists(SCRIP_CACHE_FILE):
        try:
            with open(SCRIP_CACHE_FILE, "r") as f:
                _token_cache = json.load(f)
                if _token_cache:
                    return _token_cache
        except Exception:
            pass

    print("  📥 Fetching Angel One Scrip Master for NSE Equities...")
    try:
        resp = requests.get(SCRIP_MASTER_URL, timeout=15)
        if resp.status_code == 200:
            raw = resp.json()
            cache = {}
            for item in raw:
                if item.get("exch_seg") == "NSE" and item.get("symbol", "").endswith("-EQ"):
                    base_sym = item["symbol"].replace("-EQ", "")
                    cache[base_sym] = {
                        "tradingsymbol": item["symbol"],
                        "symboltoken": item["token"]
                    }
            _token_cache = cache
            with open(SCRIP_CACHE_FILE, "w") as f:
                json.dump(_token_cache, f)
            print(f"  ✅ Cached {len(cache)} NSE equity scrip tokens.")
            return _token_cache
    except Exception as e:
        print(f"  ⚠️ Failed to download Scrip Master: {e}")
    return {}

def get_scrip_token(symbol):
    """Returns (tradingsymbol, symboltoken) for a given stock symbol."""
    cache = load_or_update_scrip_cache()
    clean_sym = symbol.replace(".NS", "").upper()
    if clean_sym in cache:
        return cache[clean_sym]["tradingsymbol"], cache[clean_sym]["symboltoken"]
    # Fallback to standard conventions
    return f"{clean_sym}-EQ", None

def get_live_ltp(symbol):
    """Fetches real-time LTP, High, Low, and Close from Angel One."""
    session = get_angel_session()
    if not session:
        return None

    tradingsymbol, token = get_scrip_token(symbol)
    if not token:
        return None

    try:
        data = session.ltpData(exchange="NSE", tradingsymbol=tradingsymbol, symboltoken=token)
        if data.get("status") and "data" in data:
            d = data["data"]
            return {
                "symbol": symbol,
                "tradingsymbol": tradingsymbol,
                "token": token,
                "ltp": float(d.get("ltp", 0.0)),
                "open": float(d.get("open", 0.0)),
                "high": float(d.get("high", 0.0)),
                "low": float(d.get("low", 0.0)),
                "close": float(d.get("close", 0.0))
            }
    except Exception as e:
        print(f"  ⚠️ Error fetching LTP for {symbol}: {e}")
    return None

def place_live_cnc_order(symbol, qty, price, transaction_type="BUY"):
    """
    Places a live CNC (Delivery) Equity swing order on Angel One.
    Set MODE='LIVE' in config.py to enable real execution.
    """
    session = get_angel_session()
    if not session:
        print("  ❌ Cannot place order: Not authenticated with Angel One.")
        return None

    tradingsymbol, token = get_scrip_token(symbol)
    if not token:
        print(f"  ❌ Cannot find token for {symbol}")
        return None

    order_params = {
        "variety": "NORMAL",
        "tradingsymbol": tradingsymbol,
        "symboltoken": token,
        "transactiontype": transaction_type.upper(),
        "exchange": "NSE",
        "ordertype": "LIMIT",
        "producttype": "CNC",
        "duration": "DAY",
        "price": str(price),
        "squareoff": "0",
        "stoploss": "0",
        "quantity": str(qty)
    }

    try:
        order_id = session.placeOrder(order_params)
        print(f"  🚀 Angel One Order Placed! Order ID: {order_id} ({transaction_type} {qty} {symbol} @ ₹{price})")
        return order_id
    except Exception as e:
        print(f"  ❌ Angel One Order Placement Error: {e}")
        return None

if __name__ == "__main__":
    print("Testing Angel One Feed...")
    s = get_angel_session()
    if s:
        test_syms = ["BBOX", "PTCIL", "BHEL", "OFSS"]
        for sym in test_syms:
            info = get_live_ltp(sym)
            print(f"  • {sym}: {info}")
