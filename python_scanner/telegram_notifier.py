"""
GOD SWING — TELEGRAM NOTIFICATION DISPATCHER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sends formatted Telegram alerts for:
  - Daily Market Scan Summary
  - New Paper Trade Entries (BUY NOW / NEAR ENTRY)
  - Target 1 Bookings (50% locked in + Breakeven SL)
  - Target 2 Exits (Full profit)
  - Stop Loss Hits
  - Direct Link to Live Web Dashboard

Credentials read securely from environment variables:
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import requests
import json
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message_text):
    """Sends a markdown/HTML formatted message to your Telegram account."""
    if not BOT_TOKEN or not CHAT_ID:
        print("  ℹ️ Telegram credentials not configured. Skipping alert.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("  ✅ Telegram notification sent successfully!")
            return True
        else:
            print(f"  ⚠️ Telegram API error ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"  ⚠️ Failed to send Telegram message: {e}")
        return False

def format_daily_alert(market, portfolio, actions_taken, top_signals):
    """Formats a beautiful HTML alert for Telegram."""
    flag = "🇮🇳" if market == "IN" else "🇺🇸"
    curr = "₹" if market == "IN" else "$"
    market_name = "India NSE 500" if market == "IN" else "US S&P 500"

    cash = portfolio.get("cash_balance", portfolio.get("cash_balance_usd", 0))
    initial = portfolio.get("initial_capital", portfolio.get("initial_capital_usd", 0))
    realized = portfolio.get("realized_pnl", portfolio.get("realized_pnl_usd", 0))
    open_pos = portfolio.get("open_positions", {})

    invested = sum(p.get("cost", 0) for p in open_pos.values())
    total_eq = cash + invested
    ret_pct = ((total_eq - initial) / initial) * 100 if initial else 0

    pnl_sign = "+" if realized >= 0 else ""

    is_muhurat = market == "IN" and (datetime.now().strftime("%Y-%m-%d") == "2026-11-08" or os.getenv("FORCE_MUHURAT", "").lower() in ["1", "true"])

    if is_muhurat:
        msg = f"<b>🪔 GOD SWING SYSTEM — DIWALI MUHURAT TRADING 2026 (SAMVAT 2083) 🪔</b>\n"
        msg += f"<i>✨ Wishing you wealth, prosperity & disciplined execution! ✨</i>\n"
        msg += f"<b>Session:</b> 2:20 PM – 3:40 PM IST (Special Diwali Muhurat Session)\n\n"
    else:
        msg = f"<b>⚡ GOD SWING SYSTEM — DAILY REPORT {flag}</b>\n"
        msg += f"<i>{market_name} | Post-Market Summary</i>\n\n"

    msg += "<b>💼 PORTFOLIO STATUS:</b>\n"
    msg += f"• <b>Total Equity:</b> {curr}{total_eq:,.2f} (<code>{ret_pct:+.2f}%</code>)\n"
    msg += f"• <b>Cash Balance:</b> {curr}{cash:,.2f}\n"
    msg += f"• <b>Open Positions:</b> {len(open_pos)} / 6 active\n"
    msg += f"• <b>Realized P&L:</b> {curr}{pnl_sign}{realized:,.2f}\n\n"

    # Actions taken
    if actions_taken:
        msg += "<b>🎯 ACTIONS TAKEN TODAY:</b>\n"
        for act in actions_taken:
            msg += f"• {act}\n"
        msg += "\n"
    elif open_pos:
        msg += "<b>🎯 ACTIONS TAKEN:</b> Holding all active positions (No new fills/exits today).\n\n"
    else:
        msg += "<b>🎯 ACTIONS TAKEN:</b> No trades taken.\n\n"

    # Current Active Positions
    if open_pos:
        msg += f"<b>📌 ACTIVE PAPER POSITIONS ({len(open_pos)}/6):</b>\n"
        for sym, pos in open_pos.items():
            entry_p = pos.get('entry', 0)
            shs = pos.get('shares', 0)
            sl_p = pos.get('sl', 0)
            tp1_p = pos.get('tp1', 0)
            score = pos.get('score', 0)
            msg += f"• <b>{sym}</b>: {shs} shs @ {curr}{entry_p:,.2f} | SL: {curr}{sl_p:,.2f} | TP1: {curr}{tp1_p:,.2f}\n"
        msg += "\n"

    # Next Session Watchlist (Excluding already held symbols)
    next_watchlist = [s for s in top_signals if s['symbol'] not in open_pos]
    if next_watchlist:
        msg += "<b>👀 TOP WATCHLIST FOR NEXT SESSION (Unfilled Candidates):</b>\n"
        for i, s in enumerate(next_watchlist[:4], 1):
            target_p = s.get("confirm_at") if s.get("verdict") == "NEAR ENTRY" and s.get("confirm_at") else s.get("close")
            msg += f"{i}. <b>{s['symbol']}</b> (<code>{s['verdict']}</code>) — Entry/Target: {curr}{target_p:,.2f} | Score: {s['score']}/10\n"
        msg += "\n"

    msg += f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/"><b>View Live Web Dashboard</b></a>'

    return msg
