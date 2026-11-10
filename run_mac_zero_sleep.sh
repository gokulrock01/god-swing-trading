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

# 1. Send Startup Telegram Dispatch
"$DIR/venv/bin/python" - << 'EOF'
import requests, os

# Bot 1 & 2 Telegram Tokens
SWING_TOKEN = "9087683073:AAHrRxkXIXpG3RIc61tEoINvo1WmpijH7f4"
NIFTY_TOKEN = "9195212668:AAFRAxvb8GNdXxyYekIfJknkmrDEAgF0lfw"
CHAT_ID = "607732212"

msg = (
    "⚡ <b>GOD TRADING SYSTEM: ALL 3 BOTS ACTIVE (ZERO-SLEEP)</b>\n\n"
    "• <b>Status:</b> macOS Caffeinate Active (No Sleep / No Wi-Fi Drop) ✅\n"
    "• <b>Engine 1:</b> Hybrid Stock Options (TATASTEEL / F&O Momentum)\n"
    "• <b>Engine 2:</b> Nifty Index Options (09:35 AM Strangle + Profit-Lock)\n"
    "• <b>Engine 3:</b> GOD BTST Orderflow (09:15 AM Exit + 03:15 PM Scan)\n"
    "• <b>Live Session:</b> Streaming until 03:30 PM EOD\n"
)

for token in [SWING_TOKEN, NIFTY_TOKEN]:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass
EOF

export PYTHONUNBUFFERED=1

# 2. Check 09:15 AM BTST Morning Exit
CURRENT_TIME=$(date +'%H:%M')
if [[ "$CURRENT_TIME" < "10:30" ]]; then
    if [ -d "/Users/gokul/Downloads/GOD_BTST" ]; then
        echo "[$(date)] 🌅 Checking BTST 09:15 AM Morning Exits..." >> "$LOG_FILE"
        (cd "/Users/gokul/Downloads/GOD_BTST" && "$DIR/venv/bin/python" automation_engine.py --mode morning-exit >> "$DIR/logs/btst_morning.log" 2>&1 || true) &
    fi
fi

# 3. Launch Engine 1: Hybrid Stock Options Engine in background
echo "[$(date)] 🚀 Launching Engine 1: Hybrid Stock Options..." >> "$LOG_FILE"
caffeinate -d -i -m -u -s "$DIR/venv/bin/python" -u "$DIR/SwingTradingSystem/python_scanner/hybrid_stock_options_engine.py" --force >> "$LOG_FILE" 2>&1 &
STOCK_ENGINE_PID=$!
echo "[$(date)] Engine 1 (Stock Options) active with PID: $STOCK_ENGINE_PID" >> "$LOG_FILE"

# 4. Launch Engine 2: Nifty & Sensex Index Options Sentinel in background
echo "[$(date)] 🚀 Launching Engine 2: Nifty Index Options Sentinel..." >> "$LOG_FILE"
caffeinate -d -i -m -u -s "$DIR/venv/bin/python" -u "$DIR/angel_watcher.py" >> "$DIR/logs/nifty_sentinel.log" 2>&1 &
INDEX_ENGINE_PID=$!
echo "[$(date)] Engine 2 (Index Sentinel) active with PID: $INDEX_ENGINE_PID" >> "$LOG_FILE"

# 5. Monitor and Trigger Engine 3 (BTST EOD Screener at 03:15 PM)
BTST_TRIGGERED=false
while true; do
    CURRENT_TIME=$(date +'%H:%M')
    
    # 03:15 PM BTST Scan Trigger
    if [[ "$CURRENT_TIME" > "15:14" ]] && [ "$BTST_TRIGGERED" = false ]; then
        echo "[$(date)] 🎯 03:15 PM reached: Triggering EOD BTST Screener..." >> "$LOG_FILE"
        if [ -d "/Users/gokul/Downloads/GOD_BTST" ]; then
            (cd "/Users/gokul/Downloads/GOD_BTST" && "$DIR/venv/bin/python" automation_engine.py --mode scan >> "$DIR/logs/btst_eod.log" 2>&1 || true)
        fi
        BTST_TRIGGERED=true
    fi
    
    # 03:30 PM Market Close & Clean Shutdown
    if [[ "$CURRENT_TIME" > "15:30" ]] || [[ "$CURRENT_TIME" == "15:30" ]]; then
        echo "[$(date)] 🏁 03:30 PM Market Closed. Safely stopping engines..." >> "$LOG_FILE"
        kill -15 $STOCK_ENGINE_PID 2>/dev/null || true
        kill -15 $INDEX_ENGINE_PID 2>/dev/null || true
        break
    fi
    
    sleep 20
done

echo "==========================================================" >> "$LOG_FILE"
echo "✅ All 3 Engines successfully completed for today." >> "$LOG_FILE"
echo "==========================================================" >> "$LOG_FILE"
