"""
NSE TRADING HOLIDAY & MARKET STATUS GUARD (2025 - 2026)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detects weekends and official Indian Stock Exchange (NSE/BSE) holidays.
Computes the exact next trading day and dispatches a notification
to Telegram at 09:00 AM IST so the trader knows markets are closed.
"""

import sys
import datetime
import requests

# Official Indian Stock Market (NSE / BSE) Trading Holidays
# Includes Equity, Equity Derivatives (F&O), and SLB segments.
NSE_HOLIDAYS = {
    # --- 2025 Calendar ---
    "2025-01-26": "Republic Day",
    "2025-02-26": "Maha Shivratri",
    "2025-03-14": "Holi",
    "2025-03-31": "Id-Ul-Fitr (Ramzan Id)",
    "2025-04-10": "Mahavir Jayanti",
    "2025-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2025-04-18": "Good Friday",
    "2025-05-01": "Maharashtra Day",
    "2025-06-07": "Bakri Id / Eid-ul-Adha",
    "2025-07-06": "Muharram",
    "2025-08-15": "Independence Day",
    "2025-09-05": "Milad-un-Nabi",
    "2025-10-02": "Mahatma Gandhi Jayanti",
    "2025-10-21": "Dussehra",
    "2025-10-22": "Diwali Balipratipada",
    "2025-11-05": "Guru Nanak Jayanti",
    "2025-12-25": "Christmas",

    # --- 2026 Calendar ---
    "2026-01-26": "Republic Day",
    "2026-02-16": "Maha Shivratri",
    "2026-03-03": "Holi",
    "2026-03-20": "Id-Ul-Fitr (Ramzan Id)",
    "2026-03-27": "Ram Navami",
    "2026-03-31": "Mahavir Jayanti",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-27": "Bakri Id / Eid-ul-Adha",
    "2026-06-26": "Muharram",
    "2026-08-15": "Independence Day",
    "2026-09-04": "Milad-un-Nabi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-08": "Diwali Laxmi Pujan (Normal Trading Closed; Muhurat in Evening)",
    "2026-11-09": "Diwali Balipratipada",
    "2026-11-10": "Bhaubeej / Exchange Holiday",
    "2026-11-24": "Guru Nanak Jayanti",
    "2026-12-25": "Christmas",
}

def is_market_open_today(date_to_check=None):
    """
    Returns (is_open: bool, reason: str, next_session_str: str)
    """
    if date_to_check is None:
        date_to_check = datetime.date.today()
    elif isinstance(date_to_check, datetime.datetime):
        date_to_check = date_to_check.date()

    next_trading_day = get_next_trading_day(date_to_check)
    next_session_str = next_trading_day.strftime("%A, %d %b %Y at 09:15 AM IST")

    # 1. Weekend check
    weekday = date_to_check.weekday()
    if weekday == 5:
        return False, "Saturday (Weekend Closure)", next_session_str
    if weekday == 6:
        return False, "Sunday (Weekend Closure)", next_session_str

    # 2. Holiday check
    d_str = date_to_check.strftime("%Y-%m-%d")
    if d_str in NSE_HOLIDAYS:
        return False, f"NSE Holiday — {NSE_HOLIDAYS[d_str]}", next_session_str

    return True, "Active Trading Day", next_session_str

def get_next_trading_day(from_date=None):
    """Iterates forward to find the next business day that is not a weekend or NSE holiday."""
    if from_date is None:
        from_date = datetime.date.today()
    elif isinstance(from_date, datetime.datetime):
        from_date = from_date.date()

    candidate = from_date + datetime.timedelta(days=1)
    while True:
        if candidate.weekday() in (5, 6):
            candidate += datetime.timedelta(days=1)
            continue
        c_str = candidate.strftime("%Y-%m-%d")
        if c_str in NSE_HOLIDAYS:
            candidate += datetime.timedelta(days=1)
            continue
        return candidate

def send_holiday_telegram_alert(tokens=None, chat_id="607732212"):
    """Dispatches a formatted NSE Holiday notice across the bots."""
    today = datetime.date.today()
    is_open, reason, next_session = is_market_open_today(today)
    if is_open:
        print("[i] Market is open today. No holiday notification needed.")
        return False

    date_formatted = today.strftime("%A, %d %B %Y")
    
    msg = (
        f"🏖️ <b>NSE TRADING HOLIDAY NOTICE — NO TRADING TODAY</b> 🇮🇳\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 <b>Date:</b> {date_formatted}\n"
        f"🎉 <b>Occasion:</b> {reason}\n"
        f"🏛️ <b>Market Status:</b> NSE & BSE Closed (Equity & Derivatives)\n\n"
        f"🛡️ <b>Trading Suite Status:</b>\n"
        f"• <b>Nifty Options Sentinel:</b> Standby / Power-Save ✅\n"
        f"• <b>Hybrid Stock Options:</b> Standby / Power-Save ✅\n"
        f"• <b>Institutional BTST:</b> Standby / Power-Save ✅\n"
        f"• <b>Cash Swing Radar:</b> Standby / Power-Save ✅\n\n"
        f"⏭️ <b>Next Live Trading Session:</b>\n"
        f"<b>{next_session}</b>\n\n"
        f"✨ <i>Enjoy your holiday! Zero monitoring required today.</i> ☕🏖️"
    )

    if tokens is None:
        tokens = [
            "9195212668:AAFRAxvb8GNdXxyYekIfJknkmrDEAgF0lfw",  # @Godoptions_bot
            "9087683073:AAHrRxkXIXpG3RIc61tEoINvo1WmpijH7f4",  # @Godswingalertbot
            "9047159970:AAHYxR3STsJO83ACYlFIjrP9UP1t97VFGTk"   # @BTSTALERTbot
        ]

    for tok in tokens:
        try:
            url = f"https://api.telegram.org/bot{tok}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML"
            }
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                print(f"  ✅ Holiday notice dispatched via bot ({tok[:10]}...)")
            else:
                print(f"  ⚠️ Error sending holiday notice ({tok[:10]}...): {res.text}")
        except Exception as e:
            print(f"  ❌ Failed to dispatch to token {tok[:10]}...: {e}")

    return True

if __name__ == "__main__":
    is_open, reason, next_session = is_market_open_today()
    if not is_open:
        print(f"CLOSED: {reason} | Next Session: {next_session}")
        if "--notify" in sys.argv:
            send_holiday_telegram_alert()
        sys.exit(1)
    else:
        print(f"OPEN: {reason} | Next Session: {next_session}")
        sys.exit(0)
