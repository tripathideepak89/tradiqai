"""
Dividend Radar Engine - Data Models

Defines data structures for dividend candidates and results.
"""
from typing import Optional
from pydantic import BaseModel

class DividendCandidate(BaseModel):
    symbol: str
    company_name: str
    ex_date: str
    yield_percent: float
    roe: Optional[float]
    payout_ratio: Optional[float]
    debt_to_equity: Optional[float] = None
    years_dividend_history: Optional[int] = None
    dividend_growth_3yr: Optional[float] = None
    price: Optional[float]
    dma_20: Optional[float]
    dma_50: Optional[float]
    dma_200: Optional[float]
    dividend_score: Optional[int]
    trend: Optional[str]
    category: Optional[str] = None  # Classification bucket (Strong Buy / Watchlist / etc.)
    alert: Optional[str] = None     # e.g. ENTRY, WATCH, IGNORE
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
