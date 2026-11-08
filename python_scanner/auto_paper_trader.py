"""
GOD SWING — AUTONOMOUS PAPER TRADING ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Automatically runs at 4:00 PM IST on market days:
  1. Updates all OPEN paper positions (checks SL, TP1, TP2 vs today's High/Low).
  2. Scans all 501 Nifty 500 stocks using the 5-layer analysis engine.
  3. Enters new BUY NOW and NEAR ENTRY positions (allocating 1-1.5% risk).
  4. Saves portfolio state to 'paper_portfolio.json' and 'trade_history.csv'.
  5. Outputs a detailed Daily P&L and Open Positions report.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from swing_scanner_v2 import run_deep_scan, FULL_NIFTY500, CAPITAL, MAX_OPEN_TRADES
from telegram_notifier import send_telegram_message, format_daily_alert

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "signals", "paper_portfolio.json")
HISTORY_FILE   = os.path.join(os.path.dirname(__file__), "signals", "paper_trade_history.csv")
DAILY_LOG_FILE = os.path.join(os.path.dirname(__file__), "signals", "daily_paper_report.log")

DEFAULT_PORTFOLIO = {
    "initial_capital": CAPITAL,
    "cash_balance": CAPITAL,
    "realized_pnl": 0.0,
    "open_positions": {},  # { "SYMBOL": { entry, sl, tp1, tp2, shares, date, ... } }
    "closed_positions": []
}

def load_portfolio():
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PORTFOLIO.copy()

def save_portfolio(p):
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(p, f, indent=2)

def log_trade_history(trade_record):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    df_new = pd.DataFrame([trade_record])
    if os.path.exists(HISTORY_FILE):
        df_new.to_csv(HISTORY_FILE, mode='a', header=False, index=False)
    else:
        df_new.to_csv(HISTORY_FILE, mode='w', header=True, index=False)

def is_market_open_today():
    """
    Checks if today is a regular market day or special Muhurat trading session.
    Returns: (is_market_day, can_execute, session_title)
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    MUHURAT_DATES = ["2026-11-08"]
    force = os.getenv("FORCE_EXECUTE", "").lower() in ["1", "true"]
    is_muhurat = (today_str in MUHURAT_DATES) or (os.getenv("FORCE_MUHURAT", "").lower() in ["1", "true"])

    if is_muhurat:
        # Muhurat market normal hours: 2:20 PM to 3:30 PM IST (Closing session up to 3:45 PM IST)
        utc_now = datetime.utcnow()
        ist_minutes = (utc_now.hour * 60 + utc_now.minute + 330) % 1440
        ist_time_dec = ist_minutes / 60.0

        if force or ist_time_dec >= 15.5:  # Post-Muhurat close (3:30 PM IST onwards)
            return True, True, "🪔 Diwali Muhurat Trading Session (Samvat 2083) - Post-Market Execution"
        elif ist_time_dec >= 14.33:        # In-session (2:20 PM to 3:30 PM IST)
            return True, True, "🪔 Diwali Muhurat Trading Session (Samvat 2083) - Live Session Execution"
        else:
            return True, False, "🪔 Diwali Muhurat Trading Session (Samvat 2083) - Pre-Market (Opens 2:20 PM IST)"

    weekday = datetime.now().weekday()
    if weekday in [5, 6] and not force:
        return False, False, "Market Closed (Weekend)"

    return True, True, "Regular Market Session"

