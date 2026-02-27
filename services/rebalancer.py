"""Rebalancer Service — Feature 3: Automated Monthly Rebalancer.

Scores each strategy bucket on recent performance and produces
TARGET ALLOCATION RECOMMENDATIONS only — no auto-trading.

Scoring (out of 100):
  30% weighted return      (annualised from closed trades)
  20% profit factor
  20% max drawdown (inverted; lower DD = better score)
  15% win rate
  15% equity slope (recent momentum of net PnL)

Adjustment rules:
  Score > 70 → +5%  allocation
  Score < 40 → -5%  allocation
  Max single-month change: ±10%
  Hard floor:  5%  per bucket
  Hard ceiling: 40% per bucket
"""
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

BASE_ALLOCATIONS: Dict[str, float] = {
    "DIVIDEND": 25.0,
    "SWING":    30.0,
    "MID_TERM": 30.0,
    "INTRADAY": 10.0,
    "CASH":      5.0,
}

BUCKET_FLOOR   = 5.0
BUCKET_CEILING = 40.0
MAX_CHANGE     = 10.0     # max ±% per rebalance cycle
HIGH_SCORE     = 70.0     # +5%
LOW_SCORE      = 40.0     # -5%


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BucketScore:
    bucket: str
    score: float           # 0-100
    trade_count: int
    win_rate_pct: float
    profit_factor: float
    annualised_return_pct: float
    max_drawdown_pct: float
    equity_slope: float    # linear regression slope of cumulative PnL


@dataclass
class AllocationChange:
    bucket: str
    old_pct: float
    new_pct: float
    delta_pct: float
    reason: str


