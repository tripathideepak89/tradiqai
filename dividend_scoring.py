"""
dividend_scoring.py
===================
TradiqAI — Dividend Radar Engine
Scoring engine: takes normalised dividend records + live price data
and produces DRE scores, classifications, entry signals, and trap flags.

Drop this file in your TradiqAI root directory.

Usage:
    from dividend_scoring import DividendScoringEngine
    engine = DividendScoringEngine(db_conn)
    scored = engine.score_all(dividend_records)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  SCORE CONFIGURATION
#  Easy to tweak without changing logic
# ─────────────────────────────────────────────

SCORE_CONFIG = {
    # 1. Yield scoring  (0–25)
    "yield_high":   5.0,    # → 25 points
    "yield_mid":    3.0,    # → 20 points
    "yield_low":    2.0,    # → 10 points
    "yield_pts":    {5.0: 25, 3.0: 20, 2.0: 10, 0: 0},

    # 2. Consistency scoring  (0–20)
    "consistency_full":  4,     # 4 years paid → 20
    "consistency_3yr":   3,     # 3 years      → 15
    "consistency_pts":   {4: 20, 3: 15, 2: 10, 1: 5, 0: 0},

    # 3. Growth scoring  (0–15)
    "growth_threshold":  10.0,  # 3-yr CAGR > 10% → 15 else 5
    "growth_high_pts":   15,
    "growth_low_pts":    5,

    # 4. Financial strength  (0–20)
    "roe_threshold":     18.0,  # ROE > 18% → 10 pts
    "de_threshold":      1.0,   # D/E  < 1  → 10 pts

    # 5. Technical strength  (0–20)
    # price > 50DMA → 10,  price > 200DMA → 10

    # Entry signal thresholds
    "entry_min_score":   70,
    "entry_min_ex_days": 5,
    "entry_max_ex_days": 14,

    # Trap: high yield but downtrend
    "trap_yield_min":    8.0,
}


# ─────────────────────────────────────────────
#  PRICE DATA FETCHER
#  Uses yfinance — already common in trading stacks.
#  Fallback: returns None gracefully.
# ─────────────────────────────────────────────

def _fetch_price_data(symbol: str) -> Optional[dict]:
    """
    Fetch latest EOD price + moving averages for a symbol.
    Returns dict with keys: price, sma20, sma50, sma200, above_20dma, above_50dma, above_200dma
    or None on failure.

    NSE suffix: symbol + ".NS"   e.g. "ITC.NS"
    BSE suffix: symbol + ".BO"   e.g. "500875.BO"
    """
    try:
        import yfinance as yf
        ticker = f"{symbol}.NS"
        df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 50:
            logger.warning(f"Price data insufficient for {symbol}")
            return None

        close  = df["Close"]
        price  = float(close.iloc[-1])
        sma20  = float(close.tail(20).mean())
        sma50  = float(close.tail(50).mean())
        sma200 = float(close.tail(200).mean()) if len(close) >= 200 else None

        return {
            "price":       price,
            "sma20":       sma20,
            "sma50":       sma50,
            "sma200":      sma200,
            "above_20dma": price > sma20,
            "above_50dma": price > sma50,
            "above_200dma": (price > sma200) if sma200 else False,
            "5d_high":     float(close.tail(5).max()),
        }

    except ImportError:
        logger.warning("yfinance not installed — technical scores will be 0")
        return None
    except Exception as exc:
        logger.warning(f"Price fetch failed for {symbol}: {exc}")
        return None


def _fetch_fundamentals(symbol: str) -> Optional[dict]:
    """
    Fetch ROE, D/E, dividend history from yfinance.
    Returns dict or None.
    """
    try:
        import yfinance as yf
        t    = yf.Ticker(f"{symbol}.NS")
        info = t.info or {}

        roe  = info.get("returnOnEquity")
        de   = info.get("debtToEquity")

        # yfinance returns ROE as decimal (0.22 = 22%)
        roe_pct = float(roe) * 100 if roe else None
        # D/E is sometimes in percent form (100 = 1.0 ratio)
        de_ratio = float(de) / 100 if (de and de > 10) else (float(de) if de else None)

        # Dividend history for consistency/growth
        hist = t.dividends
        if not hist.empty:
            hist = hist.sort_index()
            # Group by year
            yearly = hist.groupby(hist.index.year).sum()
            years  = sorted(yearly.index.tolist(), reverse=True)
            recent = [float(yearly[y]) for y in years[:5]]
        else:
            recent = []

        return {
            "roe":         roe_pct,
            "de":          de_ratio,
            "div_history": recent,   # last 5 years, most recent first
        }

    except Exception as exc:
        logger.warning(f"Fundamentals fetch failed for {symbol}: {exc}")
        return None


# ─────────────────────────────────────────────
#  SCORING FUNCTIONS
# ─────────────────────────────────────────────

def _score_yield(yield_pct: float, cfg: dict) -> int:
    if yield_pct >= cfg["yield_high"]:  return 25
    if yield_pct >= cfg["yield_mid"]:   return 20
    if yield_pct >= cfg["yield_low"]:   return 10
    return 0


def _score_consistency(div_history: list) -> int:
    """
    div_history: list of annual dividend amounts, most recent first.
    Count consecutive non-zero years.
    """
    years_paid = sum(1 for d in div_history if d and d > 0)
    if years_paid >= 4:  return 20
    if years_paid == 3:  return 15
    if years_paid == 2:  return 10
    if years_paid == 1:  return 5
    return 0


def _score_growth(div_history: list) -> int:
    """
    Compute 3-yr dividend CAGR.
    Needs at least 4 years (year 0 = most recent, year 3 = base).
    """
    if len(div_history) < 4:
        return 5  # insufficient data
    recent = div_history[0]
    base   = div_history[3]
    if not base or base == 0:
        return 5
    try:
        cagr_3yr = ((recent / base) ** (1 / 3) - 1) * 100
        return 15 if cagr_3yr >= 10.0 else 5
    except Exception:
        return 5


def _score_financials(roe: Optional[float], de: Optional[float]) -> int:
    pts = 0
    if roe is not None and roe > 18.0:  pts += 10
    if de  is not None and de  <  1.0:  pts += 10
    return pts


def _score_technicals(price_data: Optional[dict]) -> int:
    if not price_data:
        return 0
    pts = 0
    if price_data.get("above_50dma"):   pts += 10
    if price_data.get("above_200dma"):  pts += 10
    return pts


def _compute_yield(dividend_amount: float, price: float) -> float:
    if not price or price == 0:
        return 0.0
    return round((dividend_amount / price) * 100, 2)


def _is_dividend_trap(yield_pct: float, price_data: Optional[dict]) -> bool:
    """Trap: yield > 8% AND price below both 50DMA and 200DMA (downtrend)."""
    if yield_pct < 8.0:
        return False
    if not price_data:
        return False
    return (not price_data.get("above_50dma")) and (not price_data.get("above_200dma"))


def _classify(score: int) -> str:
    if score >= 80:  return "Strong Buy"
    if score >= 60:  return "Watchlist"
    if score >= 40:  return "Moderate"
    return "Ignore"


def _entry_signal(
    score: int,
    price_data: Optional[dict],
    ex_date: str,
    is_trap: bool,
    cfg: dict,
) -> bool:
    """
    Entry signal rules (from your DRE spec):
      DividendScore > 70
      AND price above 20DMA
      AND breakout above last 5-day high
      AND ex-date between 5–14 days away
      AND not a dividend trap
    """
    if is_trap or score < cfg["entry_min_score"]:
        return False
    if not price_data:
        return False
    if not price_data.get("above_20dma"):
        return False

    # Price breakout above 5-day high
    price   = price_data.get("price", 0)
    high_5d = price_data.get("5d_high", 0)
    if high_5d and price < high_5d * 0.99:  # within 1% = acceptable
        return False

    # Days to ex-date
    try:
        ex = datetime.strptime(ex_date, "%Y-%m-%d")
        days = (ex - datetime.now()).days
        if not (cfg["entry_min_ex_days"] <= days <= cfg["entry_max_ex_days"]):
            return False
    except Exception:
        return False

    return True


def _entry_zone(price: float) -> tuple[float, float]:
    """Suggest entry zone: current price ± 1%."""
    if not price:
        return (0, 0)
    return (round(price * 0.99, 1), round(price * 1.01, 1))


# ─────────────────────────────────────────────
#  MAIN SCORING ENGINE
# ─────────────────────────────────────────────

class DividendScoringEngine:
    """
    Takes normalised dividend records (from DividendIngestionService),
    fetches price + fundamental data, and returns fully scored records.

    Usage:
        engine = DividendScoringEngine(db_conn)
        scored = engine.score_all(dividend_records)
    """

    def __init__(self, db_conn=None, cfg: dict = None):
        self.db_conn = db_conn
        self.cfg     = cfg or SCORE_CONFIG
        self._price_cache = {}
        self._fund_cache  = {}

    def score_all(self, records: list[dict]) -> list[dict]:
        """
        Score each dividend record and return enriched list.
        Records without a valid symbol are skipped.
        """
        scored = []
        for rec in records:
            symbol = rec.get("symbol") or rec.get("name", "").split()[0].upper()
            if not symbol:
                continue
            try:
                result = self._score_one(rec, symbol)
                scored.append(result)
            except Exception as exc:
                logger.warning(f"Scoring failed for {symbol}: {exc}")

        # Sort by score descending
        scored.sort(key=lambda x: x["dre_score"], reverse=True)
        logger.info(f"Scoring: {len(scored)} records scored. "
                    f"Strong Buy: {sum(1 for r in scored if r['category'] == 'Strong Buy')}, "
                    f"Entry Signals: {sum(1 for r in scored if r['entry_signal'])}, "
                    f"Traps: {sum(1 for r in scored if r['is_trap'])}")
        return scored

    def _score_one(self, rec: dict, symbol: str) -> dict:
        # Fetch price data (cached)
        if symbol not in self._price_cache:
            self._price_cache[symbol] = _fetch_price_data(symbol)
        price_data = self._price_cache[symbol]

        # Fetch fundamentals (cached)
        if symbol not in self._fund_cache:
            self._fund_cache[symbol] = _fetch_fundamentals(symbol)
        fund = self._fund_cache[symbol] or {}

        # Compute yield
        price         = price_data["price"] if price_data else None
        div_amt       = rec.get("dividend_amount") or 0
        yield_pct     = _compute_yield(div_amt, price) if price else 0.0

        # Individual scores
        div_history    = fund.get("div_history", [])
        s_yield        = _score_yield(yield_pct, self.cfg)
        s_consistency  = _score_consistency(div_history)
        s_growth       = _score_growth(div_history)
        s_financial    = _score_financials(fund.get("roe"), fund.get("de"))
        s_technical    = _score_technicals(price_data)

        dre_score  = s_yield + s_consistency + s_growth + s_financial + s_technical
        is_trap    = _is_dividend_trap(yield_pct, price_data)
        category   = _classify(dre_score)
        ex_date    = rec.get("ex_date", "")
        signal     = _entry_signal(dre_score, price_data, ex_date, is_trap, self.cfg)

        days_to_ex = None
        if ex_date:
            try:
                days_to_ex = (datetime.strptime(ex_date, "%Y-%m-%d") - datetime.now()).days
            except Exception:
                pass

        ez = _entry_zone(price) if price and signal else (None, None)

        trend = "Unknown"
        if price_data:
            above_20  = price_data.get("above_20dma", False)
            above_50  = price_data.get("above_50dma", False)
            above_200 = price_data.get("above_200dma", False)
            if above_20 and above_50 and above_200:
                trend = "Strong"
            elif above_20 and above_50:
                trend = "Moderate"
            elif above_20:
                trend = "Weak Uptrend"
            elif not above_20 and not above_50:
                trend = "Downtrend"
            else:
                trend = "Weak"

        return {
            # Original record fields
            **rec,

            # Enriched price/fundamental data
            "price":            price,
            "yield_pct":        yield_pct,
            "roe":              fund.get("roe"),
            "de":               fund.get("de"),
            "div_history":      div_history,
            "above_20dma":      price_data.get("above_20dma") if price_data else None,
            "above_50dma":      price_data.get("above_50dma") if price_data else None,
            "above_200dma":     price_data.get("above_200dma") if price_data else None,
            "trend":            trend,

            # Score breakdown
            "score_yield":      s_yield,
            "score_consistency":s_consistency,
            "score_growth":     s_growth,
            "score_financial":  s_financial,
            "score_technical":  s_technical,
            "dre_score":        dre_score,

            # Classification & signals
            "category":         category,
            "is_trap":          is_trap,
            "entry_signal":     signal,
            "days_to_ex":       days_to_ex,
            "entry_zone_low":   ez[0],
            "entry_zone_high":  ez[1],

            # Exit strategies
            "exit_s1":          "1 day before ex-date (Dividend Capture)",
            "exit_s2":          "Exit if close below 20DMA (Trend + Dividend)",
        }

    def save_scores_to_db(self, scored: list[dict]):
        """
        Upsert scores back into the DB.
        Saves to dividend_scores table for dashboard queries.
        """
        if not self.db_conn or not scored:
            return

        upsert_sql = """
            INSERT INTO dividend_scores (
                symbol, ex_date, dre_score, yield_pct, category,
                is_trap, entry_signal, days_to_ex, trend,
                score_yield, score_consistency, score_growth,
                score_financial, score_technical,
                entry_zone_low, entry_zone_high,
                price, roe, de, scored_at
            )
            VALUES (
                %(symbol)s, %(ex_date)s, %(dre_score)s, %(yield_pct)s, %(category)s,
                %(is_trap)s, %(entry_signal)s, %(days_to_ex)s, %(trend)s,
                %(score_yield)s, %(score_consistency)s, %(score_growth)s,
                %(score_financial)s, %(score_technical)s,
                %(entry_zone_low)s, %(entry_zone_high)s,
                %(price)s, %(roe)s, %(de)s, NOW()
            )
            ON CONFLICT (symbol, ex_date)
            DO UPDATE SET
                dre_score    = EXCLUDED.dre_score,
                yield_pct    = EXCLUDED.yield_pct,
                category     = EXCLUDED.category,
                is_trap      = EXCLUDED.is_trap,
                entry_signal = EXCLUDED.entry_signal,
                days_to_ex   = EXCLUDED.days_to_ex,
                trend        = EXCLUDED.trend,
                price        = EXCLUDED.price,
                scored_at    = NOW();
        """

        create_scores_table = """
            CREATE TABLE IF NOT EXISTS dividend_scores (
                id               SERIAL PRIMARY KEY,
                symbol           VARCHAR(20),
                ex_date          DATE,
                dre_score        INT,
                yield_pct        NUMERIC(6,2),
                category         VARCHAR(20),
                is_trap          BOOLEAN DEFAULT FALSE,
                entry_signal     BOOLEAN DEFAULT FALSE,
                days_to_ex       INT,
                trend            VARCHAR(20),
                score_yield      INT,
                score_consistency INT,
                score_growth     INT,
                score_financial  INT,
                score_technical  INT,
                entry_zone_low   NUMERIC(10,2),
                entry_zone_high  NUMERIC(10,2),
                price            NUMERIC(10,2),
                roe              NUMERIC(6,2),
                de               NUMERIC(6,2),
                scored_at        TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(symbol, ex_date)
            );
        """

        with self.db_conn.cursor() as cur:
            cur.execute(create_scores_table)
            for s in scored:
                safe = {k: s.get(k) for k in [
                    "symbol","ex_date","dre_score","yield_pct","category",
                    "is_trap","entry_signal","days_to_ex","trend",
                    "score_yield","score_consistency","score_growth",
                    "score_financial","score_technical",
                    "entry_zone_low","entry_zone_high",
                    "price","roe","de"
                ]}
                try:
                    cur.execute(upsert_sql, safe)
                except Exception as exc:
                    logger.warning(f"Score save skipped for {s.get('symbol')}: {exc}")
        self.db_conn.commit()
        logger.info(f"DB: saved {len(scored)} scores to dividend_scores.")


# ─────────────────────────────────────────────
#  STANDALONE TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    # Mock record to test scoring without DB
    mock_records = [
        {
            "symbol": "ITC", "name": "ITC Ltd", "exchange": "NSE",
            "dividend_amount": 6.5, "ex_date": "2026-03-12",
            "dividend_type": "Final", "source": "NSE",
            "purpose": "Dividend - Rs 6.50 Per Share"
        },
        {
            "symbol": "COALINDIA", "name": "Coal India Ltd", "exchange": "NSE",
            "dividend_amount": 14.5, "ex_date": "2026-03-08",
            "dividend_type": "Interim", "source": "BSE",
            "purpose": "Interim Dividend - Rs 14.50 Per Share"
        },
    ]

    engine = DividendScoringEngine()
    scored = engine.score_all(mock_records)

    print(f"\n{'Symbol':15} {'Score':6} {'Yield%':7} {'Category':14} {'Signal':7} {'Trap':6} {'Trend'}")
    print("-" * 75)
    for s in scored:
        print(
            f"{s['symbol']:15} "
            f"{s['dre_score']:6} "
            f"{s.get('yield_pct', 0):7.1f}% "
            f"{s['category']:14} "
            f"{'YES' if s['entry_signal'] else 'no':7} "
            f"{'⚠️' if s['is_trap'] else '-':6} "
            f"{s.get('trend','?')}"
        )
