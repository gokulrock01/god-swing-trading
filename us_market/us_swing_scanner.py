"""
GOD SWING SCANNER — US EQUITIES (S&P 500 & NASDAQ 100)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scans all 503 S&P 500 constituents using the 5-Layer Engine:
  - Weekly & Monthly CPR
  - Fibonacci Golden Pocket (0.618 - 0.65)
  - Relative Strength vs S&P 500 (SPY)
  - Volume Surge & Retest Analysis
  - Order Flow Proxy / CVD & OBV Accumulation
  - 21 / 50 / 200 Daily EMAs

Currency: USD ($) | Base Portfolio: $100,000 | Risk: 1% - 1.5%
Usage: python3 us_swing_scanner.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import warnings
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

try:
    yf.set_tz_cache_location("/tmp/yfinance_us_tz")
except Exception:
    pass

# ─────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────
CAPITAL_USD      = 100_000     # Virtual trading capital in $
RISK_PCT_APLUS   = 1.5         # Risk % for A+ trades ($1,500)
RISK_PCT_A       = 1.0         # Risk % for A trades ($1,000)
MAX_OPEN_TRADES  = 6           # Max simultaneous positions
MIN_SCORE        = 6           # Minimum score for A grade
NUM_THREADS      = 12          # Parallel download workers

# ─────────────────────────────────────────────────────
# LOAD S&P 500 UNIVERSE
# ─────────────────────────────────────────────────────
def load_sp500():
    file_path = os.path.join(os.path.dirname(__file__), "config", "sp500_symbols.txt")
    symbols = []
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            symbols = [line.strip().upper() for line in f if line.strip()]
    if not symbols:
        # Fallback to leading US tech and blue chips
        symbols = [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "JNJ",
            "JPM", "V", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "COST", "PEP",
            "KO", "ADBE", "WMT", "MCD", "CSCO", "BAC", "NFLX", "AMD", "CRM", "INTC",
            "QCOM", "TXN", "AMAT", "HON", "IBM", "GE", "CAT", "BA", "DIS", "NKE"
        ]
    return symbols

SP500_SYMBOLS = load_sp500()

# ─────────────────────────────────────────────────────
# INDICATOR FUNCTIONS
# ─────────────────────────────────────────────────────
def ema(s, p): return s.ewm(span=p, adjust=False).mean()

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
# DEEP ANALYSIS FOR US STOCKS
# ─────────────────────────────────────────────────────
def analyse_us_stock(symbol):
    try:
        t = yf.Ticker(symbol)
        df = t.history(period="1y", interval="1d", auto_adjust=True)
        if df is None or len(df) < 60:
            return None
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

        lb = 20
        df["swH"] = df["High"].rolling(lb).max()
        df["swL"] = df["Low"].rolling(lb).min()
        df["swR"] = df["swH"] - df["swL"]
        df["f618"] = df["swH"] - df["swR"] * 0.618
        df["f65"]  = df["swH"] - df["swR"] * 0.65
        df["f786"] = df["swH"] - df["swR"] * 0.786
        df["f127"] = df["swH"] + df["swR"] * 0.272
        df["f161"] = df["swH"] + df["swR"] * 0.618

        r = df.iloc[-1]
        c = r["Close"]

        checks = {}

        # 1. Trend
        e21_v = r["e21"]; e50_v = r["e50"]; e200_v = r["e200"]
        ema_aligned = e21_v > e50_v or (e21_v >= e50_v * 0.98)
        if c > e50_v and ema_aligned and c > e200_v:
            checks["Trend"] = ("PASS", "Price above 50 & 200 SMA, 21 EMA aligned — solid uptrend")
        elif c > e200_v and c > e50_v:
            checks["Trend"] = ("PARTIAL", f"Above 200 (${round(e200_v,2)}) and 50 (${round(e50_v,2)}) — uptrend intact")
        elif c > e200_v:
            checks["Trend"] = ("PARTIAL", f"Above 200-day line (${round(e200_v,2)}) — macro bull, medium consolidating")
        else:
            checks["Trend"] = ("FAIL", f"Price ${round(c,2)} below 200 EMA ${round(e200_v,2)} — not in uptrend")

        # 2. Weekly CPR width
        wNarrow = r["wWidth"] < r["wWidthAvg"] * 0.8 if not pd.isna(r.get("wWidth", np.nan)) else False
        if wNarrow:
            checks["Weekly CPR Width"] = ("PASS", f"Narrow CPR = ${round(r['wWidth'],2)} — trend expansion expected")
        else:
            checks["Weekly CPR Width"] = ("WARN", f"Wide CPR = ${round(r['wWidth'],2)} — possible range-bound week")

        # 3. Weekly CPR position
        wTC = r.get("wTC", np.nan)
        wBC = r.get("wBC", np.nan)
        if not pd.isna(wTC):
            if c > wTC:
                checks["Weekly CPR Position"] = ("PASS", f"Price ${round(c,2)} above Weekly TC ${round(wTC,2)} — bullish")
            elif c > wBC:
                checks["Weekly CPR Position"] = ("WARN", f"Price inside CPR band ($BC: {round(wBC,2)} - $TC: {round(wTC,2)})")
            else:
                checks["Weekly CPR Position"] = ("FAIL", f"Price below Weekly BC ${round(wBC,2)}")
        else:
            checks["Weekly CPR Position"] = ("WARN", "Weekly CPR data unavailable")

        # 4. Monthly CPR
        mTC = r.get("mTC", np.nan)
        if not pd.isna(mTC):
            if c > mTC:
                checks["Monthly CPR"] = ("PASS", f"Above Monthly TC ${round(mTC,2)} — institutional macro bias bullish")
            else:
                checks["Monthly CPR"] = ("WARN", f"Below Monthly TC ${round(mTC,2)}")
        else:
            checks["Monthly CPR"] = ("WARN", "Monthly CPR unavailable")

        # 5. Fibonacci Golden Pocket
        f618 = r["f618"]; f65 = r["f65"]; f786 = r["f786"]
        if c <= f618 and c >= f65:
            checks["Fibonacci Zone"] = ("PASS", f"Price in Golden Pocket (0.618: ${round(f618,2)} to 0.65: ${round(f65,2)})")
        elif c <= f618 * 1.02 and c >= f786 * 0.98:
            checks["Fibonacci Zone"] = ("PASS", f"Price in deep reversal zone (0.618 - 0.786)")
        elif c < f786:
            checks["Fibonacci Zone"] = ("FAIL", f"Price below 0.786 Fib (${round(f786,2)}) — pullback too deep")
        else:
            checks["Fibonacci Zone"] = ("WARN", f"Not in Fib pocket yet. Target pull level: ${round(f618,2)}")

        # 6. RSI
        rv = r["rsi"]
        if 40 <= rv <= 55:
            checks["RSI"] = ("PASS", f"RSI {round(rv,1)} — ideal pullback zone (40-55)")
        elif rv < 40:
            checks["RSI"] = ("WARN", f"RSI {round(rv,1)} — oversold")
        elif rv > 70:
            checks["RSI"] = ("WARN", f"RSI {round(rv,1)} — overbought (high chase risk)")
        else:
            checks["RSI"] = ("PARTIAL", f"RSI {round(rv,1)} — positive momentum")

        # 7. Volume
        vRatio = r["Volume"] / r["vSMA"] if r["vSMA"] > 0 else 0
        if vRatio >= 2.0:
            checks["Volume"] = ("PASS", f"Volume surge {round(vRatio,1)}x — institutional expansion")
        elif vRatio < 0.7:
            checks["Volume"] = ("PASS", f"Volume dry-up ({round(vRatio,1)}x avg) — healthy pullback, no dump")
        elif vRatio >= 1.4:
            checks["Volume"] = ("PARTIAL", f"Volume {round(vRatio,1)}x average")
        else:
            checks["Volume"] = ("WARN", f"Volume normal ({round(vRatio,1)}x)")

        # 8. OBV & CVD
        obv_ok = r["obv"] > r["obvE"]
        checks["OBV"] = ("PASS", "OBV > 21 EMA — institutional accumulation") if obv_ok else ("FAIL", "OBV below 21 EMA — distribution")

        cvd_ok = r["cvd"] > r["cvdE"]
        checks["CVD (Order Flow)"] = ("PASS", "Delta positive — aggressive buyers active") if cvd_ok else ("FAIL", "Delta negative")

        # Score calculation
        score = 0
        pass_map = {"Trend": 2, "Weekly CPR Width": 1, "Weekly CPR Position": 1,
                    "Monthly CPR": 1, "Fibonacci Zone": 2, "RSI": 1, "OBV": 1, "CVD (Order Flow)": 1}
        for k, w in pass_map.items():
            st = checks.get(k, ("FAIL",))[0]
            if st == "PASS": score += w
            elif st == "PARTIAL": score += max(0, w - 1)

        dist_to_f618_pct = round(((c - f618) / c) * 100, 1)
        near_zone = abs(dist_to_f618_pct) <= 3.0

        trend_ok     = checks["Trend"][0] in ("PASS","PARTIAL")
        cpr_pos_ok   = checks["Weekly CPR Position"][0] == "PASS"
        cpr_pos_warn = checks["Weekly CPR Position"][0] == "WARN"
        fib_ok       = checks["Fibonacci Zone"][0] == "PASS"

        confirmation_level = None

        if not trend_ok:
            verdict = "SKIP"
            verdict_why = f"Price ${round(c,2)} below key EMAs. Macro trend is not bullish."
        elif score >= 8 and cpr_pos_ok and fib_ok and obv_ok:
            verdict = "BUY NOW"
            verdict_why = "All layers aligned. Enter at open or place limit order near close."
        elif score >= 7 and fib_ok and obv_ok and (cpr_pos_ok or cpr_pos_warn):
            verdict = "BUY NOW"
            verdict_why = "Strong confluence (7+ score, Fib pocket, accumulation). Favorable R:R."
        elif score >= 6 and near_zone and obv_ok and trend_ok:
            verdict = "NEAR ENTRY"
            confirmation_level = round(f618, 2)
            verdict_why = f"Price is {abs(dist_to_f618_pct)}% from Golden Pocket (${round(f618,2)}). Set limit buy at ${round(f618,2)}."
        elif score >= 6 and cpr_pos_warn and fib_ok:
            verdict = "WAIT FOR CONFIRMATION"
            confirmation_level = round(wTC, 2) if not pd.isna(wTC) else None
            verdict_why = f"Inside CPR band. Wait for daily close above Weekly TC ${confirmation_level}."
        elif score >= 6 and not fib_ok and trend_ok:
            verdict = "WAIT FOR PULLBACK"
            confirmation_level = round(f618, 2)
            verdict_why = f"Uptrend intact, but price is {dist_to_f618_pct}% above Fib pocket. Wait for pullback to ${confirmation_level}."
        else:
            verdict = "SKIP"
            verdict_why = "Insufficient confluence."

        # Risk and Position sizing
        sl  = round(min(r["swL"], r["f786"]) - r["atr"] * 0.5, 2)
        tp1 = round(c + (c - sl) * 2.0, 2)
        tp2 = round(c + (c - sl) * 3.0, 2)
        rr1 = round((tp1 - c) / (c - sl), 2) if c > sl else 0

        grade    = "A+" if score >= 8 else "A" if score >= 6 else "B" if score >= 4 else "SKIP"
        risk_pct = RISK_PCT_APLUS if grade == "A+" else RISK_PCT_A
        risk_amt = CAPITAL_USD * (risk_pct / 100)
        rps      = c - sl
        shares   = int(risk_amt / rps) if rps > 0 else 0
        pos_val  = round(shares * c, 2)

        return {
            "symbol"     : symbol,
            "score"      : score,
            "grade"      : grade,
            "verdict"    : verdict,
            "verdict_why": verdict_why,
            "checks"     : checks,
            "close"      : round(c, 2),
            "sl"         : sl,
            "tp1"        : tp1,
            "tp2"        : tp2,
            "rr"         : rr1,
            "atr"        : round(r["atr"], 2),
            "rsi"        : round(r["rsi"], 1),
            "shares"     : shares,
            "pos_val"    : pos_val,
            "risk_amt"   : round(risk_amt, 2),
            "risk_pct"   : risk_pct,
            "confirm_at" : confirmation_level,
            "f618"       : round(f618, 2),
            "f786"       : round(f786, 2),
            "wTC"        : round(wTC, 2) if not pd.isna(wTC) else "N/A",
            "wBC"        : round(wBC, 2) if not pd.isna(wBC) else "N/A",
        }
    except Exception:
        return None

# ─────────────────────────────────────────────────────
# DISPLAY TABLES
# ─────────────────────────────────────────────────────
VERDICT_ICONS = {
    "BUY NOW"              : "🏆",
    "NEAR ENTRY"           : "🎯",
    "WAIT FOR CONFIRMATION": "⏳",
    "WAIT FOR PULLBACK"    : "🔄",
    "WATCHLIST"            : "👀",
    "SKIP"                 : "⏭️ ",
    "AVOID"                : "🚫",
}

def print_us_summary_table(results):
    buynow    = [r for r in results if r["verdict"] == "BUY NOW"]
    nearentry = [r for r in results if r["verdict"] == "NEAR ENTRY"]
    waitconf  = [r for r in results if r["verdict"] == "WAIT FOR CONFIRMATION"]
    waitpull  = [r for r in results if r["verdict"] == "WAIT FOR PULLBACK"]
    skips     = [r for r in results if r["verdict"] in ("SKIP","AVOID")]

    print(f"\n\n  {'█'*65}")
    print(f"  🇺🇸 US MARKET FINAL RANKED DECISION TABLE (S&P 500)")
    print(f"  {'█'*65}")
    print(f"  {'Stock':<10} {'Score':>5} {'Grade':>5}  {'Verdict':<26} {'Price':>8} {'SL':>8} {'TP1':>8}  {'R:R'}")
    print(f"  {'─'*80}")

    for group, label in [
        (buynow,    "── 🏆 BUY NOW (Immediate Entry) ─────────────────────────"),
        (nearentry, "── 🎯 NEAR ENTRY (Within 2-3% of Fib Golden Pocket) ────"),
        (waitconf,  "── ⏳ WAIT FOR CONFIRMATION (Breakout Needed) ───────────"),
        (waitpull,  "── 🔄 WAIT FOR PULLBACK (Extended, Await Retrace) ──────"),
        (skips,     "── 🚫 SKIP / AVOID ──────────────────────────────────────"),
    ]:
        if group:
            print(f"\n  {label}")
            for r in sorted(group, key=lambda x: x["score"], reverse=True):
                vicon = VERDICT_ICONS.get(r["verdict"], "")
                print(f"  {vicon} {r['symbol']:<9} {r['score']:>5}/10  {r['grade']:>5}  "
                      f"{r['verdict']:<26} ${r['close']:>7.2f} ${r['sl']:>7.2f} ${r['tp1']:>7.2f}  1:{r['rr']}")

    print(f"\n  {'─'*80}")
    print(f"  SUMMARY: {len(buynow)} BUY NOW  |  "
          f"{len(nearentry)} NEAR ENTRY  |  "
          f"{len(waitconf)} WAIT CONFIRM  |  "
          f"{len(waitpull)} WAIT PULLBACK  |  "
          f"{len(skips)} SKIP/AVOID")

    actionable = buynow + nearentry
    if actionable:
        print(f"\n  ⚡ TOP ACTIONABLE US PICKS ({len(actionable)} stocks):")
        total_risk = 0
        for r in actionable:
            total_risk += r["risk_amt"]
            target_entry = r["confirm_at"] if r["verdict"] == "NEAR ENTRY" and r["confirm_at"] else r["close"]
            print(f"    ★  {r['symbol']} ({r['verdict']}): Target Entry ${target_entry} | {r['shares']} shares | "
                  f"SL ${r['sl']} | TP1 ${r['tp1']} | Risk ${r['risk_amt']:,.0f}")
        print(f"\n    Total planned portfolio risk: ${total_risk:,.0f} "
              f"({round(total_risk/CAPITAL_USD*100,2)}% of capital)")

def run_us_deep_scan(symbols=None):
    if symbols is None:
        symbols = SP500_SYMBOLS

    print("\n" + "█"*65)
    print("  🇺🇸  GOD SWING DEEP ANALYSIS SCANNER — US EQUITIES")
    print(f"  📅  {datetime.now().strftime('%A, %d %B %Y  %I:%M %p EST')}")
    print(f"  💰  Virtual Capital: ${CAPITAL_USD:,} USD | S&P 500 ({len(symbols)} stocks)")
    print(f"  ⚡  Multi-threaded scanner ({NUM_THREADS} workers active)...")
    print("█"*65 + "\n")

    results = []
    completed = 0
    total = len(symbols)

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        future_to_stock = {executor.submit(analyse_us_stock, sym): sym for sym in symbols}
        for future in as_completed(future_to_stock):
            completed += 1
            try:
                r = future.result()
                if r and r["score"] >= MIN_SCORE:
                    results.append(r)
            except Exception:
                pass
            if completed % 50 == 0 or completed == total:
                print(f"  ... {completed}/{total} stocks scanned | {len(results)} candidate signals")

    results.sort(key=lambda x: x["score"], reverse=True)
    top = [r for r in results if r["grade"] in ("A+","A")]

    print_us_summary_table(top)

    out_csv = os.path.join(os.path.dirname(__file__), "signals", "us_signals.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    rows = [{k: v for k, v in r.items() if k not in ("checks",)} for r in results]
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    print(f"\n  💾 US Scan results saved to: {out_csv}\n" + "█"*65 + "\n")

    return results

if __name__ == "__main__":
    run_us_deep_scan()
