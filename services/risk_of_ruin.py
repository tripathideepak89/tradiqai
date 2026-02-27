"""Risk-of-Ruin Service — Feature 4: Monte Carlo Risk-of-Ruin Calculator.

Uses historical R-multiple distribution from closed trades to bootstrap
Monte Carlo simulations and estimate the probability of ruin.

R-multiple = net_pnl / risk_amount  (e.g. +2.0 = 2R winner, -1.0 = full loser)

Ruin is defined as drawdown reaching or exceeding `ruin_threshold_pct` of
starting capital (default: 20%).

Outputs:
  - Ruin probability (% of simulations that hit the ruin threshold)
  - Median, 5th, 25th, 75th, 95th percentile equity curves
  - Recommended max concurrent risk
  - Kelly fraction
"""
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Reproducible seed for CI/testing; change to None for true randomness
_SIMULATION_SEED = 42


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskOfRuinResult:
    # Input parameters
    starting_capital: float
    ruin_threshold_pct: float    # % drawdown that constitutes "ruin"
    simulation_count: int
    trades_per_sim: int

    # R-multiple statistics
    r_multiple_count: int
    avg_r: float
    win_rate_pct: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float          # E[R] per trade
    kelly_fraction: float        # full Kelly %

    # Ruin analysis
    ruin_probability_pct: float  # % of sims that hit ruin
    median_final_capital: float
    pct5_final_capital: float    # 5th percentile (worst)
    pct25_final_capital: float
    pct75_final_capital: float
    pct95_final_capital: float   # 95th percentile (best)
    avg_max_drawdown_pct: float

    # Recommendations
    recommended_risk_per_trade_pct: float  # fractional Kelly suggestion
    safe_concurrent_positions: int

    # Percentile equity curves (sampled paths, one path per percentile)
    equity_curves: Dict[str, List[float]]  # "p5","p25","median","p75","p95"

    generated_at: datetime

    def to_dict(self) -> dict:
        return {
            "starting_capital": round(self.starting_capital, 2),
            "ruin_threshold_pct": self.ruin_threshold_pct,
            "simulation_count": self.simulation_count,
            "trades_per_sim": self.trades_per_sim,
            "r_multiple_count": self.r_multiple_count,
            "avg_r": round(self.avg_r, 4),
            "win_rate_pct": round(self.win_rate_pct, 2),
            "avg_win_r": round(self.avg_win_r, 4),
            "avg_loss_r": round(self.avg_loss_r, 4),
            "expectancy_r": round(self.expectancy_r, 4),
            "kelly_fraction": round(self.kelly_fraction, 4),
            "ruin_probability_pct": round(self.ruin_probability_pct, 2),
            "median_final_capital": round(self.median_final_capital, 2),
            "pct5_final_capital": round(self.pct5_final_capital, 2),
            "pct25_final_capital": round(self.pct25_final_capital, 2),
            "pct75_final_capital": round(self.pct75_final_capital, 2),
            "pct95_final_capital": round(self.pct95_final_capital, 2),
            "avg_max_drawdown_pct": round(self.avg_max_drawdown_pct, 2),
            "recommended_risk_per_trade_pct": round(self.recommended_risk_per_trade_pct, 2),
            "safe_concurrent_positions": self.safe_concurrent_positions,
            "equity_curves": {
                k: [round(v, 2) for v in curve]
                for k, curve in self.equity_curves.items()
            },
            "generated_at": self.generated_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class RiskOfRuinService:
    """Monte Carlo risk-of-ruin simulation using historical R-multiples."""

    DEFAULT_SIMS           = 2000
    DEFAULT_TRADES_PER_SIM = 100
    DEFAULT_RUIN_PCT       = 20.0    # 20% drawdown = ruin
    KELLY_DIVISOR          = 4.0     # use ¼ Kelly for conservatism

    def __init__(
        self,
        db: Session,
        starting_capital: float = 100_000.0,
        ruin_threshold_pct: float = DEFAULT_RUIN_PCT,
        simulation_count: int = DEFAULT_SIMS,
        trades_per_sim: int = DEFAULT_TRADES_PER_SIM,
        seed: Optional[int] = _SIMULATION_SEED,
    ):
        self.db = db
        self.starting_capital = starting_capital
        self.ruin_threshold_pct = ruin_threshold_pct
        self.simulation_count = simulation_count
        self.trades_per_sim = trades_per_sim
        self.rng = random.Random(seed)

    def compute(self) -> RiskOfRuinResult:
        r_multiples = self._load_r_multiples()

        if len(r_multiples) < 10:
            # Fallback: generate synthetic distribution (WR=55%, avg W=1.5R, avg L=-1R)
            logger.warning("[RiskOfRuin] Insufficient trade history (<10 trades). Using synthetic R-multiples.")
            r_multiples = self._synthetic_r_multiples(200, win_rate=0.55, avg_win=1.5, avg_loss=-1.0)

        stats = self._compute_stats(r_multiples)
        kelly = self._kelly_fraction(stats["win_rate"], stats["avg_win_r"], abs(stats["avg_loss_r"]))

        ruin_pct, final_caps, max_dds, sample_curves = self._run_monte_carlo(
            r_multiples, stats["risk_per_trade_pct"]
        )

        sorted_finals = sorted(final_caps)
        n = len(sorted_finals)

        equity_curves = self._percentile_curves(sample_curves)

        rec_risk = min(2.0, max(0.25, kelly / self.KELLY_DIVISOR * 100))  # cap at 2%
        safe_concurrent = max(1, int(self.starting_capital * rec_risk / 100 / (self.starting_capital * 0.01)))

        return RiskOfRuinResult(
            starting_capital=self.starting_capital,
            ruin_threshold_pct=self.ruin_threshold_pct,
            simulation_count=self.simulation_count,
            trades_per_sim=self.trades_per_sim,
            r_multiple_count=len(r_multiples),
            avg_r=stats["avg_r"],
            win_rate_pct=stats["win_rate"] * 100,
            avg_win_r=stats["avg_win_r"],
            avg_loss_r=stats["avg_loss_r"],
            expectancy_r=stats["expectancy_r"],
            kelly_fraction=kelly,
            ruin_probability_pct=ruin_pct,
            median_final_capital=sorted_finals[n // 2],
            pct5_final_capital=sorted_finals[max(0, int(n * 0.05))],
            pct25_final_capital=sorted_finals[max(0, int(n * 0.25))],
            pct75_final_capital=sorted_finals[min(n-1, int(n * 0.75))],
            pct95_final_capital=sorted_finals[min(n-1, int(n * 0.95))],
            avg_max_drawdown_pct=sum(max_dds) / len(max_dds) if max_dds else 0.0,
            recommended_risk_per_trade_pct=rec_risk,
            safe_concurrent_positions=safe_concurrent,
            equity_curves=equity_curves,
            generated_at=datetime.utcnow(),
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _load_r_multiples(self) -> List[float]:
        from models import Trade, TradeStatus
        trades = (
            self.db.query(Trade)
            .filter(
                Trade.status == TradeStatus.CLOSED,
                Trade.risk_amount > 0,
            )
            .all()
        )
        result = []
        for t in trades:
            if t.risk_amount and t.risk_amount > 0 and t.net_pnl is not None:
                result.append(t.net_pnl / t.risk_amount)
        return result

    def _synthetic_r_multiples(
        self,
        n: int,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> List[float]:
        result = []
        for _ in range(n):
            if self.rng.random() < win_rate:
                r = avg_win * self.rng.uniform(0.5, 1.5)
            else:
                r = avg_loss * self.rng.uniform(0.5, 1.5)
            result.append(r)
        return result

    def _compute_stats(self, r_multiples: List[float]) -> dict:
        wins   = [r for r in r_multiples if r > 0]
        losses = [r for r in r_multiples if r <= 0]
        n = len(r_multiples)
        win_rate  = len(wins) / n if n else 0
        avg_win   = sum(wins)   / len(wins)   if wins   else 0.0
        avg_loss  = sum(losses) / len(losses) if losses else 0.0
        avg_r     = sum(r_multiples) / n      if n       else 0.0
        exp_r     = win_rate * avg_win + (1 - win_rate) * avg_loss
        # Use CME's 1% as baseline risk per trade
        return {
            "win_rate": win_rate,
            "avg_win_r": avg_win,
            "avg_loss_r": avg_loss,
            "avg_r": avg_r,
            "expectancy_r": exp_r,
            "risk_per_trade_pct": 1.0,
        }

    def _kelly_fraction(self, win_rate: float, avg_win: float, avg_loss_abs: float) -> float:
        """Full Kelly = W/|L| - (1-W)/W  (simplified for non-binary bets)."""
        if avg_loss_abs <= 0 or win_rate <= 0:
            return 0.0
        # Kelly = (W*b - (1-W)) / b  where b = avg_win / avg_loss
        b = avg_win / avg_loss_abs
        kelly = (win_rate * b - (1 - win_rate)) / b
        return max(0.0, min(1.0, kelly))

    def _run_monte_carlo(
        self,
        r_multiples: List[float],
        risk_pct: float,
    ) -> Tuple[float, List[float], List[float], List[List[float]]]:
        ruin_threshold = self.starting_capital * (1 - self.ruin_threshold_pct / 100)
        ruin_count = 0
        final_caps = []
        max_dds = []
        sample_paths = []  # store 100 paths for percentile curves

        for sim in range(self.simulation_count):
            capital = self.starting_capital
            peak = capital
            max_dd = 0.0
            path = [capital]

            for _ in range(self.trades_per_sim):
                r = self.rng.choice(r_multiples)
                risk_amount = capital * risk_pct / 100.0
                capital += r * risk_amount
                capital = max(0.0, capital)
                peak = max(peak, capital)
                dd = (peak - capital) / peak * 100 if peak > 0 else 0.0
                max_dd = max(max_dd, dd)
                path.append(capital)

                if capital <= ruin_threshold:
                    ruin_count += 1
                    break

            final_caps.append(capital)
            max_dds.append(max_dd)
            if sim < 100:
                sample_paths.append(path)

        ruin_pct = ruin_count / self.simulation_count * 100
        return ruin_pct, final_caps, max_dds, sample_paths

    def _percentile_curves(self, paths: List[List[float]]) -> Dict[str, List[float]]:
        """Build 5 representative equity curves at p5/p25/median/p75/p95."""
        if not paths:
            return {"p5": [], "p25": [], "median": [], "p75": [], "p95": []}

        # Find the path whose final capital is closest to each percentile
        finals_with_idx = sorted(enumerate(paths), key=lambda x: x[1][-1])
        n = len(finals_with_idx)

        def pick(pct):
            idx = finals_with_idx[int(n * pct / 100)][0]
            return paths[idx]

        # Pad all paths to same length
        max_len = max(len(p) for p in paths)

        def pad(path):
            return path + [path[-1]] * (max_len - len(path))

        return {
            "p5":     pad(pick(5)),
            "p25":    pad(pick(25)),
            "median": pad(pick(50)),
            "p75":    pad(pick(75)),
            "p95":    pad(pick(95)),
        }
