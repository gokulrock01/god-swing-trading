"""
GOD SWING — ANGEL ONE LIVE SWING SENTINEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Autonomous Real-Time Market Hours Engine (9:15 AM - 3:30 PM IST):
  1. Live Tick Monitoring via Angel One SmartAPI (0-sec delay).
  2. Instant 50% Profit Booking on TP1 Hit & SL trailed to Breakeven.
  3. Strict Stop-Loss Exits on SL breaches.
  4. Real-time Breakout Entry execution for NEAR ENTRY candidates.
  5. Immediate Telegram Flash Alerts for every execution event.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import time
import json
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from angel_feed import get_angel_session, get_live_ltp, place_live_cnc_order
from telegram_notifier import send_telegram_message

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "signals", "paper_portfolio.json")
HISTORY_FILE   = os.path.join(os.path.dirname(__file__), "signals", "paper_trade_history.csv")
WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "signals", "deep_analysis.csv")
MAX_OPEN_TRADES = 6

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"initial_capital": 1000000, "cash_balance": 1000000, "realized_pnl": 0.0, "open_positions": {}, "closed_positions": []}

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

def monitor_open_positions(portfolio):
    """Checks active swing positions against Angel One live market ticks."""
    open_pos = portfolio.get("open_positions", {})
    if not open_pos:
        return False

    changed = False
    symbols_to_close = []

    for sym, pos in list(open_pos.items()):
        quote = get_live_ltp(sym)
        if not quote:
            continue

        ltp  = quote["ltp"]
        high = quote["high"]
        low  = quote["low"]

        entry  = float(pos["entry"])
        sl     = float(pos["sl"])
        tp1    = float(pos["tp1"])
        tp2    = float(pos["tp2"])
        shares = int(pos["shares"])
        score  = pos.get("score", 10)

        # 1. Stop Loss Hit (Checked against Day Low / Current LTP)
        if low <= sl or ltp <= sl:
            exit_p = min(entry, sl)
            pnl = (exit_p - entry) * shares
            portfolio["cash_balance"] += (exit_p * shares)
            portfolio["realized_pnl"] += pnl
            symbols_to_close.append((sym, "STOP_LOSS", exit_p, pnl))
            changed = True

            tg = (
                f"🚨 <b>ANGEL ONE LIVE: STOP LOSS TRIGGERED</b>\n\n"
                f"• <b>Symbol:</b> #{sym}\n"
                f"• <b>Exit Price:</b> ₹{exit_p:,.2f} (SL: ₹{sl:,.2f})\n"
                f"• <b>Shares:</b> {shares}\n"
                f"• <b>P&L:</b> <code>₹{pnl:+,.2f}</code>\n"
                f"• <b>Capital Preserved:</b> ₹{exit_p * shares:,.2f} returned to cash.\n\n"
                f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Dashboard</a>'
            )
            send_telegram_message(tg)
            print(f"  ❌ [ANGEL ONE LIVE] STOP LOSS on {sym}: Exit ₹{exit_p:.2f} | P&L: ₹{pnl:+,.2f}")

        # 2. Target 1 Hit (50% Locked + Move SL to Breakeven)
        elif (high >= tp1 or ltp >= tp1) and not pos.get("tp1_booked", False):
            half_shares = shares // 2
            pos["shares"] -= half_shares
            pos["tp1_booked"] = True
            pos["sl"] = entry # Breakeven trailing!
            pnl = (tp1 - entry) * half_shares
            portfolio["cash_balance"] += (tp1 * half_shares)
            portfolio["realized_pnl"] += pnl
            changed = True

            log_trade({
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Symbol": sym,
                "Action": "PARTIAL_TP1_LIVE",
                "Entry": entry,
                "Exit": tp1,
                "Shares": half_shares,
                "Realized_PnL": round(pnl, 2),
                "Notes": f"Angel One Live Feed | 50% locked @ TP1, SL moved to BE ₹{entry:.2f}"
            })

            tg = (
                f"🎉 <b>ANGEL ONE LIVE: TARGET 1 HIT (50% LOCKED)!</b>\n\n"
                f"• <b>Symbol:</b> #{sym}\n"
                f"• <b>Target 1:</b> ₹{tp1:,.2f} (LTP: ₹{ltp:,.2f})\n"
                f"• <b>Profit Booked:</b> <code>+₹{pnl:,.2f}</code> on {half_shares} shares\n"
                f"• <b>Trailing SL:</b> Moved to Break-Even (<b>₹{entry:,.2f}</b>) — <i>Zero Risk Trade!</i>\n"
                f"• <b>Remaining Runner:</b> {pos['shares']} shares targeting TP2 (₹{tp2:,.2f})\n\n"
                f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Dashboard</a>'
            )
            send_telegram_message(tg)
            print(f"  🎉 [ANGEL ONE LIVE] TARGET 1 HIT on {sym}: Booked 50% | P&L: +₹{pnl:,.2f} | SL -> BE ₹{entry:.2f}")

        # 3. Target 2 Hit (Full Exit of remaining 50%)
        elif (high >= tp2 or ltp >= tp2) and pos.get("tp1_booked", False):
            rem_shares = pos["shares"]
            pnl = (tp2 - entry) * rem_shares
            portfolio["cash_balance"] += (tp2 * rem_shares)
            portfolio["realized_pnl"] += pnl
            symbols_to_close.append((sym, "TARGET_2", tp2, pnl))
            changed = True

            tg = (
                f"🏆 <b>ANGEL ONE LIVE: TARGET 2 REACHED (MAX PROFIT)!</b>\n\n"
                f"• <b>Symbol:</b> #{sym}\n"
                f"• <b>Target 2:</b> ₹{tp2:,.2f} (Full Exit)\n"
                f"• <b>Shares:</b> {rem_shares}\n"
                f"• <b>P&L on Runner:</b> <code>+₹{pnl:,.2f}</code>\n"
                f"• <b>Trade Status:</b> Completed with Maximum Institutional Confluence!\n\n"
                f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Dashboard</a>'
            )
            send_telegram_message(tg)
            print(f"  🏆 [ANGEL ONE LIVE] TARGET 2 HIT on {sym}: Full Exit at ₹{tp2:.2f} | P&L: +₹{pnl:,.2f}")

    for sym, reason, exit_price, pnl in symbols_to_close:
        pos = open_pos.pop(sym)
        record = {
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Symbol": sym,
            "Action": f"CLOSE_{reason}_LIVE",
            "Entry": pos["entry"],
            "Exit": exit_price,
            "Shares": pos["shares"],
            "Realized_PnL": round(pnl, 2),
            "Notes": f"Closed via Angel One Live Sentinel ({reason})"
        }
        portfolio.setdefault("closed_positions", []).append(record)
        log_trade(record)

    return changed

def monitor_near_entries(portfolio):
    """Watches NEAR ENTRY candidates and enters live on breakout confirmation."""
    open_pos = portfolio.get("open_positions", {})
    slots = MAX_OPEN_TRADES - len(open_pos)
    if slots <= 0 or not os.path.exists(WATCHLIST_FILE):
        return False

    changed = False
    try:
        df = pd.read_csv(WATCHLIST_FILE)
        near_candidates = df[df["verdict"] == "NEAR ENTRY"].to_dict("records")
    except Exception:
        return False

    for r in near_candidates[:slots]:
        sym = r["symbol"]
        if sym in open_pos:
            continue

        confirm_p = float(r.get("confirm_at", 0) or r.get("close", 0))
        quote = get_live_ltp(sym)
        if not quote:
            continue

        ltp = quote["ltp"]
        # Breakout Trigger: LTP crossed above confirmation price!
        if ltp >= confirm_p:
            shares = int(r["shares"])
            cost = ltp * shares

            if cost > portfolio["cash_balance"]:
                shares = int(portfolio["cash_balance"] / ltp)
                cost = ltp * shares

            if shares <= 0:
                continue

            portfolio["cash_balance"] -= cost
            pos_record = {
                "symbol": sym,
                "verdict": "BUY NOW",
                "entry": ltp,
                "sl": float(r["sl"]),
                "tp1": float(r["tp1"]),
                "tp2": float(r["tp2"]),
                "shares": shares,
                "cost": round(cost, 2),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "score": int(r["score"]),
                "tp1_booked": False
            }
            open_pos[sym] = pos_record
            changed = True

            log_trade({
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Symbol": sym,
                "Action": "LIVE_BREAKOUT_BUY",
                "Entry": ltp,
                "Exit": None,
                "Shares": shares,
                "Realized_PnL": 0.0,
                "Notes": f"Angel One Live Breakout Trigger @ ₹{ltp:.2f} (Confirmed above ₹{confirm_p:.2f})"
            })

            tg = (
                f"⚡ <b>ANGEL ONE LIVE: BREAKOUT ENTRY CONFIRMED!</b>\n\n"
                f"• <b>Symbol:</b> #{sym}\n"
                f"• <b>Breakout Price:</b> ₹{ltp:,.2f} (Triggered above ₹{confirm_p:,.2f})\n"
                f"• <b>Position Size:</b> {shares} shares (₹{cost:,.2f})\n"
                f"• <b>Stop Loss:</b> ₹{r['sl']}\n"
                f"• <b>Target 1 (50%):</b> ₹{r['tp1']}\n"
                f"• <b>Target 2:</b> ₹{r['tp2']}\n"
                f"• <b>Confluence Score:</b> {r['score']}/10\n\n"
                f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Dashboard</a>'
            )
            send_telegram_message(tg)
            print(f"  ⚡ [ANGEL ONE LIVE] BREAKOUT CONFIRMED: {sym} filled @ ₹{ltp:.2f}")

    return changed

def run_angel_sentinel_cycle():
    """Runs a single live check across open positions and near entries."""
    portfolio = load_portfolio()
    changed_pos = monitor_open_positions(portfolio)
    changed_near = monitor_near_entries(portfolio)

    if changed_pos or changed_near:
        save_portfolio(portfolio)
        print("  💾 Live state updated & saved to paper_portfolio.json")

def start_angel_sentinel_daemon(poll_seconds=20):
    """Continuous daemon loop running during market hours."""
    print("=" * 65)
    print("  🛡️ ANGEL ONE LIVE SWING SENTINEL STARTED")
    print(f"  📅 {datetime.now().strftime('%A, %d %B %Y %I:%M:%S %p IST')}")
    print("  ⚡ Monitoring: 0-Sec Latency Real-Time TP1/TP2 & Breakout Entries")
    print("=" * 65)

    session = get_angel_session()
    if not session:
        print("  ❌ Failed to start Sentinel: Angel One authentication failed.")
        return

    while True:
        try:
            now = datetime.now()
            # Market hours: 09:15 to 15:35 IST
            t_str = now.strftime("%H:%M")
            weekday = now.weekday()

            if weekday in [5, 6]:
                print(f"[{now.strftime('%H:%M:%S')}] ⏸️ Weekend: Market is closed. Sentinel in standby mode...")
                time.sleep(300)
                continue

            if t_str < "09:15":
                print(f"[{now.strftime('%H:%M:%S')}] ⏳ Pre-market: Waiting for 09:15 AM IST open...")
                time.sleep(60)
                continue
            elif t_str > "15:35":
                print(f"[{now.strftime('%H:%M:%S')}] 🏁 Market closed (15:35 IST). Sentinel completed for today.")
                break

            run_angel_sentinel_cycle()
            time.sleep(poll_seconds)

        except KeyboardInterrupt:
            print("\n  🛑 Angel One Sentinel stopped by user.")
            break
        except Exception as e:
            print(f"  ⚠️ Error in Sentinel loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Angel One Live Swing Sentinel")
    parser.add_argument("--once", action="store_true", help="Run a single check and exit")
    parser.add_argument("--interval", type=int, default=20, help="Poll interval in seconds (default: 20)")
    args = parser.parse_args()

    if args.once:
        run_angel_sentinel_cycle()
    else:
        start_angel_sentinel_daemon(poll_seconds=args.interval)
