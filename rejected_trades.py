"""Rejected Trades Audit Service.

Responsibilities
────────────────
• log_rejection()  — called by OrderManager at every rejection point.
    - Checks the REJECTED_TRADES_AUDIT_ENABLED feature flag.
    - De-duplicates within a configurable window (default 10 min).
• get_today()      — returns today's rejected trades for a user, sorted
                     newest-first.
• get_by_id()      — returns a single record by id (user-scoped).
• cleanup_old()    — deletes records older than retention period.
                     Meant to be called once per day by a background job.

Data classes
────────────
RejectionReason   — one rule that caused the rejection.
RiskSnapshot      — lightweight portfolio state at decision time.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from config import settings
from models import RejectedTrade

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

DEDUP_WINDOW_MINUTES: int = 10


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class RejectionReason:
    """Structured description of a single rule that blocked the trade."""
    code: str        # e.g. "CME_HALTED", "COST_FILTER", "RISK_DAILY_LOSS"
    message: str     # human-readable explanation
    rule_name: str   # exact function / rule identifier
    rule_value: str = ""  # e.g. "sector_limit=30%, current_exposure=38%"


@dataclass
class RiskSnapshot:
    """Lightweight portfolio state captured at decision time."""
    portfolio_equity: float = 0.0
    cash_available: float = 0.0
    exposure_pct: float = 0.0
    drawdown_pct: float = 0.0
    sector_exposure_pct: float = 0.0   # sector of the rejected symbol
    strategy_exposure_pct: float = 0.0  # strategy bucket
    regime: str = "UNKNOWN"
    vix_proxy: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("vix_proxy") is None:
            d.pop("vix_proxy", None)
        return d


# ─── Service ──────────────────────────────────────────────────────────────────

class RejectedTradesService:
    """Logs, de-duplicates and retrieves rejected trade records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def log_rejection(
        self,
        *,
        user_id: str,
        symbol: str,
        strategy_name: str,
        side: str,                           # "BUY" | "SELL"
        order_type: str = "CNC",             # "CNC" | "MIS"
        reasons: List[RejectionReason],
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        quantity: int = 0,
        exchange: str = "NSE",
        snapshot: Optional[RiskSnapshot] = None,
    ) -> None:
        """Log a rejection event.  Silent on any failure — must never
        affect trading behaviour."""
        if not getattr(settings, "rejected_trades_audit_enabled", True):
            return
        try:
            self._upsert(
                user_id=user_id,
                symbol=symbol,
                strategy_name=strategy_name,
                side=side,
                order_type=order_type,
                reasons=reasons,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                quantity=quantity,
                exchange=exchange,
                snapshot=snapshot,
            )
        except Exception as exc:
            logger.warning("[RejectedTrades] Failed to log rejection for "
                           f"{symbol}/{strategy_name}: {exc}")

    def get_today(
        self,
        user_id: str,
        target_date: Optional[date] = None,
    ) -> List[dict]:
        """Return rejected trades for *target_date* (default = today UTC).

        Records are returned newest-first by latest_at.
        Both the user's own records AND "system" records are returned,
        supporting single-tenant deployments where the trading engine runs
        under a "system" account.
        """
        if target_date is None:
            target_date = datetime.now(timezone.utc).date()

        day_start = datetime.combine(target_date, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        day_end = day_start + timedelta(days=1)

        rows = (
            self.db.query(RejectedTrade)
            .filter(
                RejectedTrade.user_id.in_([user_id, "system"]),
                RejectedTrade.first_at >= day_start,
                RejectedTrade.first_at < day_end,
            )
            .order_by(RejectedTrade.latest_at.desc())
            .all()
        )
        return [self._to_dict(r) for r in rows]

    def get_by_id(self, user_id: str, record_id: int) -> Optional[dict]:
        """Return a single rejected-trade record (user-scoped)."""
        row = (
            self.db.query(RejectedTrade)
            .filter(
                RejectedTrade.id == record_id,
                RejectedTrade.user_id.in_([user_id, "system"]),
            )
            .first()
        )
        return self._to_dict(row) if row else None

    @staticmethod
    def cleanup_old(db: Session) -> int:
        """Delete records older than the configured retention period.
        Returns the number of rows deleted."""
        retention_days = getattr(settings, "rejected_trades_retention_days", 30)
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = (
            db.query(RejectedTrade)
            .filter(RejectedTrade.first_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(f"[RejectedTrades] Cleanup: deleted {deleted} records "
                    f"older than {retention_days} days.")
        return deleted

    # ── Internals ─────────────────────────────────────────────────────────────

    def _upsert(
        self,
        *,
        user_id: str,
        symbol: str,
        strategy_name: str,
        side: str,
        order_type: str,
        reasons: List[RejectionReason],
        entry_price: Optional[float],
        stop_loss: Optional[float],
        target: Optional[float],
        quantity: int,
        exchange: str,
        snapshot: Optional[RiskSnapshot],
    ) -> None:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)

        # Check for an existing record within the dedup window
        existing: Optional[RejectedTrade] = (
            self.db.query(RejectedTrade)
            .filter(
                RejectedTrade.user_id == user_id,
                RejectedTrade.symbol == symbol,
                RejectedTrade.strategy_name == strategy_name,
                RejectedTrade.side == side,
                RejectedTrade.latest_at >= cutoff,
            )
            .order_by(RejectedTrade.latest_at.desc())
            .first()
        )

        if existing is not None:
            existing.count += 1
            existing.latest_at = now
            # Update reasons + snapshot in case details changed
            existing.reasons = json.dumps([asdict(r) for r in reasons])
            if snapshot:
                existing.risk_snapshot = json.dumps(snapshot.to_dict())
            self.db.commit()
            return

        exposure = (quantity or 0) * (entry_price or 0.0)
        record = RejectedTrade(
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            strategy_name=strategy_name,
            side=side,
            order_type=order_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            quantity_requested=quantity or 0,
            exposure_requested=round(exposure, 2),
            reasons=json.dumps([asdict(r) for r in reasons]),
            risk_snapshot=json.dumps(snapshot.to_dict()) if snapshot else None,
            first_at=now,
            latest_at=now,
            count=1,
        )
        self.db.add(record)
        self.db.commit()
        logger.debug(f"[RejectedTrades] Logged rejection: {symbol}/{strategy_name} "
                     f"— {[r.code for r in reasons]}")

    @staticmethod
    def _to_dict(row: RejectedTrade) -> dict:
        reasons = []
        try:
            reasons = json.loads(row.reasons or "[]")
        except Exception:
            pass

        snapshot = {}
        try:
            snapshot = json.loads(row.risk_snapshot or "{}")
        except Exception:
            pass

        return {
            "id": row.id,
            "user_id": row.user_id,
            "symbol": row.symbol,
            "exchange": row.exchange,
            "strategy_name": row.strategy_name,
            "side": row.side,
            "order_type": row.order_type,
            "entry_price": row.entry_price,
            "stop_loss": row.stop_loss,
            "target": row.target,
            "quantity_requested": row.quantity_requested,
            "exposure_requested": row.exposure_requested,
            "reasons": reasons,
            "risk_snapshot": snapshot,
            "first_at": row.first_at.isoformat() if row.first_at else None,
            "latest_at": row.latest_at.isoformat() if row.latest_at else None,
            "count": row.count,
            # Derived helpers for the UI
            "primary_reason_code": reasons[0]["code"] if reasons else "UNKNOWN",
            "primary_reason_message": reasons[0]["message"] if reasons else "",
        }
