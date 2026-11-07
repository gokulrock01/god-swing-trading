"""
GOD SWING SCANNER v2.0 — DEEP ANALYSIS ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Every A+/A signal gets the same analysis a human expert
would do — factor by factor, with a clear final verdict.

Output per stock:
  - Every layer checked with reason
  - Specific confirmation level to watch
  - Risk flags (small cap, sector risk, low liquidity)
  - Verdict: BUY NOW / WAIT / SKIP / AVOID
  - Position size for your capital
  - Final ranked decision table
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run: python3 swing_scanner_v2.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import os
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

# Avoid sqlite cache contention
try:
    yf.set_tz_cache_location("/tmp/yfinance_tz_cache")
except Exception:
    pass

# ─────────────────────────────────────────────────────
# CONFIG — Edit these to match your preferences
# ─────────────────────────────────────────────────────
CAPITAL          = 1_000_000   # Your total trading capital in ₹
RISK_PCT_APLUS   = 1.5         # Risk % for A+ trades
RISK_PCT_A       = 1.0         # Risk % for A trades
MAX_OPEN_TRADES  = 6           # Max simultaneous positions
MIN_SCORE        = 6           # Minimum score to show (A grade)
NUM_THREADS      = 12          # Parallel workers for blazing fast 500-stock scan

# ─────────────────────────────────────────────────────
# STOCK UNIVERSE WITH METADATA
# (sector, market_cap_tier, risk_flags)
# ─────────────────────────────────────────────────────
UNIVERSE = {
    "TCS":         {"sector": "IT",             "tier": "large", "risk": None},
    "HDFCBANK":    {"sector": "Banking",        "tier": "large", "risk": None},
    "INFY":        {"sector": "IT",             "tier": "large", "risk": None},
    "ICICIBANK":   {"sector": "Banking",        "tier": "large", "risk": None},
    "HINDUNILVR":  {"sector": "FMCG",          "tier": "large", "risk": None},
    "SBIN":        {"sector": "Banking",        "tier": "large", "risk": None},
    "BHARTIARTL":  {"sector": "Telecom",        "tier": "large", "risk": None},
    "KOTAKBANK":   {"sector": "Banking",        "tier": "large", "risk": None},
    "LT":          {"sector": "Infra",          "tier": "large", "risk": None},
    "AXISBANK":    {"sector": "Banking",        "tier": "large", "risk": None},
    "ASIANPAINT":  {"sector": "Paints",         "tier": "large", "risk": None},
    "MARUTI":      {"sector": "Auto",           "tier": "large", "risk": None},
    "TITAN":       {"sector": "Consumer",       "tier": "large", "risk": None},
    "SUNPHARMA":   {"sector": "Pharma",         "tier": "large", "risk": None},
    "BAJFINANCE":  {"sector": "NBFC",           "tier": "large", "risk": None},
    "WIPRO":       {"sector": "IT",             "tier": "large", "risk": None},
    "NESTLEIND":   {"sector": "FMCG",          "tier": "large", "risk": None},
    "ULTRACEMCO":  {"sector": "Cement",         "tier": "large", "risk": None},
    "TECHM":       {"sector": "IT",             "tier": "large", "risk": None},
    "HCLTECH":     {"sector": "IT",             "tier": "large", "risk": None},
    "POWERGRID":   {"sector": "Power",          "tier": "large", "risk": None},
    "NTPC":        {"sector": "Power",          "tier": "large", "risk": None},
    "COALINDIA":   {"sector": "Mining",         "tier": "large", "risk": None},
    "ONGC":        {"sector": "Oil & Gas",      "tier": "large", "risk": None},
    "TATAMOTORS":  {"sector": "Auto",           "tier": "large", "risk": None},
    "TATASTEEL":   {"sector": "Metal",          "tier": "large", "risk": None},
    "JSWSTEEL":    {"sector": "Metal",          "tier": "large", "risk": None},
    "HINDALCO":    {"sector": "Metal",          "tier": "large", "risk": None},
    "GRASIM":      {"sector": "Cement",         "tier": "large", "risk": None},
    "DRREDDY":     {"sector": "Pharma",         "tier": "large", "risk": None},
    "CIPLA":       {"sector": "Pharma",         "tier": "large", "risk": None},
    "DIVISLAB":    {"sector": "Pharma",         "tier": "large", "risk": None},
    "APOLLOHOSP":  {"sector": "Healthcare",     "tier": "large", "risk": None},
    "ADANIPORTS":  {"sector": "Ports/Infra",    "tier": "large", "risk": "Adani group risk"},
    "BPCL":        {"sector": "Oil & Gas",      "tier": "large", "risk": "PSU - govt policy risk"},
    "IOC":         {"sector": "Oil & Gas",      "tier": "large", "risk": "PSU - govt policy risk"},
    "HEROMOTOCO":  {"sector": "Auto",           "tier": "large", "risk": None},
    "BAJAJFINSV":  {"sector": "NBFC",           "tier": "large", "risk": None},
    "EICHERMOT":   {"sector": "Auto",           "tier": "large", "risk": None},
    "TATACONSUM":  {"sector": "FMCG",          "tier": "large", "risk": None},
    "INDUSINDBK":  {"sector": "Banking",        "tier": "large", "risk": None},
    "SHREECEM":    {"sector": "Cement",         "tier": "large", "risk": None},
    "BRITANNIA":   {"sector": "FMCG",          "tier": "large", "risk": None},
    "M&M":         {"sector": "Auto",           "tier": "large", "risk": None},
    "SBILIFE":     {"sector": "Insurance",      "tier": "large", "risk": None},
    "HDFCLIFE":    {"sector": "Insurance",      "tier": "large", "risk": None},
    "ADANIENT":    {"sector": "Conglomerate",   "tier": "large", "risk": "Adani group risk"},
    "VEDL":        {"sector": "Metal",          "tier": "large", "risk": "Promoter pledge risk"},
    "PIDILITIND":  {"sector": "Chemicals",      "tier": "large", "risk": None},

    # MID CAP
    "ABBOTINDIA":  {"sector": "Pharma",         "tier": "mid",   "risk": None},
    "ALKEM":       {"sector": "Pharma",         "tier": "mid",   "risk": None},
    "AMBUJACEM":   {"sector": "Cement",         "tier": "mid",   "risk": None},
    "AUROPHARMA":  {"sector": "Pharma",         "tier": "mid",   "risk": None},
    "BALKRISIND":  {"sector": "Auto Ancillary", "tier": "mid",   "risk": None},
    "BANDHANBNK":  {"sector": "Banking",        "tier": "mid",   "risk": "Microfinance stress risk"},
    "BERGEPAINT":  {"sector": "Paints",         "tier": "mid",   "risk": None},
    "BIOCON":      {"sector": "Pharma/Biotech", "tier": "mid",   "risk": "FDA risk"},
    "CANBK":       {"sector": "Banking",        "tier": "mid",   "risk": "PSU bank risk"},
    "CHOLAFIN":    {"sector": "NBFC",           "tier": "mid",   "risk": None},
    "COFORGE":     {"sector": "IT",             "tier": "mid",   "risk": None},
    "CONCOR":      {"sector": "Logistics",      "tier": "mid",   "risk": "PSU - divestment risk"},
    "CROMPTON":    {"sector": "Consumer Elec",  "tier": "mid",   "risk": None},
    "CUMMINSIND":  {"sector": "Engineering",    "tier": "mid",   "risk": None},
    "DABUR":       {"sector": "FMCG",          "tier": "mid",   "risk": None},
    "DEEPAKNTR":   {"sector": "Chemicals",      "tier": "mid",   "risk": None},
    "DELTACORP":   {"sector": "Gaming/Casino",  "tier": "mid",   "risk": "HIGH: Gaming regulation risk - GST hike possible anytime"},
    "ESCORTS":     {"sector": "Agri/Auto",      "tier": "mid",   "risk": None},
    "EXIDEIND":    {"sector": "Auto Ancillary", "tier": "mid",   "risk": None},
    "FEDERALBNK":  {"sector": "Banking",        "tier": "mid",   "risk": None},
    "GLAND":       {"sector": "Pharma",         "tier": "mid",   "risk": "FDA risk"},
    "GODREJCP":    {"sector": "FMCG",          "tier": "mid",   "risk": None},
    "GODREJPROP":  {"sector": "Real Estate",    "tier": "mid",   "risk": None},
    "GRANULES":    {"sector": "Pharma",         "tier": "mid",   "risk": "FDA risk"},
    "GSPL":        {"sector": "Gas",            "tier": "mid",   "risk": None},
    "HAL":         {"sector": "Defence",        "tier": "mid",   "risk": None},
    "HAVELLS":     {"sector": "Consumer Elec",  "tier": "mid",   "risk": None},
    "IDFCFIRSTB":  {"sector": "Banking",        "tier": "mid",   "risk": None},
    "INDIAMART":   {"sector": "Internet",       "tier": "mid",   "risk": None},
    "INDUSTOWER":  {"sector": "Telecom Infra",  "tier": "mid",   "risk": None},
    "IGL":         {"sector": "Gas",            "tier": "mid",   "risk": "Govt price regulation risk"},
    "IRCTC":       {"sector": "Travel/Govt",    "tier": "mid",   "risk": "PSU - govt policy risk"},
    "JUBLFOOD":    {"sector": "QSR/Food",       "tier": "mid",   "risk": None},
    "KANSAINER":   {"sector": "Paints",         "tier": "mid",   "risk": None},
    "LALPATHLAB":  {"sector": "Healthcare",     "tier": "mid",   "risk": None},
    "LICHSGFIN":   {"sector": "NBFC",           "tier": "mid",   "risk": None},
    "LTTS":        {"sector": "IT",             "tier": "mid",   "risk": None},
    "LUPIN":       {"sector": "Pharma",         "tier": "mid",   "risk": "FDA risk"},
    "MARICO":      {"sector": "FMCG",          "tier": "mid",   "risk": None},
    "MFSL":        {"sector": "Insurance",      "tier": "mid",   "risk": None},
    "MPHASIS":     {"sector": "IT",             "tier": "mid",   "risk": None},
    "MRF":         {"sector": "Tyres",          "tier": "mid",   "risk": None},
    "MUTHOOTFIN":  {"sector": "Gold Finance",   "tier": "mid",   "risk": None},
    "NAUKRI":      {"sector": "Internet",       "tier": "mid",   "risk": None},
    "NAVINFLUOR":  {"sector": "Chemicals",      "tier": "mid",   "risk": None},
    "OBEROIRLTY":  {"sector": "Real Estate",    "tier": "mid",   "risk": None},
    "OFSS":        {"sector": "IT",             "tier": "mid",   "risk": None},
    "PAGEIND":     {"sector": "Consumer",       "tier": "mid",   "risk": None},
    "PERSISTENT":  {"sector": "IT",             "tier": "mid",   "risk": None},
    "PETRONET":    {"sector": "Gas",            "tier": "mid",   "risk": None},
    "PFC":         {"sector": "Power Finance",  "tier": "mid",   "risk": "PSU risk"},
    "PHOENIXLTD":  {"sector": "Real Estate",    "tier": "mid",   "risk": None},
    "PIIND":       {"sector": "Agri Chem",      "tier": "mid",   "risk": None},
    "PNB":         {"sector": "Banking",        "tier": "mid",   "risk": "PSU bank NPA risk"},
    "POLYCAB":     {"sector": "Cables",         "tier": "mid",   "risk": None},
    "RECLTD":      {"sector": "Power Finance",  "tier": "mid",   "risk": "PSU risk"},
    "SAIL":        {"sector": "Metal",          "tier": "mid",   "risk": "PSU - govt policy risk"},
    "SOLARINDS":   {"sector": "Defence",        "tier": "mid",   "risk": None},
    "SUNTV":       {"sector": "Media",          "tier": "mid",   "risk": None},
    "SUPREMEIND":  {"sector": "Plastics",       "tier": "mid",   "risk": None},
    "TATACOMM":    {"sector": "Telecom",        "tier": "mid",   "risk": None},
    "TATAELXSI":   {"sector": "IT/Design",      "tier": "mid",   "risk": None},
    "TORNTPHARM":  {"sector": "Pharma",         "tier": "mid",   "risk": None},
    "TRENT":       {"sector": "Retail",         "tier": "mid",   "risk": None},
    "TRIDENT":     {"sector": "Textiles",       "tier": "small", "risk": "Commodity price risk"},
    "UBL":         {"sector": "Beverages",      "tier": "mid",   "risk": None},
    "UNIONBANK":   {"sector": "Banking",        "tier": "mid",   "risk": "PSU bank risk"},
    "UPL":         {"sector": "Agri Chem",      "tier": "mid",   "risk": "High debt risk"},
    "VOLTAS":      {"sector": "Consumer Elec",  "tier": "mid",   "risk": None},
    "ZOMATO":      {"sector": "Internet/Food",  "tier": "mid",   "risk": "Profitability risk"},
    "NYKAA":       {"sector": "Internet/Beauty","tier": "mid",   "risk": "Lock-in expiry risk"},
    "PAYTM":       {"sector": "Fintech",        "tier": "mid",   "risk": "HIGH: RBI regulatory risk"},
    "POLICYBZR":   {"sector": "Insurtech",      "tier": "mid",   "risk": "Profitability risk"},
    "DELHIVERY":   {"sector": "Logistics",      "tier": "mid",   "risk": "Profitability risk"},
    "CAMPUS":      {"sector": "Footwear",       "tier": "small", "risk": None},
}

# ─────────────────────────────────────────────────────
# STOCK UNIVERSE LOADER (All 501 Nifty 500 Stocks)
# ─────────────────────────────────────────────────────
def load_nifty500():
    syms_path = os.path.join(os.path.dirname(__file__), "..", "config", "nifty500_symbols.txt")
    symbols = []
    if os.path.exists(syms_path):
        with open(syms_path, "r") as f:
            symbols = [line.strip().upper() for line in f if line.strip()]
    if not symbols:
        try:
            url = 'https://archives.nseindia.com/content/indices/ind_nifty500list.csv'
            import urllib.request
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp:
                df = pd.read_csv(resp)
                symbols = df['Symbol'].tolist()
        except Exception:
            pass

    full_universe = {}
    for s in symbols:
        if s in UNIVERSE:
            full_universe[s] = UNIVERSE[s]
        else:
            full_universe[s] = {"sector": "Nifty 500", "tier": "mid/small", "risk": None}
    return full_universe

FULL_NIFTY500 = load_nifty500()

# ─────────────────────────────────────────────────────
# INDICATOR FUNCTIONS
# ─────────────────────────────────────────────────────

def ema(s, p):   return s.ewm(span=p, adjust=False).mean()
def rsi_calc(s, p=14):
    d = s.diff(); g = d.clip(lower=0); l = -d.clip(upper=0)
    ag = g.ewm(span=p, adjust=False).mean(); al = l.ewm(span=p, adjust=False).mean()
    return 100 - (100 / (1 + ag / al))
def atr_calc(h, l, c, p=14):
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(span=p, adjust=False).mean()
def obv_calc(c, v):
    return (np.sign(c.diff()) * v).cumsum()

def weekly_cpr(df):
    df = df.copy()
    df["week"] = df.index.to_period("W")
    wk = df.groupby("week").agg(wH=("High","max"), wL=("Low","min"), wC=("Close","last")).shift(1)
    df = df.join(wk, on="week")
    df["wPivot"] = (df["wH"] + df["wL"] + df["wC"]) / 3
    df["wBC"]    = (df["wH"] + df["wL"]) / 2
    df["wTC"]    = (df["wPivot"] - df["wBC"]) + df["wPivot"]
    df["wWidth"] = (df["wTC"] - df["wBC"]).abs()
    df["wWidthAvg"] = df["wWidth"].rolling(20).mean()
    return df

def monthly_cpr(df):
    df = df.copy()
    df["month"] = df.index.to_period("M")
    mo = df.groupby("month").agg(mH=("High","max"), mL=("Low","min"), mC=("Close","last")).shift(1)
    df = df.join(mo, on="month")
    df["mPivot"] = (df["mH"] + df["mL"] + df["mC"]) / 3
    df["mBC"]    = (df["mH"] + df["mL"]) / 2
    df["mTC"]    = (df["mPivot"] - df["mBC"]) + df["mPivot"]
    return df

# ─────────────────────────────────────────────────────
# DEEP ANALYSIS ENGINE
# ─────────────────────────────────────────────────────

def analyse_stock(symbol, meta):
    ticker = symbol + ".NS"
    try:
        df = yf.download(ticker, period="1y", interval="1d",
                         auto_adjust=True, progress=False, threads=False)
        if df is None or len(df) < 60:
            return None
        df.columns = df.columns.droplevel(1) if isinstance(df.columns, pd.MultiIndex) else df.columns
        df = df[["Open","High","Low","Close","Volume"]].dropna()

        # Indicators
        df["e21"]  = ema(df["Close"], 21)
        df["e50"]  = ema(df["Close"], 50)
        df["e200"] = ema(df["Close"], 200)
        df["rsi"]  = rsi_calc(df["Close"])
        df["atr"]  = atr_calc(df["High"], df["Low"], df["Close"])
        df["vSMA"] = df["Volume"].rolling(20).mean()
        df["obv"]  = obv_calc(df["Close"], df["Volume"])
        df["obvE"] = ema(df["obv"], 21)
        df["bVol"] = df["Volume"].where(df["Close"] > df["Open"], 0)
        df["beVol"]= df["Volume"].where(df["Close"] < df["Open"], 0)
        df["cvd"]  = (df["bVol"] - df["beVol"]).cumsum()
        df["cvdE"] = ema(df["cvd"], 14)

        df = weekly_cpr(df)
        df = monthly_cpr(df)

        # Swing levels
        lb = 20
        df["swH"] = df["High"].rolling(lb).max()
        df["swL"] = df["Low"].rolling(lb).min()
        df["swR"] = df["swH"] - df["swL"]
        df["f618"] = df["swH"] - df["swR"] * 0.618
        df["f65"]  = df["swH"] - df["swR"] * 0.65
        df["f786"] = df["swH"] - df["swR"] * 0.786
        df["f382"] = df["swH"] - df["swR"] * 0.382
        df["f127"] = df["swH"] + df["swR"] * 0.272
        df["f161"] = df["swH"] + df["swR"] * 0.618

        r = df.iloc[-1]
        c = r["Close"]

        # ── Individual condition checks with reason ──────────────

        checks = {}

        # 1. Trend (relaxed: EMA 21 within 2% of EMA 50 is OK — avoids false FAIL on crossovers)
        e21_v = r["e21"]; e50_v = r["e50"]; e200_v = r["e200"]
        ema_aligned = e21_v > e50_v or (e21_v >= e50_v * 0.98)   # allow 2% tolerance
        if c > e50_v and ema_aligned and c > e200_v:
            checks["Trend"] = ("PASS", f"Price above EMA 50 & 200, EMA 21 aligned — strong bull structure")
        elif c > e200_v and c > e50_v:
            checks["Trend"] = ("PARTIAL", f"Price above EMA 200 ({round(e200_v,1)}) and 50 ({round(e50_v,1)}) — trend intact, EMA 21 lagging")
        elif c > e200_v:
            checks["Trend"] = ("PARTIAL", f"Price above EMA 200 ({round(e200_v,1)}) — long-term uptrend intact, medium-term weak")
        else:
            checks["Trend"] = ("FAIL", f"Price ₹{round(c,2)} below EMA 200 ₹{round(e200_v,1)} — not in uptrend")

        # 2. Weekly CPR width
        wNarrow = r["wWidth"] < r["wWidthAvg"] * 0.8 if not pd.isna(r.get("wWidth", np.nan)) else False
        if wNarrow:
            checks["Weekly CPR Width"] = ("PASS", f"Narrow CPR = ₹{round(r['wWidth'],1)} vs avg ₹{round(r['wWidthAvg'],1)} — trending week ahead")
        else:
            checks["Weekly CPR Width"] = ("WARN", f"Wide CPR = ₹{round(r['wWidth'],1)} vs avg ₹{round(r['wWidthAvg'],1)} — choppy/range week possible")

        # 3. Weekly CPR position
        wTC = r.get("wTC", np.nan)
        wBC = r.get("wBC", np.nan)
        if not pd.isna(wTC):
            if c > wTC:
                checks["Weekly CPR Position"] = ("PASS", f"Price ₹{round(c,2)} above Weekly TC ₹{round(wTC,2)} — bullish bias confirmed")
            elif c > wBC:
                checks["Weekly CPR Position"] = ("WARN", f"Price ₹{round(c,2)} between BC ₹{round(wBC,2)} and TC ₹{round(wTC,2)} — in CPR zone, needs breakout above ₹{round(wTC,2)}")
            else:
                checks["Weekly CPR Position"] = ("FAIL", f"Price ₹{round(c,2)} below Weekly BC ₹{round(wBC,2)} — bearish CPR position")
        else:
            checks["Weekly CPR Position"] = ("WARN", "Weekly CPR data unavailable")

        # 4. Monthly CPR
        mTC = r.get("mTC", np.nan)
        mBC = r.get("mBC", np.nan)
        if not pd.isna(mTC):
            if c > mTC:
                checks["Monthly CPR"] = ("PASS", f"Price above Monthly TC ₹{round(mTC,2)} — institutional monthly bias bullish")
            else:
                checks["Monthly CPR"] = ("WARN", f"Price below Monthly TC ₹{round(mTC,2)} — caution on bigger timeframe")
        else:
            checks["Monthly CPR"] = ("WARN", "Monthly CPR data unavailable")

        # 5. Fibonacci zone
        f618 = r["f618"]; f65 = r["f65"]; f786 = r["f786"]
        if c <= f618 and c >= f65:
            checks["Fibonacci Zone"] = ("PASS", f"Price ₹{round(c,2)} in Golden Pocket (0.618=₹{round(f618,2)} to 0.65=₹{round(f65,2)}) — ideal reversal zone")
        elif c <= f618 * 1.02 and c >= f786 * 0.98:
            checks["Fibonacci Zone"] = ("PASS", f"Price ₹{round(c,2)} in deep Fib zone (0.618-0.786) — valid pullback area, slight overshoot possible")
        elif c < f786:
            checks["Fibonacci Zone"] = ("FAIL", f"Price ₹{round(c,2)} below 0.786 Fib ₹{round(f786,2)} — pullback too deep, structure may be breaking")
        else:
            checks["Fibonacci Zone"] = ("WARN", f"Price ₹{round(c,2)} not in Fib zone yet. Watch for pullback to ₹{round(f618,2)} (0.618 level)")

        # 6. RSI
        rv = r["rsi"]
        if 40 <= rv <= 55:
            checks["RSI"] = ("PASS", f"RSI {round(rv,1)} — in healthy pullback zone (40-55) — not oversold, not overbought")
        elif rv < 40:
            checks["RSI"] = ("WARN", f"RSI {round(rv,1)} — oversold, could bounce but check for further weakness")
        elif rv > 70:
            checks["RSI"] = ("WARN", f"RSI {round(rv,1)} — overbought — chasing risk high, wait for pullback")
        else:
            checks["RSI"] = ("PARTIAL", f"RSI {round(rv,1)} — acceptable zone (55-70), momentum still positive")

        # 7. Volume
        vRatio = r["Volume"] / r["vSMA"] if r["vSMA"] > 0 else 0
        if vRatio >= 2.0:
            checks["Volume"] = ("PASS", f"Volume surge {round(vRatio,1)}x average — institutional activity confirmed")
        elif vRatio < 0.7:
            checks["Volume"] = ("PASS", f"Volume declining ({round(vRatio,1)}x avg) during pullback — healthy, no panic selling")
        elif vRatio >= 1.5:
            checks["Volume"] = ("PARTIAL", f"Volume {round(vRatio,1)}x avg — elevated but not full surge yet")
        else:
            checks["Volume"] = ("WARN", f"Volume {round(vRatio,1)}x avg — average/below average, lacks strong conviction")

        # 8. OBV accumulation
        if r["obv"] > r["obvE"]:
            checks["OBV"] = ("PASS", "OBV above its 21 EMA — institutional accumulation ongoing, smart money holding")
        else:
            checks["OBV"] = ("FAIL", "OBV below 21 EMA — distribution phase, institutions may be selling into rallies")

        # 9. CVD (order flow proxy)
        if r["cvd"] > r["cvdE"]:
            checks["CVD (Order Flow)"] = ("PASS", "Cumulative delta positive — aggressive buyers outweighing sellers")
        else:
            checks["CVD (Order Flow)"] = ("FAIL", "Cumulative delta negative — sellers in control of order flow")

        # ── Risk flag analysis ────────────────────────────────────
        risk_flags = []
        if meta["tier"] == "small":
            risk_flags.append("Small-cap: circuit filter risk, low liquidity — reduce position size")
        if meta["risk"]:
            risk_flags.append(meta["risk"])

        # Additional auto-detected risk flags
        swing_range_pct = (r["swR"] / r["swH"]) * 100 if r["swH"] > 0 else 0
        if swing_range_pct > 40:
            risk_flags.append(f"Stock moved {round(swing_range_pct,0)}% in last 20 days — extended, reversal risk higher")

        atr_pct = (r["atr"] / c) * 100 if c > 0 else 0
        if atr_pct > 5:
            risk_flags.append(f"High volatility: ATR is {round(atr_pct,1)}% of price — wide stops needed")

        # ── Score calculation ─────────────────────────────────────
        score = 0
        pass_map = {"Trend": 2, "Weekly CPR Width": 1, "Weekly CPR Position": 1,
                    "Monthly CPR": 1, "Fibonacci Zone": 2, "RSI": 1, "OBV": 1, "CVD (Order Flow)": 1}
        for k, w in pass_map.items():
            if checks.get(k, ("FAIL",))[0] == "PASS":
                score += w
            elif checks.get(k, ("FAIL",))[0] == "PARTIAL":
                score += max(0, w - 1)

        # ── Distance to Fib entry zone (key new metric) ─────────
        dist_to_f618_pct = round(((c - f618) / c) * 100, 1)   # +ve = above zone, -ve = below zone
        near_zone = abs(dist_to_f618_pct) <= 3.0               # within 3% of golden pocket

        # ── Verdict logic ─────────────────────────────────────────
        trend_ok     = checks["Trend"][0] in ("PASS","PARTIAL")
        cpr_pos_ok   = checks["Weekly CPR Position"][0] == "PASS"
        cpr_pos_warn = checks["Weekly CPR Position"][0] == "WARN"
        fib_ok       = checks["Fibonacci Zone"][0] == "PASS"
        obv_ok       = checks["OBV"][0] == "PASS"
        cvd_ok       = checks["CVD (Order Flow)"][0] == "PASS"
        rsi_ok       = checks["RSI"][0] in ("PASS","PARTIAL")
        has_high_risk= any("HIGH" in f for f in risk_flags)

        confirmation_level = None

        if has_high_risk:
            verdict     = "AVOID"
            verdict_why = f"High regulatory/structural risk. {risk_flags[0]}"

        elif not trend_ok:
            verdict     = "SKIP"
            verdict_why = f"No uptrend structure. Price below key EMAs. Wait for trend to establish."

        elif score >= 8 and cpr_pos_ok and fib_ok and obv_ok:
            verdict     = "BUY NOW"
            verdict_why = "All major layers confirmed. Enter at market open or limit order near current price."

        elif score >= 7 and fib_ok and obv_ok and (cpr_pos_ok or cpr_pos_warn):
            verdict     = "BUY NOW"
            verdict_why = "Strong confluence (7+ score, Fib zone, accumulation). CPR partially aligned — acceptable entry."

        elif score >= 6 and near_zone and obv_ok and trend_ok:
            verdict     = "NEAR ENTRY"
            confirmation_level = round(f618, 2)
            verdict_why = (f"Price is {abs(dist_to_f618_pct)}% away from Fib 0.618 zone (₹{round(f618,2)}). "
                           f"Set a limit buy at ₹{round(f618,2)}. Stock likely to reach this level within 1-3 days.")

        elif score >= 6 and cpr_pos_warn and fib_ok:
            verdict     = "WAIT FOR CONFIRMATION"
            confirmation_level = round(wTC, 2) if not pd.isna(wTC) else None
            verdict_why = (f"Price in Fib zone but below Weekly CPR TC ₹{confirmation_level}. "
                           f"Wait for a daily close ABOVE ₹{confirmation_level} with volume before entering.")

        elif score >= 6 and not fib_ok and trend_ok:
            verdict     = "WAIT FOR PULLBACK"
            confirmation_level = round(f618, 2)
            verdict_why = (f"Setup looks strong but price ₹{round(c,2)} is {dist_to_f618_pct}% above entry zone. "
                           f"Wait for pullback to ₹{confirmation_level} (Fib 0.618). "
                           f"Set a price alert at ₹{round(f618 * 1.02, 2)} to get ready.")

        elif score >= 4:
            verdict     = "SKIP"
            verdict_why = "Only partial confirmation across layers. Risk/reward not favorable enough."

        else:
            verdict     = "SKIP"
            verdict_why = "Too few conditions confirmed. No trade setup."

        # ── Stop loss and targets ─────────────────────────────────
        sl  = min(r["swL"], r["f786"]) - r["atr"] * 0.5
        sl  = round(sl, 2)
        tp1 = round(c + (c - sl) * 2.0, 2)
        tp2 = round(c + (c - sl) * 3.0, 2)
        rr1 = round((tp1 - c) / (c - sl), 2) if c > sl else 0

        # ── Position sizing ───────────────────────────────────────
        grade    = "A+" if score >= 8 else "A" if score >= 6 else "B" if score >= 4 else "SKIP"
        risk_pct = RISK_PCT_APLUS if grade == "A+" else RISK_PCT_A
        risk_amt = CAPITAL * (risk_pct / 100)
        rps      = c - sl
        shares   = int(risk_amt / rps) if rps > 0 else 0
        pos_val  = round(shares * c, 0)

        return {
            "symbol"     : symbol,
            "sector"     : meta["sector"],
            "tier"       : meta["tier"],
            "score"      : score,
            "grade"      : grade,
            "verdict"    : verdict,
            "verdict_why": verdict_why,
            "checks"     : checks,
            "risk_flags" : risk_flags,
            "close"      : round(c, 2),
            "sl"         : sl,
            "tp1"        : tp1,
            "tp2"        : tp2,
            "rr"         : rr1,
            "atr"        : round(r["atr"], 2),
            "rsi"        : round(r["rsi"], 1),
            "shares"     : shares,
            "pos_val"    : pos_val,
            "risk_amt"   : round(risk_amt, 0),
            "risk_pct"   : risk_pct,
            "confirm_at" : confirmation_level,
            "f618"       : round(f618, 2),
            "f786"       : round(f786, 2),
            "f127"       : round(r["f127"], 2),
            "f161"       : round(r["f161"], 2),
            "wTC"        : round(wTC, 2) if not pd.isna(wTC) else "N/A",
            "wBC"        : round(wBC, 2) if not pd.isna(wBC) else "N/A",
        }
    except Exception as e:
        return None

# ─────────────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────────────

ICONS = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "PARTIAL": "⚡"}
VERDICT_ICONS = {
    "BUY NOW"              : "🏆",
    "NEAR ENTRY"           : "🎯",
    "WAIT FOR CONFIRMATION": "⏳",
    "WAIT FOR PULLBACK"    : "🔄",
    "WATCHLIST"            : "👀",
    "SKIP"                 : "⏭️ ",
    "AVOID"                : "🚫",
}

def print_analysis(r):
    grade   = r["grade"]
    verdict = r["verdict"]
    vicon   = VERDICT_ICONS.get(verdict, "")
    gicon   = "🏆" if grade == "A+" else "✅" if grade == "A" else "⚡"

    print(f"\n  {'═'*62}")
    print(f"  {gicon} {r['symbol']:<14}  |  Sector: {r['sector']}  ({r['tier'].upper()} CAP)")
    print(f"  {'═'*62}")
    print(f"  Score: {r['score']}/10   Grade: {grade}   RSI: {r['rsi']}   ATR: ₹{r['atr']}")
    print(f"  {'─'*62}")

    # Factor checks
    print(f"  ANALYSIS:")
    for factor, (status, reason) in r["checks"].items():
        icon = ICONS.get(status, "?")
        print(f"    {icon}  {factor:<22}  {reason}")

    # Risk flags
    if r["risk_flags"]:
        print(f"\n  RISK FLAGS:")
        for rf in r["risk_flags"]:
            print(f"    🔴  {rf}")

    # Trade levels
    print(f"\n  TRADE LEVELS:")
    print(f"    Entry     :  ₹{r['close']}")
    print(f"    Stop Loss :  ₹{r['sl']}  (structural SL)")
    print(f"    Target 1  :  ₹{r['tp1']}  (R:R 1:{r['rr']}) — Book 50% here")
    print(f"    Target 2  :  ₹{r['tp2']}  (R:R 1:{r['rr']+1.0:.1f}) — Trail rest")
    print(f"    Fib 0.618 :  ₹{r['f618']}  |  Fib 0.786: ₹{r['f786']}")
    print(f"    Fib 1.272 :  ₹{r['f127']}  |  Fib 1.618: ₹{r['f161']}")
    print(f"    Weekly CPR:  TC: ₹{r['wTC']}  BC: ₹{r['wBC']}")

    # Position size
    print(f"\n  POSITION SIZING  (Capital: ₹{CAPITAL:,}  |  Risk: {r['risk_pct']}%)")
    print(f"    Risk Amount  :  ₹{r['risk_amt']:,.0f}")
    print(f"    Shares to Buy:  {r['shares']} shares")
    print(f"    Position Size:  ₹{r['pos_val']:,.0f}")

    # Verdict
    print(f"\n  VERDICT: {vicon} {verdict}")
    print(f"  {r['verdict_why']}")
    if r["confirm_at"]:
        print(f"  → Confirmation level: Wait for daily close above ₹{r['confirm_at']}")

def print_summary_table(results):
    buynow    = [r for r in results if r["verdict"] == "BUY NOW"]
    nearentry = [r for r in results if r["verdict"] == "NEAR ENTRY"]
    waitconf  = [r for r in results if r["verdict"] == "WAIT FOR CONFIRMATION"]
    waitpull  = [r for r in results if r["verdict"] == "WAIT FOR PULLBACK"]
    watchlist = [r for r in results if r["verdict"] == "WATCHLIST"]
    skips     = [r for r in results if r["verdict"] in ("SKIP","AVOID")]

    print(f"\n\n  {'█'*62}")
    print(f"  FINAL RANKED DECISION TABLE")
    print(f"  {'█'*62}")
    print(f"  {'Stock':<14} {'Score':>5} {'Grade':>5}  {'Verdict':<26} {'Entry':>8} {'SL':>8} {'TP1':>8}  {'R:R'}")
    print(f"  {'─'*80}")

    for group, label in [
        (buynow,    "── 🏆 BUY NOW (Immediate Execution) ────────────────────"),
        (nearentry, "── 🎯 NEAR ENTRY (Within 2-3% of Fib Golden Pocket) ────"),
        (waitconf,  "── ⏳ WAIT FOR CONFIRMATION (Breakout/Close Needed) ─────"),
        (waitpull,  "── 🔄 WAIT FOR PULLBACK (Extended, Needs Retracement) ───"),
        (watchlist, "── 👀 WATCHLIST (Developing Setups) ────────────────────"),
        (skips,     "── 🚫 SKIP / AVOID ──────────────────────────────────────"),
    ]:
        if group:
            print(f"\n  {label}")
            for r in sorted(group, key=lambda x: x["score"], reverse=True):
                vicon = VERDICT_ICONS.get(r["verdict"], "")
                print(f"  {vicon} {r['symbol']:<13} {r['score']:>5}/10  {r['grade']:>5}  "
                      f"{r['verdict']:<26} ₹{r['close']:>8.2f} ₹{r['sl']:>8.2f} ₹{r['tp1']:>8.2f}  1:{r['rr']}")

    print(f"\n  {'─'*80}")
    print(f"  SUMMARY: {len(buynow)} BUY NOW  |  "
          f"{len(nearentry)} NEAR ENTRY  |  "
          f"{len(waitconf)} WAIT CONFIRM  |  "
          f"{len(waitpull)} WAIT PULLBACK  |  "
          f"{len(watchlist)} WATCHLIST  |  "
          f"{len(skips)} SKIP/AVOID")

    actionable = buynow + nearentry
    if actionable:
        print(f"\n  ⚡ TOP ACTIONABLE PICKS ({len(actionable)} stocks):")
        total_risk = 0
        for r in actionable:
            total_risk += r["risk_amt"]
            target_entry = r["confirm_at"] if r["verdict"] == "NEAR ENTRY" and r["confirm_at"] else r["close"]
            print(f"    ★  {r['symbol']} ({r['verdict']}): Entry target ₹{target_entry} | {r['shares']} shares | "
                  f"SL ₹{r['sl']} | TP1 ₹{r['tp1']} | Risk ₹{r['risk_amt']:,.0f}")
        print(f"\n    Total planned risk: ₹{total_risk:,.0f} "
              f"({round(total_risk/CAPITAL*100,2)}% of capital)")

# ─────────────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────────────

def run_deep_scan(universe=None):
    if universe is None:
        universe = FULL_NIFTY500 if FULL_NIFTY500 else UNIVERSE

    print("\n" + "█"*65)
    print("  🇮🇳  GOD SWING DEEP ANALYSIS SCANNER v2.0")
    print(f"  📅  {datetime.now().strftime('%A, %d %B %Y  %I:%M %p IST')}")
    print(f"  💰  Capital: ₹{CAPITAL:,}  |  Universe: {len(universe)} NIFTY 500 stocks")
    print(f"  ⚡  Multi-threaded scanner ({NUM_THREADS} workers active)...")
    print("█"*65 + "\n")

    results = []
    completed = 0
    total = len(universe)

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        future_to_stock = {
            executor.submit(analyse_stock, sym, meta): sym
            for sym, meta in universe.items()
        }
        for future in as_completed(future_to_stock):
            completed += 1
            sym = future_to_stock[future]
            try:
                r = future.result()
                if r and r["score"] >= MIN_SCORE:
                    results.append(r)
            except Exception:
                pass

            if completed % 50 == 0 or completed == total:
                print(f"  ... {completed}/{total} stocks scanned | {len(results)} candidate signals")

    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)

    # Print deep analysis for top A+ and A only (limit verbose output to top 15 to keep terminal clean)
    top = [r for r in results if r["grade"] in ("A+","A")]
    print(f"\n\n  ════ DEEP ANALYSIS — TOP {min(15, len(top))} OF {len(top)} SIGNALS ════\n")

    for r in top[:15]:
        print_analysis(r)

    # Print full summary table of all A/A+ setups across Nifty 500
    print_summary_table(top)

    # Save CSV
    os.makedirs("signals", exist_ok=True)
    rows = []
    for r in results:
        row = {k: v for k, v in r.items() if k not in ("checks",)}
        row["risk_flags"] = " | ".join(r["risk_flags"]) if r["risk_flags"] else "None"
        rows.append(row)
    pd.DataFrame(rows).to_csv("signals/deep_analysis.csv", index=False)
    print(f"\n\n  💾 Full {len(results)} signals saved to: signals/deep_analysis.csv")
    print("█"*65 + "\n")

    return results

if __name__ == "__main__":
    run_deep_scan()
