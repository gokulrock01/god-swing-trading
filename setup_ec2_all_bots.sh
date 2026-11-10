#!/bin/bash
# ==============================================================================
# GOD TRADING SYSTEM — ALL-IN-ONE AWS EC2 CLOUD SENTINEL SETUP (MUMBAI)
# ==============================================================================
# Deploys and manages all 3 bots simultaneously on Ubuntu:
#   1. Bot 1: Hybrid Stock Options Engine (Momentum Sniper + Credit Spread + NewsGuard)
#   2. Bot 2: Nifty & Sensex Index Options Sentinel (Iron Condor / Short Strangle)
#   3. Bot 3: GOD BTST Options Orderflow Engine (EOD CVD & 9:15 AM Exit)
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 Starting God Trading System Setup on AWS EC2 (Mumbai)..."
echo "📅 $(date)"
echo "=========================================================="

# 1. Update OS and install prerequisites
echo "📦 Installing system dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl htop tzdata

# Set timezone to Asia/Kolkata (IST)
echo "⏰ Setting server timezone to Asia/Kolkata (IST)..."
sudo timedatectl set-timezone Asia/Kolkata

# 2. Setup 1GB Swap File for memory safety buffer
if [ ! -f /swapfile ]; then
    echo "🧠 Creating 1GB swap memory buffer..."
    sudo fallocate -l 1G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# 3. Create bot home directory
WORK_DIR="$HOME/trading_system"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# 4. Clone / Pull repositories
echo "📥 Cloning Repositories..."

# Bot 1: God Swing Trading (Hybrid Stock Options)
if [ ! -d "god-swing-trading" ]; then
    git clone https://github.com/gokulrock01/god-swing-trading.git
else
    cd god-swing-trading && git pull origin main && cd ..
fi

# Bot 2: Nifty Options Sentinel
if [ ! -d "nifty-options-sentinel" ]; then
    git clone https://github.com/gokulrock01/nifty-options-sentinel.git
else
    cd nifty-options-sentinel && git pull origin main && cd ..
fi

# Bot 3: GOD BTST
if [ ! -d "GOD_BTST" ]; then
    git clone https://github.com/gokulrock01/GOD_BTST.git
else
    cd GOD_BTST && git pull origin main && cd ..
fi

# 5. Setup Python Virtual Environment
echo "🐍 Setting up Python Virtual Environment..."
python3 -m venv "$WORK_DIR/venv"
source "$WORK_DIR/venv/bin/activate"

pip install --upgrade pip
pip install smartapi-python pyotp logzero websocket-client requests pandas numpy yfinance vaderSentiment

# 6. Configure Unified Credentials for All 3 Bots
echo "🔐 Configuring API & Telegram Credentials for all 3 engines..."

# Shared Angel One Credentials
ANGEL_KEY="${ANGEL_API_KEY:-uoY0Ego2}"
ANGEL_CODE="${ANGEL_CLIENT_CODE:-D216926}"
ANGEL_P="${ANGEL_PIN:-0514}"
ANGEL_TOTP="${ANGEL_TOTP_KEY:-JV37OTDOLAZEGFH3VXCCCJ66EA}"

SWING_TOKEN="${SWING_BOT_TOKEN:-9087683073:AAHrRxkXIXpG3RIc61tEoINvo1WmpijH7f4}"
NIFTY_TOKEN="${NIFTY_BOT_TOKEN:-9195212668:AAFRAxvb8GNdXxyYekIfJknkmrDEAgF0lfw}"
BTST_TOKEN="${BTST_BOT_TOKEN:-9047159970:AAHYxR3STsJO83ACYlFIjrP9UP1t97VFGTk}"
CHAT_ID="${TELEGRAM_CHAT_ID:-607732212}"

# Bot 1: God Swing Trading (Hybrid Stock Options)
cat << EOF > "$WORK_DIR/god-swing-trading/python_scanner/config.py"
import os
SWING_BOT_TOKEN    = os.getenv("SWING_BOT_TOKEN", "$SWING_TOKEN")
GOD_SWING_ID       = os.getenv("GOD_SWING_ID", "$CHAT_ID")
TELEGRAM_BOT_TOKEN = SWING_BOT_TOKEN
TELEGRAM_CHAT_ID   = GOD_SWING_ID

ANGEL_API_KEY      = os.getenv("ANGEL_API_KEY", "$ANGEL_KEY")
ANGEL_CLIENT_CODE  = os.getenv("ANGEL_CLIENT_CODE", "$ANGEL_CODE")
ANGEL_PIN          = os.getenv("ANGEL_PIN", "$ANGEL_P")
ANGEL_TOTP_KEY     = os.getenv("ANGEL_TOTP_KEY", "$ANGEL_TOTP")
EOF
cp "$WORK_DIR/god-swing-trading/python_scanner/config.py" "$WORK_DIR/god-swing-trading/config.py"

