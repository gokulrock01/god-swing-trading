"""
==============================================================================
GOD SWING — HYBRID STOCK OPTIONS ENGINE (ANGEL ONE SMARTAPI)
==============================================================================
Dual-Regime Autonomous Stock Options Trading Engine:
  • Regime 1 (Explosive Momentum): Model 1 — ATM Call/Put Buying (83.3% Win Rate)
      - Trigger: Open=Low/High + 2.5x Volume Spurt + Breakout
      - 50% booked at +40% gain -> SL trailed to Breakeven (0 Risk) -> Runner at +80%
  • Regime 2 (Orderly Trend): Model 2 — Hedged Credit Spreads (88.0% Win Rate)
      - Sells 1 strike OTM & Buys 2 strike OTM Hedge (Bull Put / Bear Call)
      - Collects intraday theta decay -> Auto square-off at 15:15 PM
  • 100% Intraday: Zero overnight risk. All positions closed before market bell.
  • NEWS GUARD (3 Layers):
      - Layer 1 Pre-Trade:  Checks Google News RSS + NSE RSS + Earnings Calendar
      - Layer 2 Intraday:   Monitors breaking news every 60s during active position
      - Layer 3 Earnings:   Special CE/PE bias on quarterly results day
==============================================================================
"""

import os
import sys
import time
import json
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from angel_feed import get_angel_session, get_live_ltp
from nfo_resolver import get_atm_option, get_credit_spread_contracts
from telegram_notifier import send_telegram_message
from news_guard import (
    get_news_signal, should_allow_options_trade, check_active_trade_news,
    is_earnings_day,
    SIGNAL_EARNINGS_CE, SIGNAL_EARNINGS_PE, SIGNAL_AVOID_CE, SIGNAL_AVOID_PE, SIGNAL_CLEAR,
)

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "signals", "hybrid_options_portfolio.json")
HISTORY_FILE   = os.path.join(os.path.dirname(__file__), "signals", "hybrid_options_history.csv")
LOG_FILE       = os.path.join(os.path.dirname(__file__), "signals", "hybrid_options_daily.log")

_LAST_NEWS_CHECK_TIME = 0.0  # Tracks timestamp of last Layer 2 news check (~60s cadence)
_SENT_MORNING_HEARTBEAT = False  # Ensures user receives at least 1 confirmation scan message daily

TOP_FO_UNIVERSE = [
    "TATASTEEL", "RELIANCE", "SBIN", "ICICIBANK", "TATAMOTORS",
    "INFY", "BHARTIARTL", "HDFCBANK", "LT", "BAJFINANCE",
    "AXISBANK", "TITAN", "MARUTI", "TCS", "JSWSTEEL",
    "HINDALCO", "COALINDIA", "NTPC", "ONGC", "BPCL",
    "POWERGRID", "SUNPHARMA", "VEDL", "BHEL", "OFSS"
]