def update_open_positions(portfolio, actions_taken=None):
    """Checks today's High, Low, Close for all open positions and triggers exits."""
    open_pos = portfolio["open_positions"]
    if not open_pos:
        print("  ℹ️  No existing open positions to update.")
        return

    is_market_day, can_execute, session_title = is_market_open_today()
    if not is_market_day or not can_execute:
        print(f"  ⏸️ {session_title}. Skipping live exit checks.")
        return

    print(f"\n  🔍 Monitoring {len(open_pos)} Open Positions against today's prices...")
    symbols_to_close = []

    for sym, pos in list(open_pos.items()):
        ticker = sym + ".NS"
        h, l, c = None, None, None

        # 1. Primary: Try official Angel One SmartAPI Feed (0 delay, zero rate-limiting)
        try:
            from angel_feed import get_live_ltp
            quote = get_live_ltp(sym)
            if quote and quote.get("high", 0) > 0:
                h = quote["high"]
                l = quote["low"]
                c = quote["close"]
        except Exception:
            pass

        # 2. Secondary Fallback: yfinance
        if h is None:
            try:
                df = yf.download(ticker, period="5d", interval="1d", auto_adjust=True, progress=False)
                if df is not None and len(df) > 0:
                    df.columns = df.columns.droplevel(1) if isinstance(df.columns, pd.MultiIndex) else df.columns
                    today = df.iloc[-1]
                    h = float(today["High"])
                    l = float(today["Low"])
                    c = float(today["Close"])
            except Exception:
                continue

        if h is None:
            continue

        try:
            entry = float(pos["entry"])
            sl    = float(pos["sl"])
            tp1   = float(pos["tp1"])
            tp2   = float(pos["tp2"])
            shares = int(pos["shares"])

            # 1. Stop Loss Hit
            if l <= sl:
                exit_price = min(entry, sl) # conservative execution
                pnl = (exit_price - entry) * shares
                portfolio["cash_balance"] += (exit_price * shares)
                portfolio["realized_pnl"] += pnl
                symbols_to_close.append((sym, "STOP_LOSS", exit_price, pnl))
                if actions_taken is not None:
                    actions_taken.append(f"❌ <b>STOP LOSS HIT {sym}</b>: Exit @ ₹{exit_price:,.2f} | P&L: ₹{pnl:+,.2f}")
                print(f"  ❌ STOP LOSS HIT on {sym}: Exit ₹{exit_price:.2f} | P&L: ₹{pnl:,.2f}")

            # 2. TP1 Hit (Partial 50% Profit Booking)
            elif h >= tp1 and not pos.get("tp1_booked", False):
                half_shares = shares // 2
                pos["shares"] -= half_shares
                pos["tp1_booked"] = True
                pos["sl"] = entry # Move SL to Break-Even!
                pnl = (tp1 - entry) * half_shares
                portfolio["cash_balance"] += (tp1 * half_shares)
                portfolio["realized_pnl"] += pnl
                if actions_taken is not None:
                    actions_taken.append(f"🎉 <b>TARGET 1 HIT {sym}</b>: Booked 50% ({half_shares} shs) @ ₹{tp1:,.2f} | P&L: +₹{pnl:,.2f} (SL to BE)")
                print(f"  🎉 TARGET 1 HIT on {sym}: Booked 50% ({half_shares} shares) at ₹{tp1:.2f} | P&L: +₹{pnl:,.2f} | SL moved to Entry ₹{entry:.2f}")
                log_trade_history({
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Symbol": sym,
                    "Action": "PARTIAL_TP1",
                    "Price": tp1,
                    "Shares": half_shares,
                    "Realized_PnL": round(pnl, 2),
                    "Notes": "50% booked at TP1, trailing remaining to TP2"
                })

            # 3. TP2 Hit (Exit remaining 50%)
            elif h >= tp2 and pos.get("tp1_booked", False):
                rem_shares = pos["shares"]
                pnl = (tp2 - entry) * rem_shares
                portfolio["cash_balance"] += (tp2 * rem_shares)
                portfolio["realized_pnl"] += pnl
                symbols_to_close.append((sym, "TARGET_2", tp2, pnl))
                if actions_taken is not None:
                    actions_taken.append(f"🏆 <b>TARGET 2 HIT {sym}</b>: Full Exit @ ₹{tp2:,.2f} | P&L: +₹{pnl:,.2f}")
                print(f"  🏆 TARGET 2 HIT on {sym}: Full Exit at ₹{tp2:.2f} | P&L: +₹{pnl:,.2f}")

        except Exception as e:
            print(f"  ⚠️ Error updating {sym}: {e}")

    for sym, reason, exit_price, pnl in symbols_to_close:
        pos = open_pos.pop(sym)
        record = {
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Symbol": sym,
            "Action": f"CLOSE_{reason}",
            "Entry": pos["entry"],
            "Exit": exit_price,
            "Shares": pos["shares"],
            "Realized_PnL": round(pnl, 2),
            "Notes": f"Closed via {reason}"
        }
        portfolio["closed_positions"].append(record)
        log_trade_history(record)