# Bot 2: Nifty & Sensex Index Options Sentinel
cat << EOF > "$WORK_DIR/nifty-options-sentinel/config.py"
import os
ACTIVE_DATA_SOURCE = os.getenv("ACTIVE_DATA_SOURCE", "ANGELONE")
ANGEL_API_KEY      = os.getenv("ANGEL_API_KEY", "$ANGEL_KEY")
ANGEL_CLIENT_CODE  = os.getenv("ANGEL_CLIENT_CODE", "$ANGEL_CODE")
ANGEL_PIN          = os.getenv("ANGEL_PIN", "$ANGEL_P")
ANGEL_TOTP_KEY     = os.getenv("ANGEL_TOTP_KEY", "$ANGEL_TOTP")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "$NIFTY_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "$CHAT_ID")

INDEX_NAME            = os.getenv("INDEX_NAME", "NIFTY")
ENTRY_TIME            = os.getenv("ENTRY_TIME", "09:35")
EXIT_TIME             = os.getenv("EXIT_TIME", "15:10")
STOP_LOSS_PERCENT     = float(os.getenv("STOP_LOSS_PERCENT", "30.0"))
PROFIT_LOCK_DECAY_PCT = float(os.getenv("PROFIT_LOCK_DECAY_PCT", "50.0"))
PROFIT_LOCK_SL_PCT    = float(os.getenv("PROFIT_LOCK_SL_PCT", "70.0"))
TAKE_PROFIT_DECAY_PCT = float(os.getenv("TAKE_PROFIT_DECAY_PCT", "80.0"))
OTM_STRIKE_OFFSET     = int(os.getenv("OTM_STRIKE_OFFSET", "100"))
HEDGE_STRIKE_OFFSET   = int(os.getenv("HEDGE_STRIKE_OFFSET", "250"))
LOT_SIZE              = int(os.getenv("LOT_SIZE", "25"))
EOF

# Bot 3: GOD BTST Engine
cat << EOF > "$WORK_DIR/GOD_BTST/config.py"
import os
BTST_BOT_TOKEN     = os.getenv("BTST_BOT_TOKEN", "$BTST_TOKEN")
BTST_ID            = os.getenv("BTST_ID", "$CHAT_ID")
TELEGRAM_BOT_TOKEN = BTST_BOT_TOKEN
TELEGRAM_CHAT_ID   = BTST_ID

ANGEL_API_KEY      = os.getenv("ANGEL_API_KEY", "$ANGEL_KEY")
ANGEL_CLIENT_CODE  = os.getenv("ANGEL_CLIENT_CODE", "$ANGEL_CODE")
ANGEL_PIN          = os.getenv("ANGEL_PIN", "$ANGEL_P")
ANGEL_TOTP_KEY     = os.getenv("ANGEL_TOTP_KEY", "$ANGEL_TOTP")
EOF

# 7. Create Systemd Service for Bot 1 (Hybrid Stock Options Engine)
echo "⚙️ Creating Linux background services (systemd)..."

sudo tee /etc/systemd/system/god-hybrid-options.service > /dev/null << EOF
[Unit]
Description=God Hybrid Stock Options Engine (Angel One)
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR/god-swing-trading
ExecStart=$WORK_DIR/venv/bin/python $WORK_DIR/god-swing-trading/python_scanner/hybrid_stock_options_engine.py
Restart=always
RestartSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 8. Create Systemd Service for Bot 2 (Nifty Options Sentinel)
sudo tee /etc/systemd/system/god-nifty-sentinel.service > /dev/null << EOF
[Unit]
Description=God Nifty & Sensex Index Options Sentinel
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR/nifty-options-sentinel
ExecStart=$WORK_DIR/venv/bin/python $WORK_DIR/nifty-options-sentinel/angel_watcher.py
Restart=always
RestartSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 9. Configure Crontab for Bot 3 (GOD BTST Engine at 09:15 AM and 03:15 PM)
echo "⏰ Configuring Cron triggers for BTST Engine..."

# Create cron entry for BTST
CRON_CMD_SCAN="15 15 * * 1-5 cd $WORK_DIR/GOD_BTST && $WORK_DIR/venv/bin/python automation_engine.py --mode scan >> $WORK_DIR/btst_scan.log 2>&1"
CRON_CMD_EXIT="15 9 * * 1-5 cd $WORK_DIR/GOD_BTST && $WORK_DIR/venv/bin/python automation_engine.py --mode morning-exit >> $WORK_DIR/btst_exit.log 2>&1"

(crontab -l 2>/dev/null | grep -v "automation_engine.py" ; echo "$CRON_CMD_SCAN" ; echo "$CRON_CMD_EXIT") | crontab -

# 10. Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable god-hybrid-options.service
sudo systemctl enable god-nifty-sentinel.service
sudo systemctl restart god-hybrid-options.service
sudo systemctl restart god-nifty-sentinel.service

echo "=========================================================="
echo "🎉 ALL 3 BOTS ARE DEPLOYED AND RUNNING 24/7 IN THE CLOUD!"
echo "=========================================================="
echo "• Bot 1 (Hybrid Stock Options): Active [systemctl status god-hybrid-options]"
echo "• Bot 2 (Nifty Index Sentinel): Active [systemctl status god-nifty-sentinel]"
echo "• Bot 3 (BTST Engine): Scheduled via Crontab (09:15 AM & 03:15 PM IST)"
echo "• Check logs anytime: journalctl -u god-hybrid-options -f"
echo "=========================================================="
