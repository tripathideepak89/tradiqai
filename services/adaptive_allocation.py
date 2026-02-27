"""Adaptive Allocation Engine (AAE) — Feature 5.

Computes weekly recommended target allocations by combining:
  1. Market regime (BULL/BEAR/SIDEWAYS/NEUTRAL) — from CME
  2. Recent strategy performance (last 30 days)
  3. Volatility adjustment (recent drawdown vs historical)

Output: updated allocation targets that are stored in the DB and served
to the dashboard for manual review before any changes are applied.

AAE does NOT auto-trade.  Allocations are recommendations only.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Base allocations (these are the neutral defaults)
# ─────────────────────────────────────────────────────────────────────────────

BASE_TARGETS: Dict[str, float] = {
    "DIVIDEND": 25.0,
    "SWING":    30.0,
    "MID_TERM": 30.0,
    "INTRADAY": 10.0,
    "CASH":      5.0,
}

# Regime multipliers: applied to non-cash buckets
REGIME_BIAS: Dict[str, Dict[str, float]] = {
    "BULL":     {"DIVIDEND": 1.0, "SWING": 1.1, "MID_TERM": 1.0, "INTRADAY": 1.1},
    "BEAR":     {"DIVIDEND": 1.1, "SWING": 0.7, "MID_TERM": 0.8, "INTRADAY": 0.5},
    "SIDEWAYS": {"DIVIDEND": 1.1, "SWING": 0.9, "MID_TERM": 1.0, "INTRADAY": 0.7},
    "NEUTRAL":  {"DIVIDEND": 1.0, "SWING": 0.9, "MID_TERM": 1.0, "INTRADAY": 0.6},
}

BUCKET_FLOOR   = 5.0
BUCKET_CEILING = 40.0
CASH_FLOOR     = 5.0


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AllocationTarget:
    bucket: str
    target_pct: float
    base_pct: float
    regime_adj: float        # % points added/removed by regime
    perf_adj: float          # % points added/removed by performance
    vol_adj: float           # % points added/removed by volatility
    rationale: str


@dataclass
class AAEResult:
    computed_at: datetime
    regime: str
    lookback_days: int
    targets: Dict[str, AllocationTarget]
    total_allocated_pct: float    # should sum to 100
    previous_targets: Optional[Dict[str, float]]
    deltas: Dict[str, float]      # bucket → delta vs previous

    def to_dict(self) -> dict:
        return {
            "computed_at": self.computed_at.isoformat(),
            "regime": self.regime,
            "lookback_days": self.lookback_days,
            "targets": {
                k: {
                    "bucket": v.bucket,
                    "target_pct": round(v.target_pct, 2),
                    "base_pct": round(v.base_pct, 2),
                    "regime_adj": round(v.regime_adj, 2),
                    "perf_adj": round(v.perf_adj, 2),
                    "vol_adj": round(v.vol_adj, 2),
                    "rationale": v.rationale,
                }
                for k, v in self.targets.items()
            },
            "total_allocated_pct": round(self.total_allocated_pct, 2),
            "previous_targets": {k: round(v, 2) for k, v in (self.previous_targets or {}).items()},
            "deltas": {k: round(v, 2) for k, v in self.deltas.items()},
        }


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class AdaptiveAllocationEngine:
    """Weekly allocation target calculator."""

    def __init__(
        self,
        db: Session,
        regime: str = "NEUTRAL",
        lookback_days: int = 30,
        total_capital: float = 100_000.0,
        previous_targets: Optional[Dict[str, float]] = None,
    ):
        self.db = db
        self.regime = regime if regime in REGIME_BIAS else "NEUTRAL"
        self.lookback_days = lookback_days
        self.total_capital = total_capital
        self.previous_targets = previous_targets

    def compute(self) -> AAEResult:
        from models import Trade, TradeStatus
        from capital_manager import CapitalManager

        since = datetime.utcnow() - timedelta(days=self.lookback_days)
        closed = (
            self.db.query(Trade)
            .filter(
                Trade.status == TradeStatus.CLOSED,
                Trade.exit_timestamp >= since,
            )
            .all()
        )

        # Group by bucket
        bucket_trades: Dict[str, list] = {b: [] for b in BASE_TARGETS if b != "CASH"}
        for t in closed:
            product = CapitalManager._product_from_notes(t.notes or "")
            bucket  = CapitalManager._map_to_bucket(t.strategy_name or "", product)
            bucket_trades.setdefault(bucket, []).append(t)

        # Compute performance scores per bucket (0-100)
        perf_scores = self._performance_scores(bucket_trades)

        # Volatility factor: portfolio-level recent DD vs 3% threshold
        vol_factor = self._volatility_factor(closed)

        # Build raw targets
        raw: Dict[str, float] = {}
        target_objects: Dict[str, AllocationTarget] = {}
        regime_bias = REGIME_BIAS.get(self.regime, REGIME_BIAS["NEUTRAL"])

        for bucket in BASE_TARGETS:
            if bucket == "CASH":
                continue
            base = BASE_TARGETS[bucket]
            bias = regime_bias.get(bucket, 1.0)

            # Regime adjustment
            regime_adj = (bias - 1.0) * base  # e.g. 1.1 on 25% = +2.5pp

            # Performance adjustment: score 0-100, neutral = 50
            # score 70+ → +3%, score 30- → -3%
            pscore = perf_scores.get(bucket, 50.0)
            if pscore >= 70:
                perf_adj = +3.0
            elif pscore <= 30:
                perf_adj = -3.0
            else:
                perf_adj = 0.0

            # Volatility adjustment: if recent DD > 3% portfolio, reduce all
            vol_adj = -2.0 * vol_factor  # up to -2pp reduction

            raw_pct = base + regime_adj + perf_adj + vol_adj
            raw_pct = max(BUCKET_FLOOR, min(BUCKET_CEILING, raw_pct))
            raw[bucket] = raw_pct

            rationale_parts = [f"base={base:.0f}%"]
            if abs(regime_adj) > 0.1:
                rationale_parts.append(f"regime({self.regime})={regime_adj:+.1f}%")
            if abs(perf_adj) > 0.1:
                rationale_parts.append(f"performance={perf_adj:+.1f}% (score={pscore:.0f})")
            if abs(vol_adj) > 0.1:
                rationale_parts.append(f"volatility={vol_adj:+.1f}%")

            target_objects[bucket] = AllocationTarget(
                bucket=bucket,
                target_pct=raw_pct,  # will be updated after normalisation
                base_pct=base,
                regime_adj=regime_adj,
                perf_adj=perf_adj,
                vol_adj=vol_adj,
                rationale=", ".join(rationale_parts),
            )

        # Normalise trading buckets to (100 - CASH_FLOOR)%
        trading_sum = sum(raw.values())
        if trading_sum > 0:
            scale = (100.0 - CASH_FLOOR) / trading_sum
            for b in raw:
                raw[b] = round(raw[b] * scale, 2)
                target_objects[b].target_pct = raw[b]
        raw["CASH"] = CASH_FLOOR
        target_objects["CASH"] = AllocationTarget(
            bucket="CASH",
            target_pct=CASH_FLOOR,
            base_pct=CASH_FLOOR,
            regime_adj=0.0,
            perf_adj=0.0,
            vol_adj=0.0,
            rationale="Minimum cash reserve (5%)",
        )

        # Compute deltas vs previous
        prev = self.previous_targets or BASE_TARGETS
        deltas = {b: raw.get(b, 0.0) - prev.get(b, 0.0) for b in raw}

        return AAEResult(
            computed_at=datetime.utcnow(),
            regime=self.regime,
            lookback_days=self.lookback_days,
            targets=target_objects,
            total_allocated_pct=sum(raw.values()),
            previous_targets=prev,
            deltas=deltas,
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _performance_scores(self, bucket_trades: Dict[str, list]) -> Dict[str, float]:
        """Simple performance score 0-100 per bucket."""
        scores = {}
        for bucket, trades in bucket_trades.items():
            if not trades:
                scores[bucket] = 50.0
                continue
            wins    = [t for t in trades if (t.net_pnl or 0) > 0]
            losses  = [t for t in trades if (t.net_pnl or 0) <= 0]
            wr      = len(wins) / len(trades) * 100
            gp      = sum((t.net_pnl or 0) for t in wins)
            gl      = abs(sum((t.net_pnl or 0) for t in losses))
            pf      = (gp / gl) if gl > 0 else (3.0 if gp > 0 else 0.0)
            pf_score= min(100, pf / 3.0 * 100)
            score   = wr * 0.5 + pf_score * 0.5
            scores[bucket] = min(100.0, max(0.0, score))
        return scores

    def _volatility_factor(self, closed_trades: list) -> float:
        """Return a 0-1 scale factor representing how stressed the portfolio is.

        0 = calm (no recent drawdown), 1 = high stress (>= 12% recent drawdown).
        """
        if not closed_trades:
            return 0.0
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in sorted(closed_trades, key=lambda x: x.exit_timestamp or datetime.min):
            cumulative += (t.net_pnl or 0)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / self.total_capital * 100 if self.total_capital else 0.0
            max_dd = max(max_dd, dd)

        # Scale: 3% DD = 0.5 stress, 12% = 1.0
        factor = min(1.0, max(0.0, (max_dd - 3.0) / 9.0))
        return factor
