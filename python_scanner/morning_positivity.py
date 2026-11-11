#!/usr/bin/env python3
"""
GOD TRADING SYSTEM — 07:00 AM DAILY MORNING POSITIVITY ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dispatches unique, uplifting morning messages & mindset boosts
to all 3 dedicated Telegram bots every day at 07:00 AM IST.

Bots Covered:
1. @Godoptions_bot   (Nifty Options Sentinel)
2. @BTSTALERTbot     (Institutional BTST Engine)
3. @Godswingalertbot (God Swing Trading Engine)

Each bot gets a distinct quote & wisdom thought every single day,
tailored with market holiday awareness and empowering positivity.
"""

import sys
import os
import datetime
import requests

# Curated library of 35 uplifting, disciplined, and empowering daily thoughts
DAILY_WISDOM = [
    {
        "theme": "Clarity & Calm",
        "quote": "The market is a device for transferring money from the impatient to the patient.",
        "author": "Warren Buffett",
        "thought": "Start today with a calm, unhurried mind. True strength is not reacting to noise, but staying anchored to your plan."
    },
    {
        "theme": "Discipline & Mastery",
        "quote": "We don't rise to the level of our expectations, we fall to the level of our training.",
        "author": "Archilochus",
        "thought": "Consistency beats brilliance. Focus on flawless execution, manage your risk with pride, and let compounding take care of the rest."
    },
    {
        "theme": "Gratitude & Energy",
        "quote": "When you arise in the morning, think of what a precious privilege it is to be alive—to breathe, to think, to enjoy, to love.",
        "author": "Marcus Aurelius",
        "thought": "Today is a fresh canvas with zero mistakes in it yet. Approach every opportunity with gratitude, curiosity, and high energy."
    },
    {
        "theme": "Patience & Growth",
        "quote": "The trees that are slow to grow bear the best fruit.",
        "author": "Molière",
        "thought": "Never rush the harvest. The wealth you build step-by-step with calm discipline will outlast any shortcut. Trust your journey."
    },
    {
        "theme": "Courage & Resilience",
        "quote": "Success is not final, failure is not fatal: it is the courage to continue that counts.",
        "author": "Winston Churchill",
        "thought": "Every challenge is simply data teaching you how to get sharper. Stand tall, protect your capital, and welcome today's opportunities."
    },
    {
        "theme": "Emotional Balance",
        "quote": "He who conquers himself is the mightiest warrior.",
        "author": "Confucius",
        "thought": "Mastering your own emotions is the greatest edge in life and markets. Keep your heart calm and your mind sharp today."
    },
    {
        "theme": "Focus & Simplicity",
        "quote": "Simplicity is the ultimate sophistication.",
        "author": "Leonardo da Vinci",
        "thought": "Cut out the unnecessary clutter. Trade less, observe more, and execute with absolute conviction when your setup appears."
    },
    {
        "theme": "Unshakable Confidence",
        "quote": "Believe you can and you're halfway there.",
        "author": "Theodore Roosevelt",
        "thought": "You have prepared, backtested, and engineered a solid system. Walk into today with full self-belief and quiet confidence."
    },
    {
        "theme": "The Compound Effect",
        "quote": "Small disciplines repeated with consistency every day lead to great achievements gained slowly over time.",
        "author": "John C. Maxwell",
        "thought": "A 1% improvement today seems tiny, but compounded daily it transforms your entire life. Celebrate small wins."
    },
    {
        "theme": "Presence of Mind",
        "quote": "The secret of health for both mind and body is not to mourn for the past, nor to worry about the future, but to live the present moment wisely.",
        "author": "Buddha",
        "thought": "Yesterday’s trades are history; tomorrow is an imagination. Today is where your power lives. Stay 100% present."
    },
    {
        "theme": "Vision & Purpose",
        "quote": "The only limit to our realization of tomorrow will be our doubts of today.",
        "author": "Franklin D. Roosevelt",
        "thought": "Dream big, but build grounded. Your long-term vision is already in motion. Take today's steps with joyful certainty."
    },
    {
        "theme": "Inner Peace",
        "quote": "Peace comes from within. Do not seek it without.",
        "author": "Siddhartha Gautama",
        "thought": "No market tick or outside noise can disturb your inner calm unless you allow it. Guard your peace of mind above all else today."
    },
    {
        "theme": "Excellence & Habits",
        "quote": "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
        "author": "Aristotle",
        "thought": "Every disciplined choice you make today builds the trader and the person you are becoming. Choose excellence."
    },
    {
        "theme": "Adaptability",
        "quote": "Be like water making its way through cracks. Do not be assertive, but adjust to the object, and you shall find a way around or through it.",
        "author": "Bruce Lee",
        "thought": "Markets change, weather changes, life changes. Stay flexible, flow with the trend, and adapt with effortless grace."
    },
    {
        "theme": "Self-Mastery",
        "quote": "You have power over your mind - not outside events. Realize this, and you will find strength.",
        "author": "Marcus Aurelius",
        "thought": "You cannot control the waves, but you can always control your sail. Sail with calm poise today."
    },
    {
        "theme": "Abundance Mindset",
        "quote": "Doing what you love is the cornerstone of having abundance in your life.",
        "author": "Wayne Dyer",
        "thought": "The market and life offer infinite opportunities. Never chase out of fear of missing out; what is meant for you will arrive on time."
    },
    {
        "theme": "Patience in Solitude",
        "quote": "All of humanity's problems stem from man's inability to sit quietly in a room alone.",
        "author": "Blaise Pascal",
        "thought": "Waiting is an active trading decision. Sitting in cash and waiting for an institutional A+ setup is peak sophistication."
    },
    {
        "theme": "Relentless Optimism",
        "quote": "Keep your face always toward the sunshine—and shadows will fall behind you.",
        "author": "Walt Whitman",
        "thought": "Focus your attention on solutions, growth, and gratitude. Positive momentum follows where your focus goes."
    },
    {
        "theme": "Execution Over Emotion",
        "quote": "Amateurs hope; professionals manage risk and follow their plan.",
        "author": "Trading Axiom",
        "thought": "Trading is not about being right on every single tick; it is about following your system with calm, unwavering consistency."
    },
    {
        "theme": "Gratitude & Joy",
        "quote": "Gratitude turns what we have into enough, and more.",
        "author": "Melody Beattie",
        "thought": "Take a deep breath and appreciate how far you have come. You are building something lasting. Enjoy today."
    },
    {
        "theme": "Quiet Confidence",
        "quote": "True confidence has no need for loudness. It rests in quiet certainty.",
        "author": "Lao Tzu",
        "thought": "Let your preparation speak for itself. You do not need to prove anything to anyone—just execute your rules."
    },
    {
        "theme": "The Power of Today",
        "quote": "Today is not just another day, but another possible chance to achieve what couldn't be achieved yesterday.",
        "author": "Unknown",
        "thought": "Embrace this morning with fresh enthusiasm. Reset your mindset to zero and welcome the gifts of today."
    },
    {
        "theme": "Harmony & Flow",
        "quote": "Nature does not hurry, yet everything is accomplished.",
        "author": "Lao Tzu",
        "thought": "Step out of urgency. Great wealth and deep wisdom grow naturally when you allow them time to develop."
    },
    {
        "theme": "Mental Fortitude",
        "quote": "He who has a why to live can bear almost any how.",
        "author": "Friedrich Nietzsche",
        "thought": "Remember why you started this journey: freedom, autonomy, and generational wealth. Let that purpose fuel your discipline."
    },
    {
        "theme": "Focus on the Process",
        "quote": "Focus on the process, and the results will take care of themselves.",
        "author": "Nick Saban",
        "thought": "Detach your happiness from individual trade outcomes. Fall in love with executing your rules impeccably."
    },
    {
        "theme": "Unwavering Peace",
        "quote": "Rule your mind or it will rule you.",
        "author": "Horace",
        "thought": "Before the bell rings or the day begins, give yourself 5 minutes of silence. A quiet mind sees what others miss."
    },
    {
        "theme": "Humility & Respect",
        "quote": "In the beginner's mind there are many possibilities, but in the expert's there are few.",
        "author": "Shunryu Suzuki",
        "thought": "Keep your ego small and your curiosity large. Respect the market, respect risk, and always remain a humble student."
    },
    {
        "theme": "Steady Progress",
        "quote": "It does not matter how slowly you go as long as you do not stop.",
        "author": "Confucius",
        "thought": "Brick by brick, day by day. Every single day of disciplined behavior moves you closer to financial sovereignty."
    },
    {
        "theme": "Courage to Act",
        "quote": "In any moment of decision, the best thing you can do is the right thing, the next best is the wrong thing, and the worst is nothing.",
        "author": "Theodore Roosevelt",
        "thought": "When your proven setup appears, execute without hesitation or fear. You have tested this system thousands of times."
    },
    {
        "theme": "Joy of Living",
        "quote": "Live each day as if your life had just begun.",
        "author": "Johann Wolfgang von Goethe",
        "thought": "Release all baggage from the past. Today is full of vitality, new ideas, and boundless potential. Smile and thrive."
    },
    {
        "theme": "Risk Management First",
        "quote": "Rule No. 1: Never lose money. Rule No. 2: Never forget rule No. 1.",
        "author": "Warren Buffett",
        "thought": "Protecting your downside guarantees that you will be around to harvest the upside. Wear your stop-losses with honor."
    },
    {
        "theme": "Freedom of Mind",
        "quote": "The greatest victory is that which requires no battle.",
        "author": "Sun Tzu",
        "thought": "The most profitable trades often feel the easiest because you flowed with the prevailing momentum without fighting it."
    },
    {
        "theme": "Kindness & Grace",
        "quote": "No act of kindness, no matter how small, is ever wasted.",
        "author": "Aesop",
        "thought": "Carry warmth and generosity in your heart today. Being successful is sweetest when you lift up those around you."
    },
    {
        "theme": "Enduring Fortitude",
        "quote": "Doubt is a killer. You just have to know who you are and what you stand for.",
        "author": "Jennifer Lopez",
        "thought": "Trust your preparation. You have built rock-solid algorithms, backtested them rigorously, and automated your edge."
    },
    {
        "theme": "Radiant Energy",
        "quote": "Wherever you go, no matter what the weather, always bring your own sunshine.",
        "author": "Anthony J. D'Angelo",
        "thought": "Bring infectious positivity to everything you touch today. Your energy will attract the best outcomes!"
    }
]

