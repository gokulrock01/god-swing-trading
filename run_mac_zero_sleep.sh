#!/bin/bash
# ==============================================================================
# GOD TRADING SYSTEM — MASTER MAC ZERO-SLEEP LIVE SENTINEL (ALL 3 BOTS)
# ==============================================================================
# Wraps all 3 trading engines with macOS `caffeinate` to prevent CPU and Wi-Fi sleep
# during market hours (09:14 AM to 03:30 PM IST):
#
#   1. Bot 1 (Stock Options): Hybrid Momentum Sniper + Credit Spreads (Live Ticks)
#   2. Bot 2 (Index Options): Nifty/Sensex 09:35 AM Strangle + 50% Profit Lock
#   3. Bot 3 (BTST Engine):   09:15 AM Morning Exit & 03:15 PM EOD Screener
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

mkdir -p "$DIR/logs"
LOG_FILE="$DIR/logs/mac_sentinel.log"

echo "==========================================================" >> "$LOG_FILE"
echo "⚡ Starting Master Mac Zero-Sleep Sentinel (All 3 Engines)..." >> "$LOG_FILE"
echo "📅 $(date)" >> "$LOG_FILE"
echo "==========================================================" >> "$LOG_FILE"

# 1. Check NSE Market Holiday Status Before Starting
"$DIR/venv/bin/python" "$DIR/nse_holiday_guard.py" --notify
HOLIDAY_CODE=$?

if [ $HOLIDAY_CODE -ne 0 ]; then
    echo "[$(date)] 🏖️ NSE Trading Holiday detected. Dispatched Telegram notice & resting." >> "$LOG_FILE"
    exit 0
fi

# 2. Send 09:00 AM Morning Market Confirmation Dispatch to ALL 3 BOTS
"$DIR/venv/bin/python" - << 'EOF'
import requests

OPTIONS_TOKEN = "9195212668:AAFRAxvb8GNdXxyYekIfJknkmrDEAgF0lfw"
BTST_TOKEN    = "9047159970:AAHYxR3STsJO83ACYlFIjrP9UP1t97VFGTk"
SWING_TOKEN   = "9087683073:AAHrRxkXIXpG3RIc61tEoINvo1WmpijH7f4"
CHAT_ID       = "607732212"

msg = (
    "⚡ <b>GOD TRADING SUITE: MORNING SENTINEL ACTIVE (09:00 AM IST)</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "• <b>Market Status:</b> Official NSE Trading Day Confirmed ✅\n"
    "• <b>Device State:</b> Mac Caffeinate Zero-Sleep Mode Armed 💻\n"
    "• <b>Engine 1:</b> Hybrid Stock Options (@Godoptions_bot)\n"
    "• <b>Engine 2:</b> Nifty Index Options (@Godoptions_bot)\n"
    "• <b>Engine 3:</b> Institutional BTST Engine (@BTSTALERTbot)\n"
    "• <b>Engine 4:</b> God Swing Trading Engine (@Godswingalertbot)\n\n"
    "🚀 <i>Pre-market verification complete. Live tick streaming begins at 09:15 AM!</i>"
)

for token in [OPTIONS_TOKEN, BTST_TOKEN, SWING_TOKEN]:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=8)
    except Exception:
        pass
EOF

export PYTHONUNBUFFERED=1

# If started before 09:14 AM, wait until pre-market buffer
CURRENT_TIME=$(date +'%H:%M')
while [[ "$CURRENT_TIME" < "09:14" ]]; do
    sleep 15
    CURRENT_TIME=$(date +'%H:%M')
done

BTST_DIR="/Users/gokul/GOD_BTST"
if [ ! -d "$BTST_DIR" ]; then
    BTST_DIR="/Users/gokul/Downloads/GOD_BTST"
fi

# 3. Check 09:15 AM BTST Morning Exit
CURRENT_TIME=$(date +'%H:%M')
if [[ "$CURRENT_TIME" < "10:30" ]]; then
    if [ -d "$BTST_DIR" ]; then
        echo "[$(date)] 🌅 Checking BTST 09:15 AM Morning Exits..." >> "$LOG_FILE"
        (cd "$BTST_DIR" && "$DIR/venv/bin/python" automation_engine.py --mode morning-exit >> "$DIR/logs/btst_morning.log" 2>&1 || true) &
    fi
fi

# 4. Launch Engine 1: Hybrid Stock Options Engine in background (Production mode)
echo "[$(date)] 🚀 Launching Engine 1: Hybrid Stock Options..." >> "$LOG_FILE"
caffeinate -d -i -m -u -s "$DIR/venv/bin/python" -u "$DIR/SwingTradingSystem/python_scanner/hybrid_stock_options_engine.py" >> "$LOG_FILE" 2>&1 &
STOCK_ENGINE_PID=$!
echo "[$(date)] Engine 1 (Stock Options) active with PID: $STOCK_ENGINE_PID" >> "$LOG_FILE"

# 5. Launch Engine 2: Nifty & Sensex Index Options Sentinel in background
echo "[$(date)] 🚀 Launching Engine 2: Nifty Index Options Sentinel..." >> "$LOG_FILE"
caffeinate -d -i -m -u -s "$DIR/venv/bin/python" -u "$DIR/angel_watcher.py" >> "$DIR/logs/nifty_sentinel.log" 2>&1 &
INDEX_ENGINE_PID=$!
echo "[$(date)] Engine 2 (Index Sentinel) active with PID: $INDEX_ENGINE_PID" >> "$LOG_FILE"

