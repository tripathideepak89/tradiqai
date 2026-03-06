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


@router.post("/api/audit/rejected-trades/test-seed")
async def seed_test_rejection(
    current_user: dict = Depends(_current_user),
    db=Depends(_get_db()),
):
    """Insert one synthetic rejection record tagged with the current user's id.
    Use this to verify the table exists and the API is wired correctly.
    Only available when REJECTED_TRADES_AUDIT_ENABLED=true.
    """
    if not getattr(settings, "rejected_trades_audit_enabled", True):
        raise HTTPException(status_code=403, detail="Audit disabled")

    from rejected_trades import RejectedTradesService, RejectionReason, RiskSnapshot
    svc = RejectedTradesService(db)
    svc.log_rejection(
        user_id=current_user["id"],
        symbol="TEST",
        strategy_name="TestStrategy",
        side="BUY",
        order_type="CNC",
        entry_price=1000.0,
        stop_loss=980.0,
        target=1060.0,
        quantity=5,
        reasons=[
            RejectionReason(
                code="CME_HALTED",
                message="[TEST] Portfolio drawdown ≥ 12% — trading halted.",
                rule_name="capital_manager.approve_trade.CME_HALTED",
                rule_value="drawdown=12.5%,threshold=12%",
            )
        ],
        snapshot=RiskSnapshot(
            portfolio_equity=95000.0,
            cash_available=12000.0,
            exposure_pct=62.0,
            drawdown_pct=12.5,
            regime="BEAR",
        ),
    )
    return {"ok": True, "user_id": current_user["id"],
            "message": "Test rejection logged — refresh the audit page."}