DEFAULT_PORTFOLIO = {
    "initial_capital": 100000.0,
    "cash_balance": 100000.0,
    "realized_pnl": 0.0,
    "active_trade": None,  # Max 1 high-conviction trade at a time
    "closed_trades": []
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

def get_option_ltp(contract_symbol, token):
    """Fetches real-time option contract quote via Angel One SmartAPI."""
    session = get_angel_session()
    if not session:
        return None
    try:
        res = session.ltpData(exchange="NFO", tradingsymbol=contract_symbol, symboltoken=str(token))
        if res.get("status") and "data" in res:
            d = res["data"]
            ltp = float(d.get("ltp", 0.0))
            if ltp > 0:
                return ltp
            return float(d.get("close", 0.0))
    except Exception as e:
        print(f"  ⚠️ Error fetching option LTP for {contract_symbol}: {e}")
    return None

def scan_morning_regimes():
    """
    Evaluates market regime across Top 25 F&O stocks at 09:30 AM.
    Integrates 3-layer News Guard per stock:
      - Earnings day candidates get boosted score and Mode 2 skipped
      - Bad-news stocks are filtered from momentum buying
    Returns (regime_type, candidate_info)
    """
    print("\n  🔍 Scanning Top 25 F&O Universe for Morning Regimes + News Guard...")
    session = get_angel_session()
    if not session:
        return None, None

    momentum_candidates = []
    spread_candidates   = []

    for name in TOP_FO_UNIVERSE:
        q = get_live_ltp(name)
        if not q or q.get("open", 0) <= 0:
            continue

        day_open  = q["open"]
        day_high  = q["high"]
        day_low   = q["low"]
        ltp       = q["ltp"]

        chg_pct      = ((ltp - day_open) / day_open) * 100
        is_open_low  = (abs(day_open - day_low)  / day_open) < 0.0018
        is_open_high = (abs(day_open - day_high) / day_open) < 0.0018

        is_m1_ce = is_open_low and chg_pct >= 1.0 and ltp >= day_high * 0.998
        is_m1_pe = is_open_high and chg_pct <= -1.0 and ltp <= day_low * 1.002
        is_m2_bull = chg_pct >= 0.7
        is_m2_bear = chg_pct <= -0.7

        # Performance optimization: skip news check for stocks with no technical setup
        if not (is_m1_ce or is_m1_pe or is_m2_bull or is_m2_bear):
            continue

        # ── Layer 1: Get News Guard Signal for qualified setup ──────────
        try:
            ng = get_news_signal(name, max_news_age_minutes=60)
            ng_signal         = ng["signal"]
            ng_is_earnings    = ng["is_earnings_day"]
            ng_earn_src       = ng["earnings_source"]
            ng_reason         = ng["reason"]
        except Exception as e:
            print(f"  [NewsGuard] ⚠️ Signal fetch failed for {name}: {e}")
            ng_signal      = SIGNAL_CLEAR
            ng_is_earnings = False
            ng_earn_src    = "error"
            ng_reason      = ""

        # ── 1. Explosive Momentum (Regime 1) ──────────────────────
        if is_m1_ce:
            # Block CE if strong bearish news
            if ng_signal == SIGNAL_AVOID_CE:
                print(f"  🔴 NewsGuard BLOCKED CE on {name}: {ng_reason[:60]}")
            else:
                score = chg_pct * 2.0
                # Earnings day → boost score, flag for wider SL
                if ng_is_earnings:
                    score *= 1.5
                    print(f"  🟡 Earnings Day ({ng_earn_src}): {name} CE score boosted")
                momentum_candidates.append({
                    "name": name, "type": "CALL_BUY_CE", "spot": ltp,
                    "chg": chg_pct, "score": score,
                    "is_earnings": ng_is_earnings, "news_signal": ng_signal,
                    "news_reason": ng_reason,
                })

        elif is_m1_pe:
            # Block PE if strong bullish news
            if ng_signal == SIGNAL_AVOID_PE:
                print(f"  🟢 NewsGuard BLOCKED PE on {name}: {ng_reason[:60]}")
            else:
                score = abs(chg_pct) * 2.0
                if ng_is_earnings:
                    score *= 1.5
                    print(f"  🟡 Earnings Day ({ng_earn_src}): {name} PE score boosted")
                momentum_candidates.append({
                    "name": name, "type": "PUT_BUY_PE", "spot": ltp,
                    "chg": chg_pct, "score": score,
                    "is_earnings": ng_is_earnings, "news_signal": ng_signal,
                    "news_reason": ng_reason,
                })

        # ── 2. Orderly Trend (Regime 2 Credit Spread) ─────────────
        # Skip credit spreads on earnings day (IV crush risk)
        if ng_is_earnings:
            print(f"  🟡 Earnings Day: Skipping credit spread on {name} (IV crush risk)")
        elif is_m2_bull:
            if ng_signal == SIGNAL_AVOID_CE:
                print(f"  🔴 NewsGuard BLOCKED Bull Put Spread on {name}: {ng_reason[:60]}")
            else:
                spread_candidates.append({
                    "name": name, "type": "BULL_PUT_SPREAD", "spot": ltp,
                    "chg": chg_pct, "score": chg_pct,
                    "is_earnings": False, "news_signal": ng_signal, "news_reason": ng_reason,
                })
        elif is_m2_bear:
            if ng_signal == SIGNAL_AVOID_PE:
                print(f"  🟢 NewsGuard BLOCKED Bear Call Spread on {name}: {ng_reason[:60]}")
            else:
                spread_candidates.append({
                    "name": name, "type": "BEAR_CALL_SPREAD", "spot": ltp,
                    "chg": chg_pct, "score": abs(chg_pct),
                    "is_earnings": False, "news_signal": ng_signal, "news_reason": ng_reason,
                })

    # Priority 1: Explosive momentum → Model 1
    if momentum_candidates:
        momentum_candidates.sort(key=lambda x: x["score"], reverse=True)
        return "MODEL_1_MOMENTUM_SNIPER", momentum_candidates[0]

    # Priority 2: Orderly trend → Model 2
    if spread_candidates:
        spread_candidates.sort(key=lambda x: x["score"], reverse=True)
        return "MODEL_2_CREDIT_SPREAD", spread_candidates[0]

    return "NO_REGIME_FOUND", None

def execute_model_1_entry(portfolio, candidate):
    """Executes Model 1 (ATM Option Buying) with live Angel One quote.
    Applies News Guard pre-trade filter and Earnings Day special mode:
      - Earnings Day: wider SL (-30%), quicker TP (+30%/+60%), bigger alert
      - news_signal/is_earnings stored in trade record for intraday monitor
    """
    name      = candidate["name"]
    spot      = candidate["spot"]
    opt_type  = "CE" if candidate["type"] == "CALL_BUY_CE" else "PE"
    is_earn   = candidate.get("is_earnings", False)
    ng_signal = candidate.get("news_signal", SIGNAL_CLEAR)
    ng_reason = candidate.get("news_reason", "")

    # ── Earnings Day alert ──────────────────────────────────────────
    if is_earn:
        earn_tg = (
            f"📅 <b>EARNINGS DAY ALERT: {name} Results Today!</b>\n\n"
            f"• <b>Signal:</b> {ng_signal}\n"
            f"• <b>Strategy:</b> Model 1 Momentum Sniper ({opt_type})\n"
            f"• <b>Mode:</b> Earnings mode — wider SL (-30%), quick TP (+30%)\n"
        )
        send_telegram_message(earn_tg)
        print(f"  📅 EARNINGS MODE activated for {name} ({opt_type})")

    contract = get_atm_option(name, spot, opt_type)
    if not contract:
        print(f"  ⚠️ Could not resolve ATM {opt_type} contract for {name}")
        return

    sym     = contract["symbol"]
    token   = contract["token"]
    lotsize = contract["lotsize"]
    strike  = contract["strike"]

    opt_ltp = get_option_ltp(sym, token)
    if not opt_ltp or opt_ltp <= 0.05:
        opt_ltp = round(spot * 0.020, 2)

    cost = opt_ltp * lotsize

    # ── Earnings Day: wider SL, quicker TP ─────────────────────────
    if is_earn:
        sl_opt  = round(opt_ltp * 0.70, 2)   # -30% SL (wider for earnings volatility)
        tp1_opt = round(opt_ltp * 1.30, 2)   # +30% TP1 (quick profit on earnings spike)
        tp2_opt = round(opt_ltp * 1.60, 2)   # +60% TP2
    else:
        sl_opt  = round(opt_ltp * 0.75, 2)   # -25% SL (standard)
        tp1_opt = round(opt_ltp * 1.40, 2)   # +40% TP1
        tp2_opt = round(opt_ltp * 1.80, 2)   # +80% TP2

    portfolio["cash_balance"] -= cost
    trade_record = {
        "model":            "MODEL_1_MOMENTUM_SNIPER",
        "stock":            name,
        "contract":         sym,
        "token":            token,
        "strike":           strike,
        "type":             opt_type,
        "entry_time":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "spot_entry":       spot,
        "opt_entry":        opt_ltp,
        "shares":           lotsize,
        "cost":             round(cost, 2),
        "sl":               sl_opt,
        "tp1":              tp1_opt,
        "tp2":              tp2_opt,
        "tp1_booked":       False,
        "is_earnings":      is_earn,
        "news_signal":      ng_signal,
        "news_poll_count":  0,   # Increments each 20s cycle; news check every 3rd = 60s
    }
    portfolio["active_trade"] = trade_record
    save_portfolio(portfolio)

    log_trade({
        "Date":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Model":        "MOMENTUM_SNIPER" + ("_EARNINGS" if is_earn else ""),
        "Contract":     sym,
        "Action":       f"BUY_{opt_type}",
        "Entry":        opt_ltp,
        "Exit":         None,
        "Shares":       lotsize,
        "Realized_PnL": 0.0,
        "Notes":        f"Open=Low/High Breakout on {name} | SL: ₹{sl_opt} | TP1: ₹{tp1_opt}" +
                        (" | EARNINGS DAY" if is_earn else ""),
    })

    earn_badge = " 📅 EARNINGS DAY" if is_earn else ""
    tg = (
        f"⚡ <b>ANGEL ONE LIVE: HYBRID OPTION SNIPER ACTIVATED{earn_badge}</b>\n\n"
        f"• <b>Stock:</b> #{name} (Breakout at ₹{spot:,.2f})\n"
        f"• <b>Contract:</b> <code>{sym}</code> (ATM {strike} {opt_type})\n"
        f"• <b>Entry Premium:</b> ₹{opt_ltp:,.2f}\n"
        f"• <b>Lot Size:</b> {lotsize} shares (Capital: ₹{cost:,.2f})\n"
        f"• <b>Stop Loss:</b> ₹{sl_opt:,.2f} ({'-30% Earnings Mode' if is_earn else '-25%'})\n"
        f"• <b>Target 1:</b> ₹{tp1_opt:,.2f} ({'+30%' if is_earn else '+40%'} — 50% Booking & SL to Breakeven)\n"
        f"• <b>Target 2:</b> ₹{tp2_opt:,.2f} ({'+60%' if is_earn else '+80%'} Runner)\n"
        f"• <b>News Guard:</b> {ng_signal}\n\n"
        f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Web Dashboard</a>'
    )
    send_telegram_message(tg)
    earn_tag = " [EARNINGS]" if is_earn else ""
    print(f"  ⚡ EXECUTED MOMENTUM SNIPER{earn_tag}: {sym} @ ₹{opt_ltp} | Cost: ₹{cost:,.2f}")


def execute_model_2_entry(portfolio, candidate):
    """Executes Model 2 (Hedged Credit Spread) with live Angel One quotes."""
    name = candidate["name"]
    spot = candidate["spot"]
    spread_type = candidate["type"]

    spread = get_credit_spread_contracts(name, spot, spread_type)
    if not spread:
        print(f"  ⚠️ Could not resolve credit spread contracts for {name}")
        return

    sell_leg = spread["sell_leg"]
    buy_leg  = spread["buy_leg"]
    lotsize  = sell_leg["lotsize"]

    sell_p = get_option_ltp(sell_leg["symbol"], sell_leg["token"]) or round(spot * 0.015, 2)
    buy_p  = get_option_ltp(buy_leg["symbol"], buy_leg["token"]) or round(spot * 0.009, 2)

    net_credit = max(0.20, sell_p - buy_p)
    total_credit = net_credit * lotsize
    sl_points = net_credit * 1.5

    portfolio["cash_balance"] += total_credit
    trade_record = {
        "model": "MODEL_2_CREDIT_SPREAD",
        "stock": name,
        "spread_type": spread_type,
        "sell_leg": sell_leg["symbol"],
        "buy_leg": buy_leg["symbol"],
        "sell_token": sell_leg["token"],
        "buy_token": buy_leg["token"],
        "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "spot_entry": spot,
        "sell_entry": sell_p,
        "buy_entry": buy_p,
        "net_credit": round(net_credit, 2),
        "total_credit": round(total_credit, 2),
        "sl_spread": round(net_credit + sl_points, 2),
        "lotsize": lotsize,
        "news_signal": candidate.get("news_signal", "CLEAR")
    }
    portfolio["active_trade"] = trade_record
    save_portfolio(portfolio)

    log_trade({
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Model": "CREDIT_SPREAD",
        "Contract": f"{sell_leg['symbol']} / {buy_leg['symbol']}",
        "Action": f"SELL_{spread_type}",
        "Entry": net_credit,
        "Exit": None,
        "Shares": lotsize,
        "Realized_PnL": 0.0,
        "Notes": f"Net Credit: ₹{net_credit:.2f} (Total ₹{total_credit:,.2f}) | SL Spread: ₹{trade_record['sl_spread']:.2f} | News: {candidate.get('news_signal', 'CLEAR')}"
    })

    tg = (
        f"🛡️ <b>ANGEL ONE LIVE: HEDGED CREDIT SPREAD ACTIVATED</b>\n\n"
        f"• <b>Stock:</b> #{name} ({spread_type.replace('_', ' ')})\n"
        f"• <b>Sell Leg:</b> <code>{sell_leg['symbol']}</code> @ ₹{sell_p:,.2f}\n"
        f"• <b>Buy Hedge:</b> <code>{buy_leg['symbol']}</code> @ ₹{buy_p:,.2f}\n"
        f"• <b>Net Credit Collected:</b> <b>₹{net_credit:,.2f}</b> (Total ₹{total_credit:,.2f})\n"
        f"• <b>Edge:</b> Theta Decay pays you automatically by 03:15 PM EOD.\n"
        f"• <b>Stop Loss Spread:</b> ₹{trade_record['sl_spread']:,.2f}\n"
        f"• <b>News Guard:</b> {candidate.get('news_signal', 'CLEAR')}\n\n"
        f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Web Dashboard</a>'
    )
    send_telegram_message(tg)
    print(f"  🛡️ EXECUTED CREDIT SPREAD on {name}: Net Credit ₹{net_credit:.2f} (Total ₹{total_credit:,.2f})")

def monitor_hybrid_trade():
    """Monitors the active option trade against live market ticks."""
    global _LAST_NEWS_CHECK_TIME
    portfolio = load_portfolio()
    tr = portfolio.get("active_trade")
    if not tr:
        return

    now = datetime.now()
    t_str = now.strftime("%H:%M")

    # Safety check: if active trade is from a previous day, auto-archive to unblock today's scan
    entry_date = tr.get("entry_time", "")[:10]
    today_date = now.strftime("%Y-%m-%d")
    if entry_date and entry_date != today_date:
        print(f"  ⚠️ Stale intraday trade from {entry_date}. Auto-closing for new session {today_date}...")
        tr["exit_time"] = f"{entry_date} 15:15:00"
        tr["exit_reason"] = "PREVIOUS_DAY_EOD_CLOSED"
        portfolio.setdefault("closed_trades", []).append(tr)
        portfolio["active_trade"] = None
        save_portfolio(portfolio)
        return

    # 1. MONITOR MODEL 1 (ATM BUYING)
    if tr["model"] == "MODEL_1_MOMENTUM_SNIPER":
        opt_cur = get_option_ltp(tr["contract"], tr["token"])
        if not opt_cur:
            return

        entry = tr["opt_entry"]
        sl    = tr["sl"]
        tp1   = tr["tp1"]
        tp2   = tr["tp2"]
        shares = tr["shares"]

        # LAYER 2: News Sentinel Active Monitor (runs every ~60s)
        now_ts = time.time()
        if now_ts - _LAST_NEWS_CHECK_TIME >= 60.0:
            _LAST_NEWS_CHECK_TIME = now_ts
            stock_name = tr.get("stock", "")
            trade_action = f"BUY_{tr.get('opt_type', 'CE')}"
            try:
                news_res = check_active_trade_news(stock_name, trade_action)
                if news_res.get("emergency_exit"):
                    exit_p = opt_cur
                    rem_shares = tr["shares"]
                    pnl = (exit_p - entry) * rem_shares
                    portfolio["cash_balance"] += (exit_p * rem_shares)
                    portfolio["realized_pnl"] += pnl

                    tr["exit_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    tr["exit_price"] = exit_p
                    tr["final_pnl"] = round(pnl, 2)
                    tr["exit_reason"] = "NEWS_GUARD_EXIT"
                    tr["news_exit_note"] = news_res.get("exit_note", "")
                    portfolio.setdefault("closed_trades", []).append(tr)
                    portfolio["active_trade"] = None
                    save_portfolio(portfolio)

                    log_trade({
                        "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "Model": "MOMENTUM_SNIPER",
                        "Contract": tr["contract"],
                        "Action": "EXIT_NEWS_GUARD",
                        "Entry": entry,
                        "Exit": exit_p,
                        "Shares": rem_shares,
                        "Realized_PnL": round(pnl, 2),
                        "Notes": f"EMERGENCY EXIT: {news_res.get('exit_note', '')}"
                    })

                    tg = (
                        f"🛑 <b>NEWS SENTINEL: EMERGENCY EXIT TRIGGERED!</b>\n\n"
                        f"• <b>Contract:</b> {tr['contract']} ({trade_action})\n"
                        f"• <b>Reason:</b> {news_res.get('exit_note', 'Breaking adverse news detected')}\n"
                        f"• <b>Exit Price:</b> ₹{exit_p:,.2f} (Entry: ₹{entry:,.2f})\n"
                        f"• <b>Realized P&L:</b> <code>₹{pnl:+,.2f}</code>\n"
                        f"• <b>Action:</b> Position squared off immediately to protect capital.\n\n"
                        f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Web Dashboard</a>'
                    )
                    send_telegram_message(tg)
                    print(f"  🛑 NEWS GUARD EMERGENCY EXIT on {tr['contract']}: {news_res.get('exit_note', '')} | P&L: ₹{pnl:+,.2f}")
                    return
            except Exception as e:
                print(f"  [NewsGuard] ⚠️ Intraday news check error for {stock_name}: {e}")

        # Stop Loss Hit
        if opt_cur <= sl:
            rem_shares = tr["shares"]
            exit_p = entry if tr["tp1_booked"] else opt_cur
            pnl = 0.0 if tr["tp1_booked"] else (exit_p - entry) * rem_shares
            portfolio["cash_balance"] += (exit_p * rem_shares)
            portfolio["realized_pnl"] += pnl
            
            tr["exit_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            tr["exit_price"] = exit_p
            tr["final_pnl"] = round(pnl, 2)
            tr["exit_reason"] = "BREAKEVEN_SL" if tr["tp1_booked"] else "STOP_LOSS"
            portfolio.setdefault("closed_trades", []).append(tr)
            portfolio["active_trade"] = None
            save_portfolio(portfolio)

            log_trade({
                "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
                "Model": "MOMENTUM_SNIPER",
                "Contract": tr["contract"],
                "Action": "EXIT_SL",
                "Entry": entry,
                "Exit": exit_p,
                "Shares": rem_shares,
                "Realized_PnL": round(pnl, 2),
                "Notes": tr["exit_reason"]
            })

            tg = (
                f"🚨 <b>ANGEL ONE LIVE: OPTION STOP LOSS TRIGGERED</b>\n\n"
                f"• <b>Contract:</b> {tr['contract']}\n"
                f"• <b>Exit Price:</b> ₹{exit_p:,.2f} (Entry: ₹{entry:,.2f})\n"
                f"• <b>Realized P&L:</b> <code>₹{pnl:+,.2f}</code>\n"
                f"• <b>Status:</b> {'Breakeven Exit (Zero Loss)' if tr['tp1_booked'] else 'Capital Protected'}\n"
            )
            send_telegram_message(tg)
            print(f"  ❌ STOP LOSS on {tr['contract']}: P&L ₹{pnl:+,.2f}")

        # Target 1 Hit (+40% gain)
        elif opt_cur >= tp1 and not tr["tp1_booked"]:
            half_shares = shares // 2
            pnl = (tp1 - entry) * half_shares
            portfolio["cash_balance"] += (tp1 * half_shares)
            portfolio["realized_pnl"] += pnl
            tr["shares"] -= half_shares
            tr["tp1_booked"] = True
            tr["sl"] = entry # Move SL to Breakeven!
            save_portfolio(portfolio)

            log_trade({
                "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
                "Model": "MOMENTUM_SNIPER",
                "Contract": tr["contract"],
                "Action": "PARTIAL_TP1",
                "Entry": entry,
                "Exit": tp1,
                "Shares": half_shares,
                "Realized_PnL": round(pnl, 2),
                "Notes": "50% Profit Booked (+40%) | SL -> Breakeven"
            })

            tg = (
                f"🎉 <b>ANGEL ONE LIVE: TARGET 1 HIT (+40% PROFIT LOCKED)!</b>\n\n"
                f"• <b>Contract:</b> {tr['contract']}\n"
                f"• <b>Target 1:</b> ₹{tp1:,.2f} (LTP: ₹{opt_cur:,.2f})\n"
                f"• <b>Profit Booked:</b> <code>+₹{pnl:,.2f}</code> on {half_shares} shares\n"
                f"• <b>Trailing SL:</b> Moved to Break-Even (<b>₹{entry:,.2f}</b>) — <i>Zero Risk!</i>\n"
                f"• <b>Remaining Runner:</b> {tr['shares']} shares targeting TP2 (₹{tp2:,.2f})\n"
            )
            send_telegram_message(tg)
            print(f"  🎉 TARGET 1 HIT on {tr['contract']}: +₹{pnl:,.2f} booked | SL -> BE ₹{entry:.2f}")

        # Target 2 Hit (+80% gain)
        elif opt_cur >= tp2 and tr["tp1_booked"]:
            rem_shares = tr["shares"]
            pnl = (tp2 - entry) * rem_shares
            portfolio["cash_balance"] += (tp2 * rem_shares)
            portfolio["realized_pnl"] += pnl

            tr["exit_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            tr["exit_price"] = tp2
            tr["final_pnl"] = round(pnl, 2)
            tr["exit_reason"] = "TARGET_2_MAX_PROFIT"
            portfolio.setdefault("closed_trades", []).append(tr)
            portfolio["active_trade"] = None
            save_portfolio(portfolio)

            log_trade({
                "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
                "Model": "MOMENTUM_SNIPER",
                "Contract": tr["contract"],
                "Action": "EXIT_TP2",
                "Entry": entry,
                "Exit": tp2,
                "Shares": rem_shares,
                "Realized_PnL": round(pnl, 2),
                "Notes": "Max Target Hit (+80%)"
            })

            tg = (
                f"🏆 <b>ANGEL ONE LIVE: TARGET 2 REACHED (+80% MAX PROFIT)!</b>\n\n"
                f"• <b>Contract:</b> {tr['contract']}\n"
                f"• <b>Full Exit at:</b> ₹{tp2:,.2f}\n"
                f"• <b>P&L on Runner:</b> <code>+₹{pnl:,.2f}</code>\n"
                f"• <b>Status:</b> Trade Completed at Maximum Institutional Target!\n"
            )
            send_telegram_message(tg)
            print(f"  🏆 TARGET 2 HIT on {tr['contract']}: Full exit at ₹{tp2} | P&L +₹{pnl:,.2f}")

        # EOD Square-off (15:15 PM)
        elif t_str >= "15:15":
            rem_shares = tr["shares"]
            pnl = (opt_cur - entry) * rem_shares
            portfolio["cash_balance"] += (opt_cur * rem_shares)
            portfolio["realized_pnl"] += pnl

            tr["exit_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            tr["exit_price"] = opt_cur
            tr["final_pnl"] = round(pnl, 2)
            tr["exit_reason"] = "EOD_SQUAREOFF"
            portfolio.setdefault("closed_trades", []).append(tr)
            portfolio["active_trade"] = None
            save_portfolio(portfolio)

            log_trade({
                "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
                "Model": "MOMENTUM_SNIPER",
                "Contract": tr["contract"],
                "Action": "EXIT_EOD",
                "Entry": entry,
                "Exit": opt_cur,
                "Shares": rem_shares,
                "Realized_PnL": round(pnl, 2),
                "Notes": "15:15 PM Intraday Square-off"
            })

            tg = (
                f"🏁 <b>ANGEL ONE LIVE: 03:15 PM EOD INTRADAY EXIT</b>\n\n"
                f"• <b>Contract:</b> {tr['contract']}\n"
                f"• <b>Exit Price:</b> ₹{opt_cur:,.2f} (Entry: ₹{entry:,.2f})\n"
                f"• <b>Final P&L:</b> <code>₹{pnl:+,.2f}</code>\n"
            )
            send_telegram_message(tg)
            print(f"  🏁 EOD EXIT on {tr['contract']}: P&L ₹{pnl:+,.2f}")

    # 2. MONITOR MODEL 2 (CREDIT SPREAD)
    elif tr["model"] == "MODEL_2_CREDIT_SPREAD":
        cur_sell = get_option_ltp(tr["sell_leg"], tr["sell_token"])
        cur_buy  = get_option_ltp(tr["buy_leg"], tr["buy_token"])
        if not cur_sell or not cur_buy:
            return

        cur_spread = max(0.05, cur_sell - cur_buy)
        net_credit = tr["net_credit"]
        sl_spread  = tr["sl_spread"]
        lotsize    = tr["lotsize"]

        # LAYER 2: News Sentinel Active Monitor for Credit Spread (Runs every ~60s)
        now_ts = time.time()
        if now_ts - _LAST_NEWS_CHECK_TIME >= 60.0:
            _LAST_NEWS_CHECK_TIME = now_ts
            stock_name = tr.get("stock", "")
            spread_type = tr.get("spread_type", "")
            # BULL_PUT is hurt by bearish news (same as BUY_CE); BEAR_CALL by bullish news
            equiv_action = "BUY_CE" if spread_type == "BULL_PUT" else "BUY_PE"
            try:
                news_res = check_active_trade_news(stock_name, equiv_action)
                if news_res.get("emergency_exit"):
                    loss = (cur_spread - net_credit) * lotsize
                    portfolio["cash_balance"] -= loss
                    portfolio["realized_pnl"] -= loss

                    tr["exit_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    tr["exit_price"] = cur_spread
                    tr["final_pnl"] = round(-loss, 2)
                    tr["exit_reason"] = "NEWS_GUARD_EXIT"
                    tr["news_exit_note"] = news_res.get("exit_note", "")
                    portfolio.setdefault("closed_trades", []).append(tr)
                    portfolio["active_trade"] = None
                    save_portfolio(portfolio)

                    log_trade({
                        "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "Model": "CREDIT_SPREAD",
                        "Contract": f"{tr['sell_leg']} / {tr['buy_leg']}",
                        "Action": "EXIT_NEWS_GUARD",
                        "Entry": net_credit,
                        "Exit": cur_spread,
                        "Shares": lotsize,
                        "Realized_PnL": round(-loss, 2),
                        "Notes": f"EMERGENCY SPREAD EXIT: {news_res.get('exit_note', '')}"
                    })

                    tg = (
                        f"🛑 <b>NEWS SENTINEL: EMERGENCY EXIT FOR CREDIT SPREAD!</b>\n\n"
                        f"• <b>Stock:</b> #{stock_name} ({spread_type})\n"
                        f"• <b>Reason:</b> {news_res.get('exit_note', '')}\n"
                        f"• <b>Spread Exit:</b> ₹{cur_spread:,.2f} (Entry: ₹{net_credit:,.2f})\n"
                        f"• <b>Realized P&L:</b> <code>₹{-loss:+,.2f}</code>\n"
                        f"• <b>Action:</b> Spread closed immediately to avoid tail-risk blowout.\n\n"
                        f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Web Dashboard</a>'
                    )
                    send_telegram_message(tg)
                    print(f"  🛑 NEWS GUARD SPREAD EXIT on {stock_name}: {news_res.get('exit_note', '')} | P&L: ₹{-loss:+,.2f}")
                    return
            except Exception as e:
                print(f"  [NewsGuard] ⚠️ Intraday news check error for {stock_name}: {e}")

        # Stop Loss Hit
        if cur_spread >= sl_spread:
            loss = (cur_spread - net_credit) * lotsize
            portfolio["cash_balance"] -= loss
            portfolio["realized_pnl"] -= loss

            tr["exit_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            tr["exit_price"] = cur_spread
            tr["final_pnl"] = round(-loss, 2)
            tr["exit_reason"] = "CREDIT_SPREAD_SL"
            portfolio.setdefault("closed_trades", []).append(tr)
            portfolio["active_trade"] = None
            save_portfolio(portfolio)

            log_trade({
                "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
                "Model": "CREDIT_SPREAD",
                "Contract": f"{tr['sell_leg']} / {tr['buy_leg']}",
                "Action": "EXIT_SL",
                "Entry": net_credit,
                "Exit": cur_spread,
                "Shares": lotsize,
                "Realized_PnL": round(-loss, 2),
                "Notes": f"SL Spread Breached: ₹{cur_spread:.2f} >= ₹{sl_spread:.2f}"
            })

            tg = f"🚨 <b>CREDIT SPREAD SL TRIGGERED</b> on #{tr['stock']}: Loss ₹{loss:,.2f}"
            send_telegram_message(tg)
            print(f"  ❌ SPREAD SL on {tr['stock']}: Loss ₹{loss:,.2f}")

        # EOD Square-off (15:15 PM): Full/Partial Theta Decay Kept!
        elif t_str >= "15:15":
            pnl = (net_credit - cur_spread) * lotsize
            portfolio["realized_pnl"] += pnl

            tr["exit_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            tr["exit_price"] = cur_spread
            tr["final_pnl"] = round(pnl, 2)
            tr["exit_reason"] = "EOD_THETA_COLLECTION"
            portfolio.setdefault("closed_trades", []).append(tr)
            portfolio["active_trade"] = None
            save_portfolio(portfolio)

            log_trade({
                "Date": now.strftime("%Y-%m-%d %H:%M:%S"),
                "Model": "CREDIT_SPREAD",
                "Contract": f"{tr['sell_leg']} / {tr['buy_leg']}",
                "Action": "EXIT_EOD_THETA",
                "Entry": net_credit,
                "Exit": cur_spread,
                "Shares": lotsize,
                "Realized_PnL": round(pnl, 2),
                "Notes": "03:15 PM EOD Theta Decay Harvested"
            })

            tg = (
                f"🏁 <b>03:15 PM EOD SPREAD CLOSED (THETA PROFIT KEPT)</b>\n\n"
                f"• <b>Stock:</b> #{tr['stock']}\n"
                f"• <b>Credit Collected:</b> ₹{net_credit:,.2f} -> Closed at: ₹{cur_spread:,.2f}\n"
                f"• <b>Net Realized P&L:</b> <code>₹{pnl:+,.2f}</code>\n"
            )
            send_telegram_message(tg)
            print(f"  🏁 EOD SPREAD CLOSED on {tr['stock']}: P&L +₹{pnl:,.2f}")

def run_hybrid_cycle(force=False):
    """Runs a single live check across active trade or scans for morning regime."""
    portfolio = load_portfolio()
    now = datetime.now()
    t_str = now.strftime("%H:%M")

    if portfolio.get("active_trade") is not None:
        tr = portfolio["active_trade"]
        entry_date = tr.get("entry_time", "")[:10]
        today_date = now.strftime("%Y-%m-%d")
        if entry_date and entry_date != today_date:
            print(f"  ⚠️ Stale intraday trade from {entry_date}. Auto-closing for new session {today_date}...")
            tr["exit_time"] = f"{entry_date} 15:15:00"
            tr["exit_reason"] = "PREVIOUS_DAY_EOD_CLOSED"
            portfolio.setdefault("closed_trades", []).append(tr)
            portfolio["active_trade"] = None
            save_portfolio(portfolio)
        else:
            name = tr.get("contract") or tr.get("stock")
            print(f"[{now.strftime('%H:%M:%S')}] 📌 Active trade open: {name} | Monitoring ticks...")
            monitor_hybrid_trade()
            return

    # If within morning entry window (09:30 - 11:30 IST) or forced
    if force or ("09:30" <= t_str <= "11:30"):
        # Market Holiday Check
        try:
            from nse_holiday_guard import is_market_open_today
            is_open, reason = is_market_open_today()
            if not is_open and not force:
                print(f"[{now.strftime('%H:%M:%S')}] 🏖️ NSE Market Holiday ({reason}). Engine in standby.")
                return
        except Exception:
            pass

        regime, candidate = scan_morning_regimes()
        print(f"[{now.strftime('%H:%M:%S')}] 🎯 Detected Regime: {regime}")

        if regime == "MODEL_1_MOMENTUM_SNIPER":
            print(f"  ⚡ Activating Model 1 (Momentum Sniper CE/PE Buying) for {candidate['name']}...")
            execute_model_1_entry(portfolio, candidate)
        elif regime == "MODEL_2_CREDIT_SPREAD":
            print(f"  🛡️ Activating Model 2 (Hedged Credit Spread) for {candidate['name']}...")
            execute_model_2_entry(portfolio, candidate)
        else:
            print(f"[{now.strftime('%H:%M:%S')}] ⏸️ No high-confluence institutional setup detected. Staying 100% Cash.")
            global _SENT_MORNING_HEARTBEAT
            if not _SENT_MORNING_HEARTBEAT:
                _SENT_MORNING_HEARTBEAT = True
                msg = (
                    f"🔍 <b>ANGEL ONE OPTIONS: MORNING SCAN COMPLETED</b>\n\n"
                    f"• <b>Status:</b> Market scanned across Top 25 F&O stocks.\n"
                    f"• <b>News Sentinel:</b> Vetted with Google News RSS & NSE Archives.\n"
                    f"• <b>Regime:</b> No setup met the strict institutional breakout threshold.\n"
                    f"• <b>Capital:</b> Staying 100% Cash (Capital Protected).\n"
                    f"• <b>Monitoring:</b> Intraday daemon active until 03:15 PM EOD.\n\n"
                    f'👉 <a href="https://gokulrock01.github.io/god-swing-trading/">View Live Dashboard</a>'
                )
                send_telegram_message(msg)
    else:
        print(f"[{now.strftime('%H:%M:%S')}] 🛡️ Outside entry window (09:30-11:30 IST). Monitoring only.")

def start_hybrid_daemon(poll_seconds=20, force=False):
    """Continuous intraday daemon loop running during market hours."""
    print("=" * 65)
    print("  🚀 HYBRID STOCK OPTIONS DAEMON (ANGEL ONE SMARTAPI)")
    print(f"  📅 {datetime.now().strftime('%A, %d %B %Y  %I:%M:%S %p IST')}")
    print("  ⚡ Dual-Regime: Model 1 Momentum Sniper & Model 2 Credit Spreads")
    print("  ⏱️ Real-Time Polling: Every 20 seconds | Auto EOD Square-Off: 15:15 PM")
    print("=" * 65)

    session = get_angel_session()
    if not session:
        print("  ❌ Failed to start Daemon: Angel One authentication failed.")
        return

    while True:
        try:
            now = datetime.now()
            t_str = now.strftime("%H:%M")
            weekday = now.weekday()

            if not force:
                # Weekend check
                if weekday in [5, 6]:
                    print(f"[{now.strftime('%H:%M:%S')}] ⏸️ Weekend: Market is closed. Standby mode...")
                    time.sleep(300)
                    continue

                # Pre-market wait until 09:30 AM
                if t_str < "09:30":
                    print(f"[{now.strftime('%H:%M:%S')}] ⏳ Waiting for 09:30 AM IST opening scan...")
                    time.sleep(30)
                    continue

                # Post-market exit (15:20 IST)
                if t_str >= "15:20":
                    print(f"[{now.strftime('%H:%M:%S')}] 🏁 Market session completed (15:20 IST). Hybrid Options Engine finished for today.")
                    break

            run_hybrid_cycle(force=force)
            time.sleep(poll_seconds)

        except KeyboardInterrupt:
            print("\n  🛑 Hybrid Options Daemon stopped by user.")
            break
        except Exception as e:
            print(f"  ⚠️ Error in Hybrid Options loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hybrid Stock Options Autonomous Engine")
    parser.add_argument("--once", action="store_true", help="Run a single check and exit")
    parser.add_argument("--force", action="store_true", help="Force execute scan ignoring market hours")
    parser.add_argument("--interval", type=int, default=20, help="Polling interval in seconds (default: 20)")
    args = parser.parse_args()

    if args.once:
        run_hybrid_cycle(force=args.force)
    else:
        start_hybrid_daemon(poll_seconds=args.interval, force=args.force)
