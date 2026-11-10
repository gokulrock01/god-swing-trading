"""
NSE TRADING HOLIDAY & MARKET STATUS GUARD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detects weekends, official NSE exchange holidays, and market closure
to prevent false trade entries when the Indian stock market is closed.
"""

import sys
import datetime

# Official Indian Equity & F&O Trading Holidays (NSE/BSE)
# Format: YYYY-MM-DD : "Holiday Name"
NSE_HOLIDAYS = {
    # 2026 Known Schedule & Observances
    "2026-01-26": "Republic Day",
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
    "2026-11-08": "Diwali Laxmi Pujan (Muhurat Trading)",
    "2026-11-09": "Diwali Balipratipada",
    "2026-11-10": "Exchange Settlement Holiday / Bhaubeej",
    "2026-11-24": "Guru Nanak Jayanti",
    "2026-12-25": "Christmas",
}

def is_market_open_today(date_to_check=None):
    """
    Returns (is_open: bool, reason: str)
    is_open = True if normal trading day (Mon-Fri, non-holiday)
    is_open = False if Weekend or NSE Holiday
    """
    if date_to_check is None:
        date_to_check = datetime.date.today()
    elif isinstance(date_to_check, datetime.datetime):
        date_to_check = date_to_check.date()

    # 1. Weekend check
    weekday = date_to_check.weekday()
    if weekday == 5:
        return False, "Saturday (Weekend Closure)"
    if weekday == 6:
        return False, "Sunday (Weekend Closure)"

    # 2. Holiday check
    d_str = date_to_check.strftime("%Y-%m-%d")
    if d_str in NSE_HOLIDAYS:
        return False, f"NSE Holiday: {NSE_HOLIDAYS[d_str]}"

    return True, "Trading Day Open"

if __name__ == "__main__":
    is_open, reason = is_market_open_today()
    if not is_open:
        print(f"CLOSED: {reason}")
        sys.exit(1)
    else:
        print(f"OPEN: {reason}")
        sys.exit(0)
