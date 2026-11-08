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
    else:
        msg += "<b>🎯 ACTIONS TAKEN:</b> No changes today (Holding active positions).\n\n"

    # Top Watchlist
    if top_signals:
        msg += "<b>👀 TOP WATCHLIST FOR NEXT SESSION:</b>\n"
        for i, s in enumerate(top_signals[:4], 1):
            target_p = s.get("confirm_at") if s.get("verdict") == "NEAR ENTRY" and s.get("confirm_at") else s.get("close")
            msg += f"{i}. <b>{s['symbol']}</b> (<code>{s['verdict']}</code>) — Target: {curr}{target_p:,.2f} | Score: {s['score']}/10\n"
        msg += "\n"

    msg += f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/"><b>View Live Web Dashboard</b></a>'

    return msg