def take_new_paper_trades(portfolio, scan_results, actions_taken=None):
    """Takes simulated paper trade entries on BUY NOW and NEAR ENTRY signals."""
    open_pos = portfolio["open_positions"]
    slots_available = MAX_OPEN_TRADES - len(open_pos)

    if slots_available <= 0:
        print(f"  ⚠️ Max open positions ({MAX_OPEN_TRADES}) reached. No new trades taken today.")
        return

    # Filter actionable picks: BUY NOW first, then NEAR ENTRY
    buynow_picks = [r for r in scan_results if r["verdict"] == "BUY NOW" and r["symbol"] not in open_pos]
    near_picks   = [r for r in scan_results if r["verdict"] == "NEAR ENTRY" and r["symbol"] not in open_pos]
    candidates = buynow_picks + near_picks

    print(f"\n  🎯 Found {len(candidates)} actionable candidates. Slots available: {slots_available}")

    is_market_day, can_execute, session_title = is_market_open_today()
    if not is_market_day:
        print(f"  ⏸️ {session_title}. All {len(candidates)} candidates are queued for Monday Market Open (9:15 AM IST).")
        return

    if not can_execute:
        print(f"  🪔 {session_title}. Top {min(slots_available, len(candidates))} candidates queued for Muhurat Trading Session at 2:20 PM IST.")
        return

    for r in candidates[:slots_available]:
        sym = r["symbol"]
        price = r["confirm_at"] if r["verdict"] == "NEAR ENTRY" and r["confirm_at"] else r["close"]
        shares = r["shares"]
        cost = price * shares

        if cost > portfolio["cash_balance"]:
            shares = int(portfolio["cash_balance"] / price)
            cost = price * shares

        if shares <= 0:
            print(f"  ⚠️ Insufficient cash to buy {sym}.")
            continue

        portfolio["cash_balance"] -= cost
        pos_record = {
            "symbol": sym,
            "verdict": r["verdict"],
            "entry": price,
            "sl": r["sl"],
            "tp1": r["tp1"],
            "tp2": r["tp2"],
            "shares": shares,
            "cost": round(cost, 2),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "score": r["score"],
            "tp1_booked": False
        }
        open_pos[sym] = pos_record
        if actions_taken is not None:
            actions_taken.append(f"✅ <b>BOUGHT {sym}</b>: {shares} shares @ ₹{price:,.2f} (Allocated: ₹{cost:,.2f} | SL: ₹{r['sl']} | TP1: ₹{r['tp1']})")
        print(f"  ✅ EXECUTED PAPER BUY: {sym} | {shares} shares @ ₹{price:.2f} | Total ₹{cost:,.2f} | SL: ₹{r['sl']} | TP1: ₹{r['tp1']}")

        log_trade_history({
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Symbol": sym,
            "Action": f"BUY_{r['verdict']}",
            "Entry": price,
            "Exit": None,
            "Shares": shares,
            "Realized_PnL": 0.0,
            "Notes": f"Score {r['score']}/10, SL: ₹{r['sl']}"
        })

def print_portfolio_summary(portfolio):
    cash = portfolio["cash_balance"]
    realized = portfolio["realized_pnl"]
    open_pos = portfolio["open_positions"]

    # Calculate unrealized PnL
    invested = 0.0
    current_val = 0.0
    for sym, pos in open_pos.items():
        invested += pos["cost"]
        c = None
        try:
            from angel_feed import get_live_ltp
            quote = get_live_ltp(sym)
            if quote and quote.get("ltp", 0) > 0:
                c = float(quote["ltp"])
        except Exception:
            pass

        if c is not None:
            current_val += c * pos["shares"]
        else:
            try:
                df = yf.download(sym + ".NS", period="1d", auto_adjust=True, progress=False)
                if df is not None and len(df) > 0:
                    c = float(df.iloc[-1]["Close"])
                    current_val += c * pos["shares"]
                else:
                    current_val += pos["cost"]
            except Exception:
                current_val += pos["cost"]

    unrealized = current_val - invested
    total_equity = cash + current_val
    total_return_pct = ((total_equity - portfolio["initial_capital"]) / portfolio["initial_capital"]) * 100

    report = f"""
  {'█'*65}
  💼 PAPER TRADING PORTFOLIO SNAPSHOT
  {'█'*65}
  Initial Capital   : ₹{portfolio['initial_capital']:,.2f}
  Cash Balance      : ₹{cash:,.2f}
  Active Invested   : ₹{invested:,.2f}
  Current Value     : ₹{current_val:,.2f}
  Unrealized P&L    : ₹{unrealized:+,.2f}
  Realized P&L      : ₹{realized:+,.2f}
  Total Portfolio   : ₹{total_equity:,.2f} ({total_return_pct:+.2f}%)
  Open Positions    : {len(open_pos)} / {MAX_OPEN_TRADES}
  {'─'*65}
"""
    print(report)
    with open(DAILY_LOG_FILE, "a") as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n" + report + "\n")

def run_auto_paper_trading():
    print("\n" + "█"*65)
    print("  🤖 AUTONOMOUS PAPER TRADING ROBOT ACTIVATED")
    print(f"  📅 {datetime.now().strftime('%A, %d %B %Y  %I:%M %p IST')}")
    print("█"*65)

    portfolio = load_portfolio()
    actions_taken = []

    # Step 1: Manage and update existing open positions
    update_open_positions(portfolio, actions_taken)

    # Step 2: Run fresh 501-stock scan to find today's actionable setups
    print("\n  🚀 Running full 501 Nifty 500 Market Scan...")
    scan_results = run_deep_scan(FULL_NIFTY500)

    # Step 3: Take simulated entries
    take_new_paper_trades(portfolio, scan_results, actions_taken)

    # Step 4: Save & display state
    save_portfolio(portfolio)
    print_portfolio_summary(portfolio)
    print("  💾 State saved to paper_portfolio.json & paper_trade_history.csv")

    # Step 5: Send Telegram alert
    try:
        top_candidates = [r for r in scan_results if r["verdict"] in ("BUY NOW", "NEAR ENTRY")]
        tg_msg = format_daily_alert("IN", portfolio, actions_taken, top_candidates)
        send_telegram_message(tg_msg)
    except Exception as e:
        print(f"  ⚠️ Telegram dispatch error: {e}")

if __name__ == "__main__":
    run_auto_paper_trading()
