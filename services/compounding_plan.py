"""Compounding Plan Service — Feature 2: Capital Compounding Plan (₹1L → ₹5L).

Generates multi-year projection in 3 scenarios:
  - Conservative: 1.5% monthly return, 2% monthly max risk
  - Base:         3.0% monthly return, 3% monthly max risk
  - Aggressive:   5.0% monthly return, 5% monthly max risk

Tracks real progress against the base projection using actual closed trades.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SCENARIOS = {
    "conservative": {
        "monthly_return_pct": 1.5,
        "monthly_risk_pct":   2.0,
        "description": "Low-risk, consistent 1.5%/month — 18-24 months to ₹5L",
    },
    "base": {
        "monthly_return_pct": 3.0,
        "monthly_risk_pct":   3.0,
        "description": "Balanced 3%/month — target 12-15 months to ₹5L",
    },
    "aggressive": {
        "monthly_return_pct": 5.0,
        "monthly_risk_pct":   5.0,
        "description": "High-risk 5%/month — 8-10 months to ₹5L (requires skill + discipline)",
    },
}

TARGET_CAPITAL = 500_000.0   # ₹5,00,000


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MonthlyProjection:
    month: int
    capital: float
    monthly_profit: float
    cumulative_profit: float
    monthly_risk_budget: float


@dataclass
class ScenarioProjection:
    name: str
    description: str
    monthly_return_pct: float
    monthly_risk_pct: float
    months_to_target: Optional[int]
    projected_capital_12m: float
    projected_capital_24m: float
    monthly_data: List[MonthlyProjection]


@dataclass
class ActualProgress:
    months_elapsed: int
    realized_pnl: float
    current_capital: float
    pct_gain: float
    monthly_avg_return_pct: float
    on_track_base: bool           # ahead of base scenario?
    milestone_pct: float          # % of the way to ₹5L goal


@dataclass
class CompoundingPlanResult:
    initial_capital: float
    target_capital: float
    scenarios: Dict[str, ScenarioProjection]
    actual_progress: ActualProgress
    milestones: List[dict]         # [{label, amount, base_month}]
    generated_at: datetime

    def to_dict(self) -> dict:
        def _scenario_dict(s: ScenarioProjection) -> dict:
            return {
                "name": s.name,
                "description": s.description,
                "monthly_return_pct": s.monthly_return_pct,
                "monthly_risk_pct": s.monthly_risk_pct,
                "months_to_target": s.months_to_target,
                "projected_capital_12m": round(s.projected_capital_12m, 2),
                "projected_capital_24m": round(s.projected_capital_24m, 2),
                "monthly_data": [
                    {
                        "month": m.month,
                        "capital": round(m.capital, 2),
                        "monthly_profit": round(m.monthly_profit, 2),
                        "cumulative_profit": round(m.cumulative_profit, 2),
                        "monthly_risk_budget": round(m.monthly_risk_budget, 2),
                    }
                    for m in s.monthly_data
                ],
            }

        return {
            "initial_capital": round(self.initial_capital, 2),
            "target_capital": round(self.target_capital, 2),
            "scenarios": {k: _scenario_dict(v) for k, v in self.scenarios.items()},
            "actual_progress": {
                "months_elapsed": self.actual_progress.months_elapsed,
                "realized_pnl": round(self.actual_progress.realized_pnl, 2),
                "current_capital": round(self.actual_progress.current_capital, 2),
                "pct_gain": round(self.actual_progress.pct_gain, 2),
                "monthly_avg_return_pct": round(self.actual_progress.monthly_avg_return_pct, 2),
                "on_track_base": self.actual_progress.on_track_base,
                "milestone_pct": round(self.actual_progress.milestone_pct, 2),
            },
            "milestones": self.milestones,
            "generated_at": self.generated_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class CompoundingPlanService:
    """Generate compounding projection + track actual progress."""

    MAX_MONTHS = 36  # Project out to 3 years max

    def __init__(self, db: Session, initial_capital: float = 100_000.0):
        self.db = db
        self.initial_capital = initial_capital

    def compute(self) -> CompoundingPlanResult:
        scenarios = {
            name: self._project_scenario(name, params)
            for name, params in SCENARIOS.items()
        }

        actual = self._actual_progress(scenarios["base"])
        milestones = self._milestones(scenarios["base"])

        return CompoundingPlanResult(
            initial_capital=self.initial_capital,
            target_capital=TARGET_CAPITAL,
            scenarios=scenarios,
            actual_progress=actual,
            milestones=milestones,
            generated_at=datetime.utcnow(),
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _project_scenario(self, name: str, params: dict) -> ScenarioProjection:
        monthly_r = params["monthly_return_pct"] / 100.0
        monthly_risk_pct = params["monthly_risk_pct"]

        monthly_data = []
        capital = self.initial_capital
        months_to_target = None

        for m in range(1, self.MAX_MONTHS + 1):
            profit = capital * monthly_r
            capital += profit
            monthly_data.append(MonthlyProjection(
                month=m,
                capital=capital,
                monthly_profit=profit,
                cumulative_profit=capital - self.initial_capital,
                monthly_risk_budget=capital * monthly_risk_pct / 100.0,
            ))
            if capital >= TARGET_CAPITAL and months_to_target is None:
                months_to_target = m

        cap_12 = monthly_data[11].capital if len(monthly_data) >= 12 else monthly_data[-1].capital
        cap_24 = monthly_data[23].capital if len(monthly_data) >= 24 else monthly_data[-1].capital

        return ScenarioProjection(
            name=name,
            description=params["description"],
            monthly_return_pct=params["monthly_return_pct"],
            monthly_risk_pct=params["monthly_risk_pct"],
            months_to_target=months_to_target,
            projected_capital_12m=cap_12,
            projected_capital_24m=cap_24,
            monthly_data=monthly_data,
        )

    def _actual_progress(self, base_scenario: ScenarioProjection) -> ActualProgress:
        from models import Trade, TradeStatus
        closed = (
            self.db.query(Trade)
            .filter(Trade.status == TradeStatus.CLOSED)
            .order_by(Trade.exit_timestamp)
            .all()
        )

        realized_pnl = sum((t.net_pnl or 0) for t in closed)
        current_capital = self.initial_capital + realized_pnl
        pct_gain = (realized_pnl / self.initial_capital * 100) if self.initial_capital else 0.0

        # Months elapsed since first trade
        months_elapsed = 0
        if closed:
            first_ts = closed[0].exit_timestamp
            if first_ts:
                delta = datetime.utcnow() - first_ts.replace(tzinfo=None) if first_ts.tzinfo else datetime.utcnow() - first_ts
                months_elapsed = max(1, int(delta.days / 30))

        monthly_avg = pct_gain / months_elapsed if months_elapsed > 0 else 0.0

        # On track vs base?
        base_at_now = base_scenario.monthly_data[months_elapsed - 1].capital if months_elapsed > 0 and months_elapsed <= len(base_scenario.monthly_data) else self.initial_capital
        on_track = current_capital >= base_at_now

        # % toward ₹5L goal
        gain_needed = TARGET_CAPITAL - self.initial_capital
        gain_achieved = max(0.0, current_capital - self.initial_capital)
        milestone_pct = min(100.0, (gain_achieved / gain_needed * 100) if gain_needed > 0 else 0.0)

        return ActualProgress(
            months_elapsed=months_elapsed,
            realized_pnl=realized_pnl,
            current_capital=current_capital,
            pct_gain=pct_gain,
            monthly_avg_return_pct=monthly_avg,
            on_track_base=on_track,
            milestone_pct=milestone_pct,
        )

    def _milestones(self, base_scenario: ScenarioProjection) -> List[dict]:
        targets = [
            ("₹1.25L", 125_000),
            ("₹1.50L", 150_000),
            ("₹2L",    200_000),
            ("₹2.50L", 250_000),
            ("₹3L",    300_000),
            ("₹4L",    400_000),
            ("₹5L",    500_000),
        ]
        milestones = []
        for label, amount in targets:
            # Find which month in base scenario this is reached
            base_month = None
            for m in base_scenario.monthly_data:
                if m.capital >= amount:
                    base_month = m.month
                    break
            milestones.append({
                "label": label,
                "amount": amount,
                "base_month": base_month,
            })
        return milestones