def get_holiday_status(target_date):
    """Returns formatted market status using nse_holiday_guard if available."""
    try:
        sys.path.insert(0, "/Users/gokul/GOD")
        from nse_holiday_guard import is_market_open_today
        is_open, reason, next_session = is_market_open_today(target_date)
        if is_open:
            return "🏛️ <b>Market Status:</b> Active Trading Day (Market opens at 09:15 AM IST)\n"
        else:
            return f"🏖️ <b>Market Status:</b> {reason} (Next session: {next_session})\n"
    except Exception:
        # Fallback check for weekend
        if target_date.weekday() >= 5:
            return "🧘 <b>Market Status:</b> Weekend Pause (Enjoy your time to rest & recharge)\n"
        return "🏛️ <b>Market Status:</b> Trading Session scheduled for 09:15 AM IST\n"

def format_bot_message(bot_title, bot_icon, wisdom_entry, target_date):
    formatted_date = target_date.strftime("%A, %d %B %Y")
    holiday_info = get_holiday_status(target_date)

    msg = (
        f"🌅 <b>GOOD MORNING FROM {bot_title}</b> {bot_icon}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Date:</b> {formatted_date}\n"
        f"{holiday_info}\n"
        f"🌟 <b>Today's Mindset:</b> {wisdom_entry['theme']}\n\n"
        f"💬 <i>\"{wisdom_entry['quote']}\"</i>\n"
        f"— <b>{wisdom_entry['author']}</b>\n\n"
        f"💡 <b>Thought for the Day:</b>\n"
        f"{wisdom_entry['thought']}\n\n"
        f"✨ <i>May your day be filled with peace, unshakeable focus, disciplined execution, and great success!</i> ☕🚀"
    )
    return msg

