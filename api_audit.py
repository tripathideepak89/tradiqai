"""Audit API — Rejected Trades endpoints.

Routes (all require a valid Supabase JWT):
  GET  /api/audit/rejected-trades          Today's rejections (or ?date=YYYY-MM-DD)
  GET  /api/audit/rejected-trades/{id}     Single record detail
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from rejected_trades import RejectedTradesService

logger = logging.getLogger(__name__)
router = APIRouter()

# Bearer-token extractor — only FastAPI imported at module load time;
# Supabase auth is imported lazily at request time so tests can import
# this module without the supabase package being installed.
_security = HTTPBearer()


async def _current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """Lazy auth dependency — imports Supabase auth at request time only."""
    from tradiqai_supabase_auth import auth_manager
    return await auth_manager.get_current_user(credentials)


def _get_db():
    from database import get_db
    return get_db


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/api/audit/rejected-trades")
async def list_rejected_trades(
    date: Optional[str] = Query(
        None,
        description="Date filter in YYYY-MM-DD format (default: today UTC)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    strategy: Optional[str] = Query(None, description="Filter by strategy_name"),
    reason_code: Optional[str] = Query(None, description="Filter by rejection reason code"),
    symbol: Optional[str] = Query(None, description="Filter by symbol (case-insensitive prefix)"),
    current_user: dict = Depends(_current_user),
    db=Depends(_get_db()),
):
    """Return today's (or a specific date's) rejected trade signals.

    If the feature flag REJECTED_TRADES_AUDIT_ENABLED is false, returns
    an empty list with a flag indicating audit is disabled.
    """
    if not getattr(settings, "rejected_trades_audit_enabled", True):
        return {"audit_enabled": False, "items": [], "total": 0}

    target_date = None
    if date:
        try:
            from datetime import date as _date
            target_date = _date.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format — use YYYY-MM-DD")

    svc = RejectedTradesService(db)
    items = svc.get_today(user_id=current_user["id"], target_date=target_date)

    # Apply optional filters
    if strategy:
        items = [i for i in items if i["strategy_name"] == strategy]
    if reason_code:
        items = [
            i for i in items
            if any(r.get("code") == reason_code for r in i["reasons"])
        ]
    if symbol:
        sym_upper = symbol.upper()
        items = [i for i in items if i["symbol"].upper().startswith(sym_upper)]

    from datetime import date as _date
    return {
        "audit_enabled": True,
        "items": items,
        "total": len(items),
        "date": (target_date or _date.today()).isoformat(),
    }


@router.get("/api/audit/rejected-trades/{record_id}")
async def get_rejected_trade(
    record_id: int,
    current_user: dict = Depends(_current_user),
    db=Depends(_get_db()),
):
    """Return a single rejected-trade record by id (user-scoped)."""
    if not getattr(settings, "rejected_trades_audit_enabled", True):
        raise HTTPException(status_code=403, detail="Rejected trades audit is disabled")

    svc = RejectedTradesService(db)
    record = svc.get_by_id(user_id=current_user["id"], record_id=record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
