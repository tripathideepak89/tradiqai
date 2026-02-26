"""
Dividend Radar Engine - Scheduler

Schedules daily tasks for fetching, scoring, and updating dividend radar data.
"""
import datetime
from typing import List

from .fetchers import (
    fetch_nse_dividends,
    fetch_bse_dividends,
    fetch_price_data,
    fetch_financial_data,
)
from .scoring import DividendScorer, classify_dividend_score
from .models import DividendCandidate
from .alerts import send_dividend_alert


def _parse_ex_date(ex_date_str: str) -> datetime.date:
    """Parse ex-date string into date, supporting a few common formats."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y"):
        try:
            return datetime.datetime.strptime(ex_date_str, fmt).date()
        except (ValueError, TypeError):
            continue
    # Fallback: today (so that bad data does not silently pass far out)
    return datetime.date.today()


def _is_within_days(ex_date_str: str, min_days: int, max_days: int) -> bool:
    ex_date = _parse_ex_date(ex_date_str)
    today = datetime.date.today()
    delta = (ex_date - today).days
    return min_days <= delta <= max_days


def _build_candidate(raw: dict) -> DividendCandidate:
    """
    Normalise raw dividend announcement + fetched data into DividendCandidate.

    Expected base keys from raw announcement:
    - symbol
    - company_name
    - ex_date
    - yield_percent
    """
    symbol = raw.get("symbol")
    company_name = raw.get("company_name", symbol or "")
    ex_date = raw.get("ex_date", "")
    yield_percent = float(raw.get("yield_percent", 0.0) or 0.0)

    # Enrich with price / technicals and financials
    price_data = fetch_price_data(symbol)
    financial_data = fetch_financial_data(symbol)

    candidate_dict = {
        "symbol": symbol,
        "company_name": company_name,
        "ex_date": ex_date,
        "yield_percent": yield_percent,
        "roe": financial_data.get("roe"),
        "payout_ratio": financial_data.get("payout_ratio"),
        "debt_to_equity": financial_data.get("debt_to_equity"),
        "years_dividend_history": financial_data.get("years_dividend_history"),
        "dividend_growth_3yr": financial_data.get("dividend_growth_3yr"),
        "price": price_data.get("price"),
        "dma_20": price_data.get("dma_20"),
        "dma_50": price_data.get("dma_50"),
        "dma_200": price_data.get("dma_200"),
    }

    # Score + classification
    score = DividendScorer.score(candidate_dict)
    category = classify_dividend_score(score)

    candidate_dict["dividend_score"] = score
    candidate_dict["trend"] = category
    candidate_dict["category"] = category

    # Compute a simple suggested entry zone around current price (±2%)
    price = candidate_dict.get("price")
    if price:
        candidate_dict["entry_zone_low"] = round(price * 0.98, 2)
        candidate_dict["entry_zone_high"] = round(price * 1.02, 2)

    return DividendCandidate(**candidate_dict)


def _meets_entry_rules(candidate: DividendCandidate) -> bool:
    """
    Entry Rule (Dividend Capture + Momentum):
    - DividendScore > 70
    - price above 20DMA
    - breakout above last 5 day high (if available)
    - ex-date between 5–14 days
    """
    if not candidate.dividend_score or candidate.dividend_score <= 70:
        return False

    if not (candidate.price and candidate.dma_20 and candidate.price > candidate.dma_20):
        return False

    # Optional: breakout above last 5D high, if fetch_price_data provides it
    # We look for raw last_5d_high on the candidate dict (populated in _build_candidate via price_data)
    last_5d_high = getattr(candidate, "last_5d_high", None)  # type: ignore[attr-defined]
    if last_5d_high is not None and candidate.price <= last_5d_high:
        return False

    if not _is_within_days(candidate.ex_date, 5, 14):
        return False

    return True


def run_dividend_radar_workflow() -> List[DividendCandidate]:
    """
    End‑to‑end DRE workflow:
    - Fetch announcements from NSE & BSE
    - Filter ex‑dates within next 14 days
    - Enrich + score
    - Trigger alerts for high‑quality entry candidates

    Returns the list of scored candidates (useful for debugging / tests).
    """
    # Step 1: Fetch raw announcements
    nse_divs = fetch_nse_dividends()
    bse_divs = fetch_bse_dividends()
    all_raw = (nse_divs or []) + (bse_divs or [])

    # Step 2: Filter for ex‑dates within next 14 days
    upcoming = [
        raw for raw in all_raw
        if raw.get("ex_date") and _is_within_days(raw.get("ex_date"), 0, 14)
    ]

    # Step 3: Build candidates + score
    candidates: List[DividendCandidate] = []
    for raw in upcoming:
        try:
            candidate = _build_candidate(raw)
        except Exception:
            # Skip malformed entries but continue with others
            continue
        candidates.append(candidate)

    # Step 4: Alert on strong entry opportunities
    for candidate in candidates:
        if _meets_entry_rules(candidate):
            candidate.alert = "ENTRY"
            send_dividend_alert(candidate)
        elif (candidate.dividend_score or 0) >= 60:
            candidate.alert = "WATCH"

    # TODO: Step 5: Persist candidates to DB/Supabase for historical analysis

    return candidates


def schedule_dividend_radar() -> None:
    """
    Run the dividend radar workflow (to be scheduled at 6:30 AM daily).

    This function is intentionally synchronous so it can be used directly
    from cron / APScheduler / `python -m dividend_radar`.
    """
    run_dividend_radar_workflow()