def load_bot_configs():
    """Dynamically load tokens and chat_ids from config files or environment."""
    # 1. Options Bot
    options_tok = os.getenv("TELEGRAM_BOT_TOKEN")
    if not options_tok:
        try:
            sys.path.insert(0, "/Users/gokul/GOD")
            import config as god_cfg
            options_tok = getattr(god_cfg, "TELEGRAM_BOT_TOKEN", "9195212668:AAFRAxvb8GNdXxyYekIfJknkmrDEAgF0lfw")
        except Exception:
            options_tok = "9195212668:AAFRAxvb8GNdXxyYekIfJknkmrDEAgF0lfw"

    # 2. BTST Bot
    btst_tok = os.getenv("BTST_BOT_TOKEN")
    if not btst_tok:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("btst_cfg", "/Users/gokul/GOD_BTST/config.py")
            btst_cfg = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(btst_cfg)
            btst_tok = getattr(btst_cfg, "BTST_BOT_TOKEN", "9047159970:AAHYxR3STsJO83ACYlFIjrP9UP1t97VFGTk")
        except Exception:
            btst_tok = "9047159970:AAHYxR3STsJO83ACYlFIjrP9UP1t97VFGTk"

    # 3. Swing Bot
    swing_tok = os.getenv("SWING_BOT_TOKEN")
    if not swing_tok:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("swing_cfg", "/Users/gokul/GOD/SwingTradingSystem/python_scanner/config.py")
            swing_cfg = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(swing_cfg)
            swing_tok = getattr(swing_cfg, "SWING_BOT_TOKEN", "9087683073:AAHrRxkXIXpG3RIc61tEoINvo1WmpijH7f4")
        except Exception:
            swing_tok = "9087683073:AAHrRxkXIXpG3RIc61tEoINvo1WmpijH7f4"

    chat_id = os.getenv("TELEGRAM_CHAT_ID", "607732212")

    return [
        {
            "name": "NIFTY & STOCK OPTIONS SENTINEL",
            "icon": "⚡",
            "token": options_tok,
            "handle": "@Godoptions_bot",
            "chat_id": chat_id,
            "offset": 0
        },
        {
            "name": "INSTITUTIONAL BTST ENGINE",
            "icon": "🌙",
            "token": btst_tok,
            "handle": "@BTSTALERTbot",
            "chat_id": chat_id,
            "offset": 11
        },
        {
            "name": "GOD SWING TRADING ENGINE",
            "icon": "📈",
            "token": swing_tok,
            "handle": "@Godswingalertbot",
            "chat_id": chat_id,
            "offset": 23
        }
    ]

