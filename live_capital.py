"""Single source of truth for live available broker capital.

Written by:
  - main.py      → after risk_engine.update_available_capital() succeeds
  - dashboard.py → after broker.get_margins() succeeds on each WS tick

Read by:
  - api_portfolio.py → all 5 portfolio analytics services
  - dashboard.py     → CME snapshot total_capital
  - capital_manager  → via main.py setter on each capital refresh

Fallback: config.settings.cme_total_capital (default ₹1,00,000)
"""
import logging

logger = logging.getLogger(__name__)

_live: float = 0.0   # 0 = not yet fetched from broker


def get_live_capital(fallback: float = 100_000.0) -> float:
    """Return live broker available capital, or fallback if not yet fetched."""
    return _live if _live > 0 else fallback


def set_live_capital(value: float) -> None:
    """Set live broker available capital. Ignores zero / negative values."""
    global _live
    if value and value > 0:
        prev = _live
        _live = float(value)
        if abs(_live - prev) > 1.0:  # only log meaningful changes
            logger.info(f"[LiveCapital] Updated: ₹{prev:,.0f} → ₹{_live:,.0f}")
