"""Portfolio Analytics API — all endpoints for the 5 portfolio features.

Routes:
  GET  /api/portfolio/risk-summary        Feature 1: Risk dashboard data
  GET  /api/plan/compounding              Feature 2: Compounding projection
  POST /api/rebalance/run                 Feature 3: Run monthly rebalancer
  GET  /api/rebalance/latest              Feature 3: Latest rebalance result
  POST /api/risk/ruin                     Feature 4: Monte Carlo ruin calc
  POST /api/allocation/compute            Feature 5: AAE compute targets
  GET  /api/allocation/current            Feature 5: Current allocation targets
  GET  /api/allocation/history            Feature 5: Allocation history (last 10)

All endpoints require a valid Supabase JWT (Depends(get_current_user)).
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_auth():
    from tradiqai_supabase_auth import get_current_user
    return get_current_user


def _get_db():
    from database import get_db
    return get_db


def _capital() -> float:
    try:
        from config import settings
        return float(getattr(settings, "cme_total_capital", 100_000.0))
    except Exception:
        return 100_000.0


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1 — Portfolio Risk Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/portfolio/risk-summary")
async def portfolio_risk_summary(
    current_user: dict = Depends(_get_auth()),
    db=Depends(_get_db()),
):
    """Return full institutional-style portfolio risk summary."""
    try:
        from services.portfolio_risk import PortfolioRiskService
        svc = PortfolioRiskService(db=db, total_capital=_capital())
        result = svc.compute()
        return result.to_dict()
    except Exception as e:
        logger.exception("[API] portfolio risk-summary error")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Feature 2 — Capital Compounding Plan
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/plan/compounding")
async def get_compounding_plan(
    current_user: dict = Depends(_get_auth()),
    db=Depends(_get_db()),
):
    """Return compounding plan projections + actual progress."""
    try:
        from services.compounding_plan import CompoundingPlanService
        svc = CompoundingPlanService(db=db, initial_capital=_capital())
        result = svc.compute()
        return result.to_dict()
    except Exception as e:
        logger.exception("[API] compounding plan error")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Feature 3 — Monthly Rebalancer
# ─────────────────────────────────────────────────────────────────────────────

class RebalanceRequest(BaseModel):
    lookback_days: int = 30
    current_allocations: Optional[dict] = None   # {bucket: pct}


@router.post("/api/rebalance/run")
async def run_rebalancer(
    body: RebalanceRequest,
    current_user: dict = Depends(_get_auth()),
    db=Depends(_get_db()),
):
    """Run the monthly rebalancer and persist result."""
    try:
        from services.rebalancer import RebalancerService
        from models import RebalanceRun

        svc = RebalancerService(
            db=db,
            lookback_days=body.lookback_days,
            current_allocations=body.current_allocations,
            total_capital=_capital(),
        )
        result = svc.run()

        # Persist to DB
        row = RebalanceRun(
            lookback_days=result.lookback_days,
            bucket_scores=json.dumps(
                {k: {"score": v.score, "trade_count": v.trade_count} for k, v in result.bucket_scores.items()}
            ),
            current_allocations=json.dumps(result.current_allocations),
            recommended_allocations=json.dumps(result.recommended_allocations),
            changes=json.dumps([
                {"bucket": c.bucket, "old_pct": c.old_pct, "new_pct": c.new_pct,
                 "delta_pct": c.delta_pct, "reason": c.reason}
                for c in result.changes
            ]),
            notes=result.notes,
        )
        db.add(row)
        db.commit()

        return result.to_dict()
    except Exception as e:
        logger.exception("[API] rebalance run error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/rebalance/latest")
async def get_latest_rebalance(
    current_user: dict = Depends(_get_auth()),
    db=Depends(_get_db()),
):
    """Fetch the most recent rebalancer run from DB."""
    try:
        from models import RebalanceRun
        row = (
            db.query(RebalanceRun)
            .order_by(RebalanceRun.run_date.desc())
            .first()
        )
        if not row:
            return {"message": "No rebalance runs yet. POST /api/rebalance/run to generate one."}

        return {
            "id": row.id,
            "run_date": row.run_date.isoformat() if row.run_date else None,
            "lookback_days": row.lookback_days,
            "bucket_scores": json.loads(row.bucket_scores or "{}"),
            "current_allocations": json.loads(row.current_allocations or "{}"),
            "recommended_allocations": json.loads(row.recommended_allocations or "{}"),
            "changes": json.loads(row.changes or "[]"),
            "notes": row.notes,
        }
    except Exception as e:
        logger.exception("[API] get latest rebalance error")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Feature 4 — Risk-of-Ruin Calculator
# ─────────────────────────────────────────────────────────────────────────────

class RuinRequest(BaseModel):
    ruin_threshold_pct: float = 20.0
    simulation_count: int = 2000
    trades_per_sim: int = 100


@router.post("/api/risk/ruin")
async def compute_risk_of_ruin(
    body: RuinRequest,
    current_user: dict = Depends(_get_auth()),
    db=Depends(_get_db()),
):
    """Run Monte Carlo risk-of-ruin simulation."""
    try:
        # Clamp inputs to safe ranges
        sims  = max(100, min(5000, body.simulation_count))
        trades= max(20,  min(500,  body.trades_per_sim))
        ruin  = max(5.0, min(50.0, body.ruin_threshold_pct))

        from services.risk_of_ruin import RiskOfRuinService
        svc = RiskOfRuinService(
            db=db,
            starting_capital=_capital(),
            ruin_threshold_pct=ruin,
            simulation_count=sims,
            trades_per_sim=trades,
        )
        result = svc.compute()
        return result.to_dict()
    except Exception as e:
        logger.exception("[API] risk of ruin error")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5 — Adaptive Allocation Engine
# ─────────────────────────────────────────────────────────────────────────────

class AAERequest(BaseModel):
    regime: str = "NEUTRAL"
    lookback_days: int = 30
    previous_targets: Optional[dict] = None


@router.post("/api/allocation/compute")
async def compute_allocation(
    body: AAERequest,
    current_user: dict = Depends(_get_auth()),
    db=Depends(_get_db()),
):
    """Compute and persist new weekly allocation targets."""
    try:
        from services.adaptive_allocation import AdaptiveAllocationEngine
        from models import AllocationTargets

        # Fetch previous targets from DB if not supplied
        prev = body.previous_targets
        if prev is None:
            latest = (
                db.query(AllocationTargets)
                .order_by(AllocationTargets.computed_at.desc())
                .first()
            )
            if latest and latest.targets:
                prev = json.loads(latest.targets)

        svc = AdaptiveAllocationEngine(
            db=db,
            regime=body.regime,
            lookback_days=body.lookback_days,
            total_capital=_capital(),
            previous_targets=prev,
        )
        result = svc.compute()

        # Persist
        targets_json = json.dumps({k: v.target_pct for k, v in result.targets.items()})
        row = AllocationTargets(
            regime=result.regime,
            lookback_days=result.lookback_days,
            targets=targets_json,
            deltas=json.dumps(result.deltas),
            total_allocated_pct=result.total_allocated_pct,
        )
        db.add(row)
        db.commit()

        return result.to_dict()
    except Exception as e:
        logger.exception("[API] allocation compute error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/allocation/current")
async def get_current_allocation(
    current_user: dict = Depends(_get_auth()),
    db=Depends(_get_db()),
):
    """Fetch the most recent allocation targets."""
    try:
        from models import AllocationTargets
        row = (
            db.query(AllocationTargets)
            .order_by(AllocationTargets.computed_at.desc())
            .first()
        )
        if not row:
            from services.adaptive_allocation import BASE_TARGETS
            return {
                "message": "No allocation targets computed yet. POST /api/allocation/compute to generate.",
                "defaults": BASE_TARGETS,
            }
        return {
            "id": row.id,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            "regime": row.regime,
            "targets": json.loads(row.targets or "{}"),
            "deltas": json.loads(row.deltas or "{}"),
            "total_allocated_pct": row.total_allocated_pct,
        }
    except Exception as e:
        logger.exception("[API] get current allocation error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/allocation/history")
async def get_allocation_history(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(_get_auth()),
    db=Depends(_get_db()),
):
    """Fetch last N allocation target snapshots."""
    try:
        from models import AllocationTargets
        rows = (
            db.query(AllocationTargets)
            .order_by(AllocationTargets.computed_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "computed_at": r.computed_at.isoformat() if r.computed_at else None,
                "regime": r.regime,
                "targets": json.loads(r.targets or "{}"),
                "total_allocated_pct": r.total_allocated_pct,
            }
            for r in rows
        ]
    except Exception as e:
        logger.exception("[API] get allocation history error")
        raise HTTPException(status_code=500, detail=str(e))