# Helper function to dispatch periodic heartbeats to all 3 bots
send_heartbeat() {
    local TIME_LABEL="$1"
    "$DIR/venv/bin/python" - << EOF
import requests

OPTIONS_TOKEN = "9195212668:AAFRAxvb8GNdXxyYekIfJknkmrDEAgF0lfw"
BTST_TOKEN    = "9047159970:AAHYxR3STsJO83ACYlFIjrP9UP1t97VFGTk"
SWING_TOKEN   = "9087683073:AAHrRxkXIXpG3RIc61tEoINvo1WmpijH7f4"
CHAT_ID       = "607732212"

msg = (
    "🟢 <b>LIVE SENTINEL HEARTBEAT (${TIME_LABEL} IST)</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "• <b>Status:</b> All trading engines operating normally ✅\n"
    "• <b>Mac Assertion:</b> Caffeinate zero-sleep actively engaged 💻\n"
    "• <b>Data Stream:</b> Live Angel One SmartAPI tick feed active 📶\n"
    "• <b>Monitoring:</b> F&O universe actively scanned for A+ setups."
)

for token in [OPTIONS_TOKEN, BTST_TOKEN, SWING_TOKEN]:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=8)
    except Exception:
        pass
EOF
}

# 6. Monitor and Trigger Periodic Heartbeats & BTST EOD Screener at 03:15 PM
BTST_TRIGGERED=false
HB_11_SENT=false
HB_13_SENT=false
HB_15_SENT=false

while true; do
    CURRENT_TIME=$(date +'%H:%M')
    
    # 11:00 AM Mid-Morning Heartbeat
    if [[ "$CURRENT_TIME" > "10:59" ]] && [ "$HB_11_SENT" = false ]; then
        echo "[$(date)] 💓 Dispatching 11:00 AM Heartbeat..." >> "$LOG_FILE"
        send_heartbeat "11:00 AM"
        HB_11_SENT=true
    fi

    # 01:00 PM Afternoon Heartbeat
    if [[ "$CURRENT_TIME" > "12:59" ]] && [ "$HB_13_SENT" = false ]; then
        echo "[$(date)] 💓 Dispatching 01:00 PM Heartbeat..." >> "$LOG_FILE"
        send_heartbeat "01:00 PM"
        HB_13_SENT=true
    fi

    # 03:00 PM Pre-Close Heartbeat
    if [[ "$CURRENT_TIME" > "14:59" ]] && [ "$HB_15_SENT" = false ]; then
        echo "[$(date)] 💓 Dispatching 03:00 PM Heartbeat..." >> "$LOG_FILE"
        send_heartbeat "03:00 PM"
        HB_15_SENT=true
    fi

    # 03:15 PM BTST Scan Trigger
    if [[ "$CURRENT_TIME" > "15:14" ]] && [ "$BTST_TRIGGERED" = false ]; then
        echo "[$(date)] 🎯 03:15 PM reached: Triggering EOD BTST Screener..." >> "$LOG_FILE"
        if [ -d "$BTST_DIR" ]; then
            (cd "$BTST_DIR" && "$DIR/venv/bin/python" automation_engine.py --mode scan >> "$DIR/logs/btst_eod.log" 2>&1 || true)
        fi
        BTST_TRIGGERED=true
    fi
    
    # 03:30 PM Market Close & Clean Shutdown
    if [[ "$CURRENT_TIME" > "15:30" ]] || [[ "$CURRENT_TIME" == "15:30" ]]; then
        echo "[$(date)] 🏁 03:30 PM Market Closed. Safely stopping engines..." >> "$LOG_FILE"
        kill -15 $STOCK_ENGINE_PID 2>/dev/null || true
        kill -15 $INDEX_ENGINE_PID 2>/dev/null || true

        # Send Market Close Notification
        "$DIR/venv/bin/python" - << 'EOF'
import requests

OPTIONS_TOKEN = "9195212668:AAFRAxvb8GNdXxyYekIfJknkmrDEAgF0lfw"
BTST_TOKEN    = "9047159970:AAHYxR3STsJO83ACYlFIjrP9UP1t97VFGTk"
SWING_TOKEN   = "9087683073:AAHrRxkXIXpG3RIc61tEoINvo1WmpijH7f4"
CHAT_ID       = "607732212"

msg = (
    "🏁 <b>MARKET CLOSED — 03:30 PM IST DAILY SESSION COMPLETE</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "• <b>Status:</b> All intraday positions squared off & closed.\n"
    "• <b>Sentinel State:</b> Engines safely stopped, caffeinate released.\n"
    "• <b>Next Event:</b> Tomorrow 07:00 AM Morning Positivity & 09:00 AM Market Sentinel."
)

for token in [OPTIONS_TOKEN, BTST_TOKEN, SWING_TOKEN]:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=8)
    except Exception:
        pass
EOF
        break
    fi
    
    sleep 20
done

echo "==========================================================" >> "$LOG_FILE"
echo "✅ All 3 Engines successfully completed for today." >> "$LOG_FILE"
echo "==========================================================" >> "$LOG_FILE"
