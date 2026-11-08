"""
GOD SWING — AUTONOMOUS US PAPER TRADING BOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Runs automatically at 4:15 PM EST (post-market close):
  1. Updates all OPEN US positions (checks SL, TP1, TP2).
  2. Runs 503-stock S&P 500 Deep Scan.
  3. Executes paper entries for BUY NOW and NEAR ENTRY picks.
  4. Manages $100,000 USD portfolio, saving to 'us_paper_portfolio.json'.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import pandas as pd
import yfinance as yf
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python_scanner"))
from us_swing_scanner import run_us_deep_scan, CAPITAL_USD, MAX_OPEN_TRADES
from telegram_notifier import send_telegram_message, format_daily_alert

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "signals", "us_paper_portfolio.json")
HISTORY_FILE   = os.path.join(os.path.dirname(__file__), "signals", "us_trade_history.csv")
DAILY_LOG_FILE = os.path.join(os.path.dirname(__file__), "signals", "us_daily_report.log")

DEFAULT_PORTFOLIO = {
    "initial_capital_usd": CAPITAL_USD,
    "cash_balance_usd": CAPITAL_USD,
    "realized_pnl_usd": 0.0,
    "open_positions": {},
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

def log_trade(record):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    df = pd.DataFrame([record])
    if os.path.exists(HISTORY_FILE):
        df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(HISTORY_FILE, mode='w', header=True, index=False)

def update_open_positions(portfolio):
    open_pos = portfolio["open_positions"]
    if not open_pos:
        print("  ℹ️  No open US positions to update.")
        return

    print(f"\n  🔍 Monitoring {len(open_pos)} Open US Positions...")
    closed_syms = []

    for sym, pos in list(open_pos.items()):
        try:
            t = yf.Ticker(sym)
            df = t.history(period="5d", interval="1d", auto_adjust=True)
            if df is None or len(df) == 0: continue

            today = df.iloc[-1]
            h = float(today["High"])
            l = float(today["Low"])
            entry = float(pos["entry"])
            sl    = float(pos["sl"])
            tp1   = float(pos["tp1"])
            tp2   = float(pos["tp2"])
            shares = int(pos["shares"])

            # 1. Stop Loss Hit
            if l <= sl:
                exit_p = min(entry, sl)
                pnl = (exit_p - entry) * shares
                portfolio["cash_balance_usd"] += (exit_p * shares)
                portfolio["realized_pnl_usd"] += pnl
                closed_syms.append((sym, "STOP_LOSS", exit_p, pnl))
                print(f"  ❌ STOP LOSS HIT: {sym} Exit ${exit_p:.2f} | P&L: ${pnl:,.2f}")

            # 2. Target 1 Hit (Book 50%)
            elif h >= tp1 and not pos.get("tp1_booked", False):
                half = shares // 2
                pos["shares"] -= half
                pos["tp1_booked"] = True
                pos["sl"] = entry # Breakeven
                pnl = (tp1 - entry) * half
                portfolio["cash_balance_usd"] += (tp1 * half)
                portfolio["realized_pnl_usd"] += pnl
                print(f"  🎉 TARGET 1 HIT: {sym} Booked 50% ({half} shs) at ${tp1:.2f} | P&L: +${pnl:,.2f} | SL moved to Entry ${entry:.2f}")
                log_trade({
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Symbol": sym,
                    "Action": "PARTIAL_TP1",
                    "Price": tp1,
                    "Shares": half,
                    "Realized_PnL_USD": round(pnl, 2),
                    "Notes": "50% booked at TP1"
                })

            # 3. Target 2 Hit (Final exit)
            elif h >= tp2 and pos.get("tp1_booked", False):
                rem = pos["shares"]
                pnl = (tp2 - entry) * rem
                portfolio["cash_balance_usd"] += (tp2 * rem)
                portfolio["realized_pnl_usd"] += pnl
                closed_syms.append((sym, "TARGET_2", tp2, pnl))
                print(f"  🏆 TARGET 2 HIT: {sym} Full Exit at ${tp2:.2f} | P&L: +${pnl:,.2f}")

        except Exception as e:
            print(f"  ⚠️ Error updating {sym}: {e}")

    for sym, reason, exit_p, pnl in closed_syms:
        pos = open_pos.pop(sym)
        record = {
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Symbol": sym,
            "Action": f"CLOSE_{reason}",
            "Entry": pos["entry"],
            "Exit": exit_p,
            "Shares": pos["shares"],
            "Realized_PnL_USD": round(pnl, 2),
            "Notes": reason
        }
        portfolio["closed_positions"].append(record)
        log_trade(record)

def take_new_trades(portfolio, scan_results):
    open_pos = portfolio["open_positions"]
    slots = MAX_OPEN_TRADES - len(open_pos)
    if slots <= 0:
        print(f"  ⚠️ Max open US positions ({MAX_OPEN_TRADES}) reached.")
        return

    buynow = [r for r in scan_results if r["verdict"] == "BUY NOW" and r["symbol"] not in open_pos]
    near   = [r for r in scan_results if r["verdict"] == "NEAR ENTRY" and r["symbol"] not in open_pos]
    candidates = buynow + near

    print(f"\n  🎯 Actionable US Candidates: {len(candidates)} | Available Slots: {slots}")

    for r in candidates[:slots]:
        sym = r["symbol"]
        price = r["confirm_at"] if r["verdict"] == "NEAR ENTRY" and r["confirm_at"] else r["close"]
        shares = r["shares"]
        cost = price * shares

        if cost > portfolio["cash_balance_usd"]:
            shares = int(portfolio["cash_balance_usd"] / price)
            cost = price * shares

        if shares <= 0: continue

        portfolio["cash_balance_usd"] -= cost
        open_pos[sym] = {
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
        print(f"  ✅ EXECUTED US PAPER BUY: {sym} | {shares} shs @ ${price:.2f} | Total ${cost:,.2f} | SL: ${r['sl']} | TP1: ${r['tp1']}")

        log_trade({
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Symbol": sym,
            "Action": f"BUY_{r['verdict']}",
            "Entry": price,
            "Exit": None,
            "Shares": shares,
            "Realized_PnL_USD": 0.0,
            "Notes": f"Score {r['score']}/10, SL: ${r['sl']}"
        })

def print_portfolio_snapshot(portfolio):
    cash = portfolio["cash_balance_usd"]
    realized = portfolio["realized_pnl_usd"]
    open_pos = portfolio["open_positions"]

    invested = 0.0
    current_val = 0.0
    for sym, pos in open_pos.items():
        invested += pos["cost"]
        try:
            df = yf.download(sym, period="1d", auto_adjust=True, progress=False)
            if df is not None and len(df) > 0:
                current_val += float(df.iloc[-1]["Close"]) * pos["shares"]
            else:
                current_val += pos["cost"]
        except Exception:
            current_val += pos["cost"]

    unrealized = current_val - invested
    total_eq = cash + current_val
    ret_pct = ((total_eq - portfolio["initial_capital_usd"]) / portfolio["initial_capital_usd"]) * 100

    report = f"""
  {'█'*65}
  💼 US PAPER TRADING PORTFOLIO SNAPSHOT (S&P 500)
  {'█'*65}
  Initial Capital   : ${portfolio['initial_capital_usd']:,.2f} USD
  Cash Balance      : ${cash:,.2f}
  Invested Value    : ${invested:,.2f}
  Current Value     : ${current_val:,.2f}
  Unrealized P&L    : ${unrealized:+,.2f}
  Realized P&L      : ${realized:+,.2f}
  Total Portfolio   : ${total_eq:,.2f} ({ret_pct:+.2f}%)
  Open Positions    : {len(open_pos)} / {MAX_OPEN_TRADES}
  {'─'*65}
"""
    print(report)
    with open(DAILY_LOG_FILE, "a") as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}]\n" + report + "\n")

def run_us_paper_trading():
    print("\n" + "█"*65)
    print("  🤖 US AUTONOMOUS PAPER TRADING ROBOT ACTIVATED")
    print(f"  📅 {datetime.now().strftime('%A, %d %B %Y  %I:%M %p EST')}")
    print("█"*65)

    portfolio = load_portfolio()
    update_open_positions(portfolio)

    print("\n  🚀 Running full 503 S&P 500 Market Scan...")
    results = run_us_deep_scan()

    take_new_trades(portfolio, results)
    save_portfolio(portfolio)
    print_portfolio_snapshot(portfolio)
    print("  💾 State saved to us_paper_portfolio.json & us_trade_history.csv")

    # Send Telegram alert
    try:
        top_candidates = [r for r in results if r["verdict"] in ("BUY NOW", "NEAR ENTRY")]
        tg_msg = format_daily_alert("US", portfolio, [], top_candidates)
        send_telegram_message(tg_msg)
    except Exception as e:
        print(f"  ⚠️ Telegram dispatch error: {e}")

if __name__ == "__main__":
    run_us_paper_trading()
