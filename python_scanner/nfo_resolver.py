"""
==============================================================================
NFO STOCK OPTIONS CONTRACT RESOLVER (ANGEL ONE SMARTAPI)
==============================================================================
Resolves official NSE F&O Stock Option contracts:
  - ATM CE and PE Strikes (for Momentum Sniper)
  - 2-Leg Hedged Credit Spreads (Bull Put Spread / Bear Call Spread)
  - Local caching of contract tokens for sub-millisecond execution
==============================================================================
"""

import os
import json
import requests
from datetime import datetime

NFO_CACHE_FILE = os.path.join(os.path.dirname(__file__), "signals", "nfo_contracts_cache.json")
SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

_nfo_cache = None

def load_nfo_master():
    """Loads NFO stock option contracts from local cache or downloads fresh."""
    global _nfo_cache
    if _nfo_cache is not None:
        return _nfo_cache

    os.makedirs(os.path.dirname(NFO_CACHE_FILE), exist_ok=True)
    if os.path.exists(NFO_CACHE_FILE):
        try:
            with open(NFO_CACHE_FILE, "r") as f:
                _nfo_cache = json.load(f)
                if _nfo_cache:
                    return _nfo_cache
        except Exception:
            pass

    print("  📥 Fetching Angel One NFO Stock Options Scrip Master...")
    try:
        resp = requests.get(SCRIP_MASTER_URL, timeout=15)
        if resp.status_code == 200:
            raw = resp.json()
            cache = {}
            for item in raw:
                # Filter OPTSTK (Stock Options) on NFO exchange
                if item.get("exch_seg") == "NFO" and item.get("instrumenttype") == "OPTSTK":
                    name = item.get("name", "")
                    if name not in cache:
                        cache[name] = []
                    cache[name].append({
                        "symbol": item["symbol"],
                        "token": item["token"],
                        "expiry": item["expiry"],
                        "strike": float(item["strike"]) / 100.0,
                        "lotsize": int(item["lotsize"]),
                        "type": "CE" if item["symbol"].endswith("CE") else "PE"
                    })
            _nfo_cache = cache
            with open(NFO_CACHE_FILE, "w") as f:
                json.dump(_nfo_cache, f)
            print(f"  ✅ Cached NFO option contracts for {len(_nfo_cache)} F&O stocks.")
            return _nfo_cache
    except Exception as e:
        print(f"  ⚠️ Error downloading NFO Scrip Master: {e}")
    return {}

def get_current_expiry(name):
    """Returns the nearest upcoming monthly expiry string."""
    master = load_nfo_master()
    if name not in master:
        return None
    contracts = master[name]
    expiries = sorted(list(set(c["expiry"] for c in contracts)))
    return expiries[0] if expiries else None

def get_atm_option(name, spot_price, option_type="CE"):
    """
    Finds the nearest At-The-Money (ATM) option contract for a stock.
    Returns: { symbol, token, strike, lotsize, expiry, type }
    """
    master = load_nfo_master()
    clean_name = name.replace(".NS", "").upper()
    if clean_name not in master:
        return None

    curr_expiry = get_current_expiry(clean_name)
    if not curr_expiry:
        return None

    candidates = [
        c for c in master[clean_name]
        if c["expiry"] == curr_expiry and c["type"] == option_type.upper()
    ]
    if not candidates:
        return None

    closest = min(candidates, key=lambda c: abs(c["strike"] - spot_price))
    return closest

def get_credit_spread_contracts(name, spot_price, spread_type="BULL_PUT"):
    """
    Resolves 2-leg hedged stock option credit spread contracts:
      - BULL_PUT_SPREAD:
          Leg 1 (Sell): 1 Strike OTM Put (below spot)
          Leg 2 (Buy Hedge): 2 Strikes OTM Put (further below spot)
      - BEAR_CALL_SPREAD:
          Leg 1 (Sell): 1 Strike OTM Call (above spot)
          Leg 2 (Buy Hedge): 2 Strikes OTM Call (further above spot)
    """
    master = load_nfo_master()
    clean_name = name.replace(".NS", "").upper()
    if clean_name not in master:
        return None

    curr_expiry = get_current_expiry(clean_name)
    if not curr_expiry:
        return None

    opt_type = "PE" if spread_type == "BULL_PUT" else "CE"
    candidates = sorted(
        [c for c in master[clean_name] if c["expiry"] == curr_expiry and c["type"] == opt_type],
        key=lambda c: c["strike"]
    )
    if not candidates:
        return None

    if spread_type == "BULL_PUT":
        # Put strikes below spot
        otm_puts = [c for c in candidates if c["strike"] < spot_price]
        if len(otm_puts) < 2:
            return None
        sell_leg = otm_puts[-1] # 1 strike OTM
        buy_leg  = otm_puts[-2] # 2 strikes OTM (hedge)
        return {"sell_leg": sell_leg, "buy_leg": buy_leg, "type": "BULL_PUT_SPREAD"}
    else:
        # Call strikes above spot
        otm_calls = [c for c in candidates if c["strike"] > spot_price]
        if len(otm_calls) < 2:
            return None
        sell_leg = otm_calls[0] # 1 strike OTM
        buy_leg  = otm_calls[1] # 2 strikes OTM (hedge)
        return {"sell_leg": sell_leg, "buy_leg": buy_leg, "type": "BEAR_CALL_SPREAD"}

if __name__ == "__main__":
    load_nfo_master()
    print("Testing Resolver:")
    print("  • TATASTEEL ATM CE (Spot 152):", get_atm_option("TATASTEEL", 152.0, "CE"))
    print("  • RELIANCE Bull Put Spread (Spot 1315):", get_credit_spread_contracts("RELIANCE", 1315.0, "BULL_PUT"))
