"""
Dividend Radar Engine (DRE) - Module Entry Point

This module integrates with the main backend and provides:
- Daily dividend announcement detection
- Dividend scoring
- Technical/financial integration
- Alerting and UI data
"""

from .scheduler import schedule_dividend_radar
from .scoring import DividendScorer, classify_dividend_score
from .fetchers import fetch_nse_dividends, fetch_bse_dividends, fetch_price_data, fetch_financial_data
from .alerts import send_dividend_alert
from .models import DividendCandidate

__all__ = [
    "schedule_dividend_radar",
    "DividendScorer",
    "classify_dividend_score",
    "fetch_nse_dividends",
    "fetch_bse_dividends",
    "fetch_price_data",
    "fetch_financial_data",
    "send_dividend_alert",
    "DividendCandidate",
]
