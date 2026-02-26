"""
Dividend Radar Engine - Alerts

Handles alerting via Telegram, Email, etc.
"""
import asyncio
from typing import Optional

from monitoring import MonitoringService
from .models import DividendCandidate


async def _send_via_monitoring(message: str) -> None:
    """Internal helper to send a Telegram alert via MonitoringService."""
    service = MonitoringService()
    await service.send_alert(message, severity="INFO")


def format_dividend_alert(candidate: DividendCandidate) -> str:
    """Format a human‑readable alert message for a dividend candidate."""
    suggested_zone = ""
    if candidate.entry_zone_low is not None and candidate.entry_zone_high is not None:
        suggested_zone = (
            f"\nSuggested Entry Zone: ₹{candidate.entry_zone_low:.2f} – "
            f"₹{candidate.entry_zone_high:.2f}"
        )

    trend_text = candidate.trend or candidate.category or "N/A"

    message = (
        "🔔 Dividend Radar Alert\n\n"
        f"Stock: {candidate.symbol} ({candidate.company_name})\n"
        f"Ex-Date: {candidate.ex_date}\n"
        f"Yield: {candidate.yield_percent:.2f}%\n"
        f"Dividend Score: {candidate.dividend_score or 0}\n"
        f"Trend: {trend_text}"
        f"{suggested_zone}"
    )
    return message


def send_dividend_alert(candidate: DividendCandidate) -> None:
    """
    Public, synchronous entrypoint for sending an alert.

    This can be safely called from schedulers (e.g. APScheduler / cron),
    and it will manage the asyncio event loop internally.
    """
    message = format_dividend_alert(candidate)

    try:
        asyncio.run(_send_via_monitoring(message))
    except RuntimeError:
        # If there is already a running loop (e.g. inside FastAPI),
        # fall back to creating a background task on that loop.
        loop = asyncio.get_event_loop()
        loop.create_task(_send_via_monitoring(message))