def dispatch_daily_morning_messages(dry_run=False):
    today = datetime.date.today()
    day_of_year = today.timetuple().tm_yday
    num_quotes = len(DAILY_WISDOM)

    bot_configs = load_bot_configs()

    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🌅 07:00 AM Morning Positivity Dispatcher Running...")
    print(f"  📅 Target Date: {today.strftime('%Y-%m-%d (%A)')} | Day of Year: {day_of_year}")
    if dry_run:
        print("  🔍 MODE: DRY RUN (Messages will be printed to console only)\n")

    for bot in bot_configs:
        quote_index = (day_of_year + bot["offset"]) % num_quotes
        wisdom = DAILY_WISDOM[quote_index]
        msg = format_bot_message(bot["name"], bot["icon"], wisdom, today)

        if dry_run:
            print(f"━━━━━━━━━━ PREVIEW FOR {bot['handle']} ({bot['name']}) ━━━━━━━━━━")
            print(msg)
            print()
            continue

        url = f"https://api.telegram.org/bot{bot['token']}/sendMessage"
        payload = {
            "chat_id": bot["chat_id"],
            "text": msg,
            "parse_mode": "HTML"
        }
        try:
            r = requests.post(url, json=payload, timeout=12)
            if r.status_code == 200:
                print(f"  ✅ Sent successfully to {bot['handle']} (Theme: '{wisdom['theme']}')")
            else:
                print(f"  ⚠️ Error from {bot['handle']}: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"  ❌ Network error reaching {bot['handle']}: {e}")

if __name__ == "__main__":
    is_dry_run = "--dry-run" in sys.argv or "--test" in sys.argv
    dispatch_daily_morning_messages(dry_run=is_dry_run)