@dataclass
class RebalanceResult:
    run_date: datetime
    lookback_days: int
    bucket_scores: Dict[str, BucketScore]
    current_allocations: Dict[str, float]   # before rebalance
    recommended_allocations: Dict[str, float]  # after rebalance
    changes: List[AllocationChange]
    notes: str

    def to_dict(self) -> dict:
        return {
            "run_date": self.run_date.isoformat(),
            "lookback_days": self.lookback_days,
            "bucket_scores": {
                k: {
                    "bucket": v.bucket,
                    "score": round(v.score, 2),
                    "trade_count": v.trade_count,
                    "win_rate_pct": round(v.win_rate_pct, 2),
                    "profit_factor": round(v.profit_factor, 4),
                    "annualised_return_pct": round(v.annualised_return_pct, 2),
                    "max_drawdown_pct": round(v.max_drawdown_pct, 2),
                    "equity_slope": round(v.equity_slope, 4),
                }
                for k, v in self.bucket_scores.items()
            },
            "current_allocations": {k: round(v, 2) for k, v in self.current_allocations.items()},
            "recommended_allocations": {k: round(v, 2) for k, v in self.recommended_allocations.items()},
            "changes": [
                {
                    "bucket": c.bucket,
                    "old_pct": round(c.old_pct, 2),
                    "new_pct": round(c.new_pct, 2),
                    "delta_pct": round(c.delta_pct, 2),
                    "reason": c.reason,
                }
                for c in self.changes
            ],
            "notes": self.notes,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class RebalancerService:
    """Score strategy buckets and recommend allocation changes."""

    def __init__(
        self,
        db: Session,
        lookback_days: int = 30,
        current_allocations: Optional[Dict[str, float]] = None,
        total_capital: float = 100_000.0,
    ):
        self.db = db
        self.lookback_days = lookback_days
        self.total_capital = total_capital
        self.current_allocs = current_allocations or dict(BASE_ALLOCATIONS)

    def run(self) -> RebalanceResult:
        from models import Trade, TradeStatus
        from capital_manager import CapitalManager

        since = datetime.utcnow() - timedelta(days=self.lookback_days)
        closed = (
            self.db.query(Trade)
            .filter(
                Trade.status == TradeStatus.CLOSED,
                Trade.exit_timestamp >= since,
            )
            .order_by(Trade.exit_timestamp)
            .all()
        )

        # Group trades by bucket
        bucket_trades: Dict[str, list] = {b: [] for b in BASE_ALLOCATIONS if b != "CASH"}
        for t in closed:
            product = CapitalManager._product_from_notes(t.notes or "")
            bucket  = CapitalManager._map_to_bucket(t.strategy_name or "", product)
            bucket_trades.setdefault(bucket, []).append(t)

        # Score each bucket
        scores: Dict[str, BucketScore] = {}
        for bucket, trades in bucket_trades.items():
            scores[bucket] = self._score_bucket(bucket, trades)

        # Generate recommendations
        new_allocs = dict(self.current_allocs)
        changes: List[AllocationChange] = []

        for bucket, bs in scores.items():
            old_pct = self.current_allocs.get(bucket, BASE_ALLOCATIONS.get(bucket, 10.0))
            delta = 0.0
            reason = "No change"

            if bs.score >= HIGH_SCORE:
                delta = +5.0
                reason = f"Score {bs.score:.0f} ≥ {HIGH_SCORE:.0f} → +5% allocation"
            elif bs.score <= LOW_SCORE:
                delta = -5.0
                reason = f"Score {bs.score:.0f} ≤ {LOW_SCORE:.0f} → -5% allocation"
            elif bs.trade_count == 0:
                reason = "No trades in lookback window — allocation unchanged"

            # Clamp to ±10% max change
            delta = max(-MAX_CHANGE, min(MAX_CHANGE, delta))
            new_pct = old_pct + delta
            # Apply floor / ceiling
            new_pct = max(BUCKET_FLOOR, min(BUCKET_CEILING, new_pct))

            new_allocs[bucket] = new_pct
            if abs(new_pct - old_pct) > 0.01:
                changes.append(AllocationChange(
                    bucket=bucket,
                    old_pct=old_pct,
                    new_pct=new_pct,
                    delta_pct=new_pct - old_pct,
                    reason=reason,
                ))

        # Normalise so trading buckets sum to 95% (leaving 5% CASH)
        trading_total = sum(v for k, v in new_allocs.items() if k != "CASH")
        if trading_total > 0:
            factor = 95.0 / trading_total
            for k in new_allocs:
                if k != "CASH":
                    new_allocs[k] = round(new_allocs[k] * factor, 2)
        new_allocs["CASH"] = 5.0

        notes = (
            f"Rebalance based on {self.lookback_days}-day window. "
            f"{len(closed)} closed trades analysed. "
            f"{len(changes)} allocation changes recommended."
        )

        return RebalanceResult(
            run_date=datetime.utcnow(),
            lookback_days=self.lookback_days,
            bucket_scores=scores,
            current_allocations=dict(self.current_allocs),
            recommended_allocations=new_allocs,
            changes=changes,
            notes=notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _score_bucket(self, bucket: str, trades: list) -> BucketScore:
        if not trades:
            return BucketScore(
                bucket=bucket,
                score=50.0,  # neutral score — no data
                trade_count=0,
                win_rate_pct=0.0,
                profit_factor=0.0,
                annualised_return_pct=0.0,
                max_drawdown_pct=0.0,
                equity_slope=0.0,
            )

        wins   = [t for t in trades if (t.net_pnl or 0) > 0]
        losses = [t for t in trades if (t.net_pnl or 0) <= 0]
        total_pnl    = sum((t.net_pnl or 0) for t in trades)
        gross_profit = sum((t.net_pnl or 0) for t in wins)
        gross_loss   = abs(sum((t.net_pnl or 0) for t in losses))

        win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
        pf = (gross_profit / gross_loss) if gross_loss > 0 else (5.0 if gross_profit > 0 else 0.0)

        # Annualised return
        avg_capital = self.total_capital * BASE_ALLOCATIONS.get(bucket, 10.0) / 100.0
        period_return_pct = (total_pnl / avg_capital * 100) if avg_capital > 0 else 0.0
        ann_return = period_return_pct * (365.0 / self.lookback_days)

        # Max drawdown from equity curve
        max_dd = self._max_drawdown(trades)

        # Equity slope (linear regression slope of cumulative PnL)
        slope = self._equity_slope(trades)

        # ── Weighted score ────────────────────────────────────────────────────
        # Return score: 0-100 mapped from -20% to +20% annualised
        return_score  = min(100, max(0, (ann_return + 20) / 40 * 100))
        # PF score: 0-100 mapped from 0 to 3
        pf_score      = min(100, max(0, pf / 3.0 * 100))
        # Drawdown score: 0-100, lower DD = higher score
        dd_score      = max(0, 100 - (max_dd * 5))     # -5 pts per 1% DD
        # Win rate score: direct
        wr_score      = win_rate
        # Slope score: 0-100
        slope_score   = min(100, max(0, 50 + slope * 50))

        composite = (
            return_score  * 0.30 +
            pf_score      * 0.20 +
            dd_score      * 0.20 +
            wr_score      * 0.15 +
            slope_score   * 0.15
        )

        return BucketScore(
            bucket=bucket,
            score=composite,
            trade_count=len(trades),
            win_rate_pct=win_rate,
            profit_factor=pf,
            annualised_return_pct=ann_return,
            max_drawdown_pct=max_dd,
            equity_slope=slope,
        )

    def _max_drawdown(self, trades: list) -> float:
        """Max drawdown (%) from sequential equity curve of bucket's trades."""
        if not trades:
            return 0.0
        equity = 0.0
        peak   = 0.0
        max_dd = 0.0
        for t in sorted(trades, key=lambda x: x.exit_timestamp or datetime.min):
            equity += (t.net_pnl or 0)
            peak = max(peak, equity)
            dd = (peak - equity)
            max_dd = max(max_dd, dd)
        base = self.total_capital * BASE_ALLOCATIONS.get(trades[0].strategy_name or "", 10.0) / 100.0 if trades else 1.0
        return (max_dd / base * 100) if base > 0 else 0.0

    def _equity_slope(self, trades: list) -> float:
        """Normalised linear slope of cumulative PnL series (−1 to +1)."""
        if len(trades) < 2:
            return 0.0
        sorted_t = sorted(trades, key=lambda x: x.exit_timestamp or datetime.min)
        y = []
        cum = 0.0
        for t in sorted_t:
            cum += (t.net_pnl or 0)
            y.append(cum)
        n = len(y)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        den = sum((xi - x_mean) ** 2 for xi in x)
        if den == 0:
            return 0.0
        slope = num / den
        # Normalise: divide by average absolute PnL so it's scale-independent
        avg_abs = sum(abs(t.net_pnl or 0) for t in trades) / n
        norm = slope / avg_abs if avg_abs > 0 else 0.0
        return max(-1.0, min(1.0, norm))
