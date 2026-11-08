"""
==============================================================================
news_guard.py — Stock-Specific News & Earnings Sentinel for NSE Options
==============================================================================
Integrates into the Hybrid Stock Options Engine to provide:
  LAYER 1 — Pre-Trade:  Checks news sentiment & earnings day before entry
  LAYER 2 — Intraday:   Monitors for breaking news during active position
  LAYER 3 — Earnings:   Special mode on results day (CE/PE bias + wider SL)

Signals:
  AVOID_CE         → Bearish news → Skip CE buying
  AVOID_PE         → Bullish news → Skip PE buying
  EARNINGS_CE_BIAS → Results day, bullish bias → Prefer CE
  EARNINGS_PE_BIAS → Results day, bearish bias → Prefer PE
  CLEAR            → No significant news risk → Safe to trade

Data Sources (all FREE, no API key required):
  1. Google News RSS (India edition) — real-time, ~5-10 min lag
  2. NSE Archives Official RSS — authoritative results announcements
  3. NSE Event Calendar API — upcoming board meeting / earnings dates
  4. yfinance — earnings date fallback (.NS suffix)
  5. VADER Sentiment — offline NLP + custom Indian financial lexicon
==============================================================================
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import datetime
import re
import time
import requests
from email.utils import parsedate_to_datetime

# ---------------------------------------------------------------------------
# Optional: vaderSentiment (pip install vaderSentiment)
# Falls back to keyword matching if not installed
# ---------------------------------------------------------------------------
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER_AVAILABLE = True
except ImportError:
    _VADER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Optional: yfinance for earnings calendar
# ---------------------------------------------------------------------------
try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Indian Financial Sentiment Lexicon
# ---------------------------------------------------------------------------
BEARISH_KEYWORDS = [
    "crash", "plunge", "tumble", "slide", "slump", "collapse", "tank",
    "selloff", "sell-off", "bloodbath", "carnage", "rout",
    "lower circuit", "circuit breaker", "sebi notice", "sebi probe",
    "ed raid", "it raid", "income tax raid", "cbi probe",
    "fraud", "scam", "ponzi", "default", "npa rises", "npa surge",
    "fii selling", "fii outflow", "rate hike", "fed hawkish",
    "inflation surge", "crude jumps", "oil spike", "war", "escalat",
    "sanction", "downgrade", "recession fears",
    "profit falls", "profit drops", "net loss", "revenue miss",
    "below estimate", "misses estimate", "disappoints", "guidance cut",
    "dividend cut", "promoter sell",
]

BULLISH_KEYWORDS = [
    "rally", "surge", "soar", "skyrocket", "jump", "rebound",
    "bull run", "breakout", "all-time high", "record high", "52-week high",
    "upper circuit", "fii buying", "fii inflow", "dii buying",
    "buyback", "bonus share", "stock split", "dividend declared", "promoter buy",
    "rate cut", "fed dovish", "stimulus", "gdp beat",
    "crude drops", "oil falls", "upgrade", "outperform", "buy rating",
    "profit rises", "profit jumps", "beats estimate", "revenue beat",
    "record profit", "guidance raised", "strong results", "robust earnings",
]

CUSTOM_VADER_LEXICON = {
    "rally": 2.0, "surge": 2.0, "soar": 2.0, "breakout": 1.8,
    "bullish": 1.8, "buyback": 1.5, "upgrade": 1.5, "outperform": 1.5,
    "rebound": 1.5, "beat": 1.3, "robust": 1.4,
    "crash": -2.5, "plunge": -2.3, "slump": -1.8, "bearish": -1.8,
    "fraud": -3.0, "scam": -3.0, "default": -2.5, "downgrade": -1.8,
    "miss": -1.2, "disappoint": -1.5, "circuit": -1.5,
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Signal constants
SIGNAL_AVOID_CE    = "AVOID_CE"
SIGNAL_AVOID_PE    = "AVOID_PE"
SIGNAL_EARNINGS_CE = "EARNINGS_CE_BIAS"
SIGNAL_EARNINGS_PE = "EARNINGS_PE_BIAS"
SIGNAL_CLEAR       = "CLEAR"

SIGNAL_EMOJI = {
    SIGNAL_AVOID_CE:    "🔴",
    SIGNAL_AVOID_PE:    "🟢",
    SIGNAL_EARNINGS_CE: "🟡",
    SIGNAL_EARNINGS_PE: "🟡",
    SIGNAL_CLEAR:       "✅",
}


# =============================================================================
#  SECTION 1 — NEWS FETCHING
# =============================================================================

def fetch_google_news_rss(symbol: str, max_age_minutes: int = 60) -> list:
    """Fetches stock-specific breaking news from Google News RSS (India edition)."""
    query         = f"{symbol} NSE stock"
    encoded_query = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search?"
        f"q={encoded_query}+when:2h"
        f"&hl=en-IN&gl=IN&ceid=IN:en"
    )

    req      = urllib.request.Request(url, headers=BROWSER_HEADERS)
    articles = []

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        now  = datetime.datetime.now(datetime.timezone.utc)

        for item in root.findall(".//item"):
            title_el    = item.find("title")
            pub_date_el = item.find("pubDate")
            link_el     = item.find("link")
            source_el   = item.find("source")

            title  = title_el.text    if title_el    is not None else ""
            pub_str = pub_date_el.text if pub_date_el is not None else ""
            link   = link_el.text     if link_el     is not None else ""
            source = source_el.text   if source_el   is not None else "Google News"

            try:
                pub_dt      = parsedate_to_datetime(pub_str)
                age_minutes = (now - pub_dt).total_seconds() / 60.0
            except Exception:
                age_minutes = 0.0

            if age_minutes <= max_age_minutes:
                articles.append({
                    "title":       title,
                    "pub_date":    pub_str,
                    "age_minutes": round(age_minutes, 1),
                    "link":        link,
                    "source":      source,
                })

    except Exception as e:
        print(f"  [NewsGuard] ⚠️ Google News RSS failed for {symbol}: {e}")

    return articles


def fetch_nse_official_rss(symbol: str, max_age_minutes: int = 480) -> list:
    """Fetches official NSE Financial Results & Corporate Action announcements."""
    urls = [
        "https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml",
        "https://nsearchives.nseindia.com/content/RSS/Corporate_action.xml",
        "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml",
    ]

    headers = {**BROWSER_HEADERS, "Referer": "https://www.nseindia.com/"}
    matching = []
    symbol_upper = symbol.upper()

    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            now  = datetime.datetime.now(datetime.timezone.utc)

            for item in root.findall(".//item"):
                title_el    = item.find("title")
                desc_el     = item.find("description")
                pub_date_el = item.find("pubDate")
                link_el     = item.find("link")

                title   = title_el.text    if title_el    is not None else ""
                desc    = desc_el.text     if desc_el     is not None else ""
                pub_str = pub_date_el.text if pub_date_el is not None else ""
                link    = link_el.text     if link_el     is not None else ""

                combined = (title + " " + (desc or "")).upper()
                if symbol_upper not in combined:
                    continue

                try:
                    pub_dt      = parsedate_to_datetime(pub_str)
                    age_minutes = (now - pub_dt).total_seconds() / 60.0
                except Exception:
                    age_minutes = 0.0

                if age_minutes <= max_age_minutes:
                    matching.append({
                        "title":       title,
                        "description": desc,
                        "pub_date":    pub_str,
                        "age_minutes": round(age_minutes, 1),
                        "link":        link,
                        "source":      "NSE Official",
                    })

        except Exception as e:
            print(f"  [NewsGuard] ⚠️ NSE RSS failed ({url.split('/')[-1]}): {e}")

    return matching


# =============================================================================
#  SECTION 2 — SENTIMENT ANALYSIS
# =============================================================================

def _init_vader():
    if not _VADER_AVAILABLE:
        return None
    analyzer = SentimentIntensityAnalyzer()
    analyzer.lexicon.update(CUSTOM_VADER_LEXICON)
    return analyzer


_vader_analyzer = _init_vader()


def analyze_headline_sentiment(title: str):
    """Returns (label, score) for a headline. VADER if available, else keywords."""
    text = title.lower()

    if _VADER_AVAILABLE and _vader_analyzer:
        scores   = _vader_analyzer.polarity_scores(title)
        compound = scores["compound"]
        if compound >= 0.05:
            return "BULLISH", compound
        elif compound <= -0.05:
            return "BEARISH", compound
        return "NEUTRAL", compound
    else:
        bear_hits = sum(1 for kw in BEARISH_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", text))
        bull_hits = sum(1 for kw in BULLISH_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", text))
        net = bull_hits - bear_hits
        if net > 0:
            return "BULLISH", float(net)
        elif net < 0:
            return "BEARISH", float(net)
        return "NEUTRAL", 0.0


def score_articles(articles: list) -> dict:
    """Aggregates sentiment across multiple articles into an overall signal."""
    scored      = []
    bull_count  = 0
    bear_count  = 0
    total_score = 0.0
    top_bearish = None
    top_bullish = None

    for art in articles:
        label, score = analyze_headline_sentiment(art["title"])
        a = {**art, "sentiment": label, "score": score}
        scored.append(a)
        total_score += score

        if label == "BULLISH":
            bull_count += 1
            if top_bullish is None or score > top_bullish["score"]:
                top_bullish = a
        elif label == "BEARISH":
            bear_count += 1
            if top_bearish is None or score < top_bearish["score"]:
                top_bearish = a

    n   = len(articles)
    avg = total_score / n if n > 0 else 0.0

    # Bearish wins ties (risk-first philosophy)
    if bear_count > bull_count:
        overall = "BEARISH"
    elif bull_count > bear_count:
        overall = "BULLISH"
    elif avg <= -0.05:
        overall = "BEARISH"
    elif avg >= 0.05:
        overall = "BULLISH"
    else:
        overall = "NEUTRAL"

    return {
        "overall":         overall,
        "compound":        round(avg, 4),
        "bull_count":      bull_count,
        "bear_count":      bear_count,
        "scored_articles": scored,
        "top_bearish":     top_bearish,
        "top_bullish":     top_bullish,
    }


# =============================================================================
#  SECTION 3 — EARNINGS DATE DETECTION (3-layer fallback)
# =============================================================================

_EARNINGS_CACHE = {}      # (symbol, str_date) -> (bool, source)
_NEWS_SIGNAL_CACHE = {}   # (symbol, max_age) -> (timestamp, result_dict)

def _check_nse_event_calendar(symbol: str, check_date: datetime.date) -> bool:
    """Layer 1: NSE Event Calendar API."""
    from_dt = (check_date - datetime.timedelta(days=1)).strftime("%d-%m-%Y")
    to_dt   = (check_date + datetime.timedelta(days=1)).strftime("%d-%m-%Y")
    api_url = (
        f"https://www.nseindia.com/api/event-calendar"
        f"?index=equities&from_date={from_dt}&to_date={to_dt}"
    )
    headers = {
        **BROWSER_HEADERS,
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-event-calendar",
        "Accept":  "application/json, text/plain, */*",
    }

    try:
        session = requests.Session()
        session.get("https://www.nseindia.com/", headers=headers, timeout=3)
        time.sleep(0.1)
        resp = session.get(api_url, headers=headers, timeout=3)

        if resp.status_code != 200:
            return False

        events       = resp.json()
        symbol_upper = symbol.upper()
        check_str    = check_date.strftime("%d-%b-%Y")

        for event in events:
            ev_symbol  = event.get("symbol", "").upper()
            ev_purpose = event.get("purpose", "").lower()
            ev_date    = event.get("date", "")

            if ev_symbol != symbol_upper:
                continue

            is_results = any(kw in ev_purpose for kw in [
                "financial result", "quarterly result", "annual result",
                "board meeting", "q1", "q2", "q3", "q4",
            ])

            if check_str.lower() in ev_date.lower() and is_results:
                print(f"  [NewsGuard] 📅 NSE API: {symbol} has '{event.get('purpose')}' today")
                return True

    except Exception as e:
        print(f"  [NewsGuard] ⚠️ NSE Event Calendar failed: {e}")

    return False


def _check_yfinance_earnings(symbol: str, check_date: datetime.date) -> bool:
    """Layer 2: yfinance earnings dates."""
    if not _YFINANCE_AVAILABLE:
        return False

    try:
        stock = yf.Ticker(f"{symbol}.NS")

        cal = stock.calendar
        if cal and "Earnings Date" in cal:
            earn_dates = cal["Earnings Date"]
            if not isinstance(earn_dates, list):
                earn_dates = [earn_dates]
            for ed in earn_dates:
                if hasattr(ed, "date"):
                    ed = ed.date()
                elif isinstance(ed, datetime.datetime):
                    ed = ed.date()
                if isinstance(ed, datetime.date) and abs((ed - check_date).days) <= 1:
                    print(f"  [NewsGuard] 📅 yfinance calendar: {symbol} earnings on {ed}")
                    return True

        earn_df = stock.get_earnings_dates(limit=8)
        if earn_df is not None and not earn_df.empty:
            for idx in earn_df.index:
                try:
                    idx_date = idx.date() if hasattr(idx, "date") else idx
                    if abs((idx_date - check_date).days) <= 1:
                        print(f"  [NewsGuard] 📅 yfinance earn_dates: {symbol} on {idx_date}")
                        return True
                except Exception:
                    continue

    except Exception as e:
        print(f"  [NewsGuard] ⚠️ yfinance earnings failed for {symbol}: {e}")

    return False


def _check_nse_results_rss(symbol: str) -> bool:
    """Layer 3: NSE Official RSS — confirms if results already dropped today."""
    articles = fetch_nse_official_rss(symbol, max_age_minutes=480)
    for art in articles:
        title_lower = art["title"].lower()
        if any(kw in title_lower for kw in [
            "financial result", "quarterly result", "results", "q1", "q2", "q3", "q4"
        ]):
            print(f"  [NewsGuard] 📅 NSE Results RSS: {symbol} results found ({art['age_minutes']:.0f}m ago)")
            return True
    return False


def is_earnings_day(symbol: str, check_date: datetime.date = None):
    """
    Is today earnings/results day for this stock?
    3-layer fallback: NSE API → yfinance → NSE Results RSS.
    Results are cached in memory for the day.

    Returns: (is_earnings: bool, source: str)
    """
    if check_date is None:
        ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        check_date = datetime.datetime.now(ist).date()

    cache_key = (symbol.upper(), str(check_date))
    if cache_key in _EARNINGS_CACHE:
        return _EARNINGS_CACHE[cache_key]

    res = (False, "none")
    try:
        if _check_nse_event_calendar(symbol, check_date):
            res = (True, "NSE Event Calendar")
        elif _check_yfinance_earnings(symbol, check_date):
            res = (True, "yfinance")
        elif _check_nse_results_rss(symbol):
            res = (True, "NSE Results RSS")
    except Exception:
        pass

    _EARNINGS_CACHE[cache_key] = res
    return res


# =============================================================================
#  SECTION 4 — MASTER SIGNAL ENGINE
# =============================================================================

def get_news_signal(
    symbol: str,
    max_news_age_minutes: int = 60,
    sentiment_threshold: float = 0.08,
    min_articles_for_signal: int = 2,
) -> dict:
    """
    Master function: fetches news, scores sentiment, checks earnings,
    and returns a comprehensive trading signal dict. Cached for 60s.

    Returns:
        {signal, reason, sentiment, compound_score, news_count,
         is_earnings_day, earnings_source, headlines,
         top_bearish, top_bullish, timestamp}
    """
    now_ts = time.time()
    cache_key = (symbol.upper(), max_news_age_minutes)
    cached = _NEWS_SIGNAL_CACHE.get(cache_key)
    if cached and (now_ts - cached[0] < 60.0):
        return cached[1]

    ist     = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = datetime.datetime.now(ist)

    result = {
        "symbol":          symbol,
        "signal":          SIGNAL_CLEAR,
        "reason":          "",
        "sentiment":       "NEUTRAL",
        "compound_score":  0.0,
        "news_count":      0,
        "is_earnings_day": False,
        "earnings_source": "none",
        "headlines":       [],
        "top_bearish":     None,
        "top_bullish":     None,
        "timestamp":       now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
    }

    # 1. Earnings Day Check
    is_earn, earn_src = is_earnings_day(symbol, now_ist.date())
    result["is_earnings_day"] = is_earn
    result["earnings_source"] = earn_src

    # 2. Fetch Headlines
    google_articles = fetch_google_news_rss(symbol, max_age_minutes=max_news_age_minutes)
    nse_articles    = fetch_nse_official_rss(symbol, max_age_minutes=max_news_age_minutes)
    all_articles    = nse_articles + google_articles  # NSE official = higher priority

    result["news_count"] = len(all_articles)
    result["headlines"]  = [a["title"] for a in all_articles[:5]]

    # 3. Score Sentiment
    scored = None
    if all_articles:
        scored = score_articles(all_articles)
        result["sentiment"]      = scored["overall"]
        result["compound_score"] = scored["compound"]
        result["top_bearish"]    = scored["top_bearish"]
        result["top_bullish"]    = scored["top_bullish"]

    compound  = result["compound_score"]
    sentiment = result["sentiment"]
    n         = len(all_articles)

    # 4. Determine Signal

    # 4a: Earnings Day — overrides everything
    if is_earn:
        if sentiment == "BULLISH" and compound >= sentiment_threshold:
            result["signal"] = SIGNAL_EARNINGS_CE
            result["reason"] = (
                f"📅 Earnings day for {symbol} ({earn_src}). "
                f"Headlines BULLISH (score={compound:.3f}) → Strong results likely → CE bias."
            )
        elif sentiment == "BEARISH" and compound <= -sentiment_threshold:
            result["signal"] = SIGNAL_EARNINGS_PE
            result["reason"] = (
                f"📅 Earnings day for {symbol} ({earn_src}). "
                f"Headlines BEARISH (score={compound:.3f}) → Weak results feared → PE bias."
            )
        else:
            result["signal"] = SIGNAL_EARNINGS_CE
            result["reason"] = (
                f"📅 Earnings day for {symbol} ({earn_src}). "
                f"Neutral sentiment — CE bias (IV expansion expected on results day)."
            )

    # 4b: Strong Bearish News → Block CE
    elif sentiment == "BEARISH" and compound <= -sentiment_threshold and n >= min_articles_for_signal:
        top  = result["top_bearish"]
        bear_n = scored["bear_count"] if scored else 0
        snippet = f'"{top["title"][:70]}..." ({top["age_minutes"]}m ago)' if top else ""
        result["signal"] = SIGNAL_AVOID_CE
        result["reason"]  = (
            f"⚠️ Bearish news cluster: {bear_n}/{n} articles bearish "
            f"(score={compound:.3f}). {snippet}"
        )

    # 4c: Strong Bullish News → Block PE
    elif sentiment == "BULLISH" and compound >= sentiment_threshold and n >= min_articles_for_signal:
        top    = result["top_bullish"]
        bull_n = scored["bull_count"] if scored else 0
        snippet = f'"{top["title"][:70]}..." ({top["age_minutes"]}m ago)' if top else ""
        result["signal"] = SIGNAL_AVOID_PE
        result["reason"]  = (
            f"🚀 Bullish news cluster: {bull_n}/{n} articles bullish "
            f"(score={compound:.3f}). {snippet}"
        )

    # 4d: Clear
    else:
        result["signal"] = SIGNAL_CLEAR
        result["reason"]  = (
            f"✅ No significant news risk. "
            f"{n} articles checked. Sentiment: {sentiment} (score={compound:.3f})"
        )

    _NEWS_SIGNAL_CACHE[cache_key] = (now_ts, result)
    return result


# =============================================================================
#  SECTION 5 — CIRCUIT BREAKER (Pre-Trade & Intraday)
# =============================================================================

def should_allow_options_trade(symbol: str, trade_type: str):
    """
    Pre-trade circuit breaker: should we allow this options trade?

    Args:
        symbol: NSE ticker e.g. 'HDFCBANK'
        trade_type: 'BUY_CE' or 'BUY_PE'

    Returns:
        (allowed: bool, reason: str, full_signal: dict)
    """
    result = get_news_signal(symbol)
    signal = result["signal"]

    if trade_type == "BUY_CE" and signal == SIGNAL_AVOID_CE:
        return False, f"🚫 CE BLOCKED — bearish news: {result['reason']}", result
    if trade_type == "BUY_CE" and signal == SIGNAL_EARNINGS_PE:
        return False, f"🚫 CE BLOCKED — earnings PE bias: {result['reason']}", result
    if trade_type == "BUY_PE" and signal == SIGNAL_AVOID_PE:
        return False, f"🚫 PE BLOCKED — bullish news: {result['reason']}", result
    if trade_type == "BUY_PE" and signal == SIGNAL_EARNINGS_CE:
        return False, f"🚫 PE BLOCKED — earnings CE bias: {result['reason']}", result

    return True, f"✅ {trade_type} allowed. {result['reason']}", result


def check_active_trade_news(symbol: str, trade_type: str) -> dict:
    """
    Intraday Layer 2 — breaking news monitor for ACTIVE positions.
    Call every 60 seconds (every 3rd 20s poll cycle) to avoid rate limiting.

    Args:
        symbol: NSE ticker e.g. 'HDFCBANK'
        trade_type: 'BUY_CE' or 'BUY_PE'

    Returns:
        {emergency_exit: bool, exit_reason: str, exit_note: str, signal: str, details: dict}
    """
    result = get_news_signal(symbol, max_news_age_minutes=30)
    signal = result["signal"]

    if trade_type == "BUY_CE" and signal == SIGNAL_AVOID_CE:
        top      = result.get("top_bearish")
        headline = top["title"][:80] if top else "Breaking bearish news detected"
        return {
            "emergency_exit": True,
            "exit_reason":    "NEWS_GUARD_EXIT",
            "exit_note":      f"⚡ Breaking bearish news: {headline}",
            "signal":         signal,
            "details":        result,
        }

    if trade_type == "BUY_PE" and signal == SIGNAL_AVOID_PE:
        top      = result.get("top_bullish")
        headline = top["title"][:80] if top else "Breaking bullish news detected"
        return {
            "emergency_exit": True,
            "exit_reason":    "NEWS_GUARD_EXIT",
            "exit_note":      f"⚡ Bullish news (bad for PE): {headline}",
            "signal":         signal,
            "details":        result,
        }

    return {
        "emergency_exit": False,
        "exit_reason":    "",
        "exit_note":      result["reason"],
        "signal":         signal,
        "details":        result,
    }


# =============================================================================
#  CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys

    test_symbols = sys.argv[1:] if len(sys.argv) > 1 else ["HDFCBANK", "RELIANCE", "JSWSTEEL"]

    print("=" * 70)
    print("  📰 NewsGuard — NSE Options News & Earnings Sentinel")
    print(f"  VADER:    {'✅ Available' if _VADER_AVAILABLE else '⚠️  Not installed (using keywords)'}")
    print(f"  yfinance: {'✅ Available' if _YFINANCE_AVAILABLE else '⚠️  Not installed'}")
    print("=" * 70)

    for sym in test_symbols:
        print(f"\n📊 Analyzing: {sym}")
        print("-" * 50)

        result = get_news_signal(sym, max_news_age_minutes=120)
        emoji  = SIGNAL_EMOJI.get(result["signal"], "⚪")

        print(f"  Signal:       {emoji} {result['signal']}")
        print(f"  Reason:       {result['reason'][:100]}")
        print(f"  Sentiment:    {result['sentiment']} (score={result['compound_score']:.4f})")
        print(f"  Articles:     {result['news_count']} in window")
        print(f"  Earnings Day: {'✅ YES' if result['is_earnings_day'] else 'No'} ({result['earnings_source']})")

        if result["headlines"]:
            print("  Top Headlines:")
            for i, h in enumerate(result["headlines"][:3], 1):
                label, score = analyze_headline_sentiment(h)
                e = "📉" if label == "BEARISH" else "📈" if label == "BULLISH" else "➖"
                print(f"    {i}. {e} [{label:7s}] {h[:72]}")

        print()
        for trade in ["BUY_CE", "BUY_PE"]:
            allowed, reason, _ = should_allow_options_trade(sym, trade)
            status = "✅ ALLOWED" if allowed else "🚫 BLOCKED"
            print(f"  {trade}: {status}")
        print()
