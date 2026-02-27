"""Portfolio Risk Service — Feature 1: Institutional-Style Portfolio Risk Dashboard.

Computes read-only risk metrics from local trade history:
  - Equity curve + drawdown series
  - Open exposure by strategy/sector
  - Position concentration (Herfindahl index)
  - Compliance flags (rule breaches)
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ComplianceFlag:
    rule: str
    severity: str      # WARNING | BREACH
    message: str


@dataclass
class PortfolioRiskSummary:
    # Capital
    total_capital: float
    cash_available: float
    total_exposure: float
    exposure_pct: float

    # Drawdown
    peak_equity: float
    current_equity: float
    drawdown_pct: float
    max_historical_drawdown_pct: float

    # Performance (all-time closed trades)
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    expectancy: float           # ₹ expected per trade
    total_realized_pnl: float

    # Concentration
    herfindahl_index: float     # 0→1; higher = more concentrated
    top_concentration_symbol: str
    top_concentration_pct: float

    # Exposure breakdown
    strategy_exposure: Dict[str, float]   # bucket → ₹
    sector_exposure: Dict[str, float]     # sector → ₹
    open_positions: List[dict]            # lightweight position list

    # Compliance
    compliance_flags: List[ComplianceFlag]

    # Equity curve (last 60 days)
    equity_curve: List[dict]              # [{date, equity}]
    drawdown_series: List[dict]           # [{date, drawdown_pct}]

    # Meta
    generated_at: datetime

    def to_dict(self) -> dict:
        return {
            "total_capital": round(self.total_capital, 2),
            "cash_available": round(self.cash_available, 2),
            "total_exposure": round(self.total_exposure, 2),
            "exposure_pct": round(self.exposure_pct, 2),
            "peak_equity": round(self.peak_equity, 2),
            "current_equity": round(self.current_equity, 2),
            "drawdown_pct": round(self.drawdown_pct, 2),
            "max_historical_drawdown_pct": round(self.max_historical_drawdown_pct, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 4),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "expectancy": round(self.expectancy, 2),
            "total_realized_pnl": round(self.total_realized_pnl, 2),
            "herfindahl_index": round(self.herfindahl_index, 4),
            "top_concentration_symbol": self.top_concentration_symbol,
            "top_concentration_pct": round(self.top_concentration_pct, 2),
            "strategy_exposure": {k: round(v, 2) for k, v in self.strategy_exposure.items()},
            "sector_exposure": {k: round(v, 2) for k, v in self.sector_exposure.items()},
            "open_positions": self.open_positions,
            "compliance_flags": [
                {"rule": f.rule, "severity": f.severity, "message": f.message}
                for f in self.compliance_flags
            ],
            "equity_curve": self.equity_curve,
            "drawdown_series": self.drawdown_series,
            "generated_at": self.generated_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Service
# ─────────────────────────────────────────────────────────────────────────────

class PortfolioRiskService:
    """Computes full portfolio risk summary from local DB."""

    # Thresholds for compliance flags
    MAX_EXPOSURE_PCT    = 90.0   # flag if > 90% deployed
    MAX_SECTOR_PCT      = 30.0   # flag if any sector > 30%
    MAX_STRATEGY_PCT    = 30.0   # flag if any strategy bucket > 30%
    MIN_CASH_PCT        = 10.0   # flag if cash < 10%
    DD_WARNING_PCT      = 8.0    # warning at 8% drawdown
    DD_BREACH_PCT       = 12.0   # breach at 12% drawdown
    CONCENTRATION_WARN  = 0.4    # warn if HHI > 0.40

    def __init__(self, db: Session, total_capital: float = 100_000.0):
        self.db = db
        self.total_capital = total_capital

    def compute(self) -> PortfolioRiskSummary:
        from models import Trade, TradeStatus
        from capital_manager import CapitalManager, get_sector

        closed_trades = (
            self.db.query(Trade)
            .filter(Trade.status == TradeStatus.CLOSED)
            .order_by(Trade.exit_timestamp)
            .all()
        )
        open_trades = (
            self.db.query(Trade)
            .filter(Trade.status == TradeStatus.OPEN)
            .all()
        )

        # ── P&L stats ────────────────────────────────────────────────────────
        wins  = [t for t in closed_trades if (t.net_pnl or 0) > 0]
        losses= [t for t in closed_trades if (t.net_pnl or 0) <= 0]
        total_realized = sum((t.net_pnl or 0) for t in closed_trades)

        win_rate    = (len(wins) / len(closed_trades) * 100) if closed_trades else 0.0
        avg_win     = (sum((t.net_pnl or 0) for t in wins)   / len(wins))   if wins   else 0.0
        avg_loss    = (sum((t.net_pnl or 0) for t in losses)  / len(losses)) if losses else 0.0
        gross_profit= sum((t.net_pnl or 0) for t in wins)
        gross_loss  = abs(sum((t.net_pnl or 0) for t in losses))
        pf          = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        expectancy  = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)

        # ── Equity curve (daily, last 60 days) ───────────────────────────────
        equity_curve, drawdown_series, max_dd = self._build_equity_curve(
            closed_trades, self.total_capital
        )

        # ── Open exposure ────────────────────────────────────────────────────
        open_exposure = sum(
            (t.entry_price or 0) * (t.quantity or 0) for t in open_trades
        )
        exposure_pct  = (open_exposure / self.total_capital * 100) if self.total_capital else 0.0
        cash_avail    = max(0.0, self.total_capital - open_exposure)

        # ── Current equity ───────────────────────────────────────────────────
        current_equity = self.total_capital + total_realized
        peak_equity    = max(self.total_capital, current_equity)
        dd_now         = max(0.0, (peak_equity - current_equity) / peak_equity * 100) if peak_equity else 0.0

        # ── Strategy / sector breakdown ───────────────────────────────────────
        strategy_exp: Dict[str, float] = {b: 0.0 for b in CapitalManager.STRATEGY_CAPS}
        sector_exp: Dict[str, float] = {}
        open_pos_list = []

        for t in open_trades:
            from capital_manager import CapitalManager as CM
            product = CM._product_from_notes(t.notes or "")
            bucket  = CM._map_to_bucket(t.strategy_name or "", product)
            val     = (t.entry_price or 0) * (t.quantity or 0)
            strategy_exp[bucket] = strategy_exp.get(bucket, 0.0) + val

            sector = get_sector(t.symbol)
            sector_exp[sector] = sector_exp.get(sector, 0.0) + val

            open_pos_list.append({
                "id": t.id,
                "symbol": t.symbol,
                "strategy": t.strategy_name,
                "bucket": bucket,
                "sector": sector,
                "direction": t.direction.value if t.direction else "long",
                "quantity": t.quantity,
                "entry_price": round(t.entry_price or 0, 2),
                "market_value": round(val, 2),
                "exposure_pct": round(val / self.total_capital * 100, 2) if self.total_capital else 0.0,
                "stop_price": round(t.stop_price or 0, 2),
                "target_price": round(t.target_price or 0, 2) if t.target_price else None,
                "risk_amount": round(t.risk_amount or 0, 2),
            })

        # ── Concentration (HHI) ───────────────────────────────────────────────
        hhi, top_sym, top_pct = self._concentration(open_trades, open_exposure)

        # ── Compliance flags ──────────────────────────────────────────────────
        flags = self._check_compliance(
            exposure_pct=exposure_pct,
            cash_avail=cash_avail,
            strategy_exp=strategy_exp,
            sector_exp=sector_exp,
            dd_pct=dd_now,
            hhi=hhi,
        )

        return PortfolioRiskSummary(
            total_capital=self.total_capital,
            cash_available=cash_avail,
            total_exposure=open_exposure,
            exposure_pct=exposure_pct,
            peak_equity=peak_equity,
            current_equity=current_equity,
            drawdown_pct=dd_now,
            max_historical_drawdown_pct=max_dd,
            total_trades=len(closed_trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate_pct=win_rate,
            profit_factor=pf,
            avg_win=avg_win,
            avg_loss=avg_loss,
            expectancy=expectancy,
            total_realized_pnl=total_realized,
            herfindahl_index=hhi,
            top_concentration_symbol=top_sym,
            top_concentration_pct=top_pct,
            strategy_exposure=strategy_exp,
            sector_exposure=sector_exp,
            open_positions=open_pos_list,
            compliance_flags=flags,
            equity_curve=equity_curve,
            drawdown_series=drawdown_series,
            generated_at=datetime.utcnow(),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_equity_curve(self, closed_trades, initial_capital):
        """Build daily equity and drawdown series from closed trades."""
        if not closed_trades:
            return [], [], 0.0

        # Aggregate net_pnl by date
        daily_pnl: Dict[str, float] = {}
        for t in closed_trades:
            if not t.exit_timestamp:
                continue
            day = t.exit_timestamp.strftime("%Y-%m-%d")
            daily_pnl[day] = daily_pnl.get(day, 0.0) + (t.net_pnl or 0)

        # Sort dates
        sorted_dates = sorted(daily_pnl.keys())
        if not sorted_dates:
            return [], [], 0.0

        # Fill in date gaps (carry forward)
        start = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
        end   = datetime.strptime(sorted_dates[-1], "%Y-%m-%d")
        all_dates = []
        cur = start
        while cur <= end:
            all_dates.append(cur.strftime("%Y-%m-%d"))
            cur += timedelta(days=1)

        # Build curve
        equity_curve = []
        drawdown_series = []
        cumulative = initial_capital
        peak = initial_capital
        max_dd = 0.0

        for d in all_dates[-60:]:  # last 60 days only
            cumulative += daily_pnl.get(d, 0.0)
            peak = max(peak, cumulative)
            dd = max(0.0, (peak - cumulative) / peak * 100) if peak else 0.0
            max_dd = max(max_dd, dd)
            equity_curve.append({"date": d, "equity": round(cumulative, 2)})
            drawdown_series.append({"date": d, "drawdown_pct": round(dd, 2)})

        return equity_curve, drawdown_series, max_dd

    def _concentration(self, open_trades, total_exposure):
        """Calculate Herfindahl-Hirschman Index for position concentration."""
        if not open_trades or total_exposure <= 0:
            return 0.0, "", 0.0

        by_symbol: Dict[str, float] = {}
        for t in open_trades:
            val = (t.entry_price or 0) * (t.quantity or 0)
            by_symbol[t.symbol] = by_symbol.get(t.symbol, 0.0) + val

        shares = {s: v / total_exposure for s, v in by_symbol.items()}
        hhi = sum(s ** 2 for s in shares.values())

        top_sym = max(shares, key=shares.get) if shares else ""
        top_pct = shares.get(top_sym, 0.0) * 100

        return hhi, top_sym, top_pct

    def _check_compliance(
        self,
        exposure_pct: float,
        cash_avail: float,
        strategy_exp: Dict[str, float],
        sector_exp: Dict[str, float],
        dd_pct: float,
        hhi: float,
    ) -> List[ComplianceFlag]:
        flags = []

        # Cash reserve
        cash_pct = cash_avail / self.total_capital * 100 if self.total_capital else 100.0
        if cash_pct < self.MIN_CASH_PCT:
            flags.append(ComplianceFlag(
                rule="CASH_RESERVE",
                severity="BREACH",
                message=f"Cash {cash_pct:.1f}% below 10% minimum reserve (₹{cash_avail:,.0f} available)"
            ))

        # Drawdown
        if dd_pct >= self.DD_BREACH_PCT:
            flags.append(ComplianceFlag(
                rule="DRAWDOWN",
                severity="BREACH",
                message=f"Drawdown {dd_pct:.1f}% ≥ 12% — trading should be HALTED"
            ))
        elif dd_pct >= self.DD_WARNING_PCT:
            flags.append(ComplianceFlag(
                rule="DRAWDOWN",
                severity="WARNING",
                message=f"Drawdown {dd_pct:.1f}% ≥ 8% — risk halved, monitor closely"
            ))

        # Strategy caps
        for bucket, val in strategy_exp.items():
            from capital_manager import CapitalManager
            cap = CapitalManager.STRATEGY_CAPS.get(bucket, 30.0)
            pct = val / self.total_capital * 100 if self.total_capital else 0.0
            if pct > cap:
                flags.append(ComplianceFlag(
                    rule=f"STRATEGY_CAP_{bucket}",
                    severity="BREACH",
                    message=f"{bucket} exposure {pct:.1f}% exceeds {cap:.0f}% cap (₹{val:,.0f})"
                ))

        # Sector caps
        for sector, val in sector_exp.items():
            pct = val / self.total_capital * 100 if self.total_capital else 0.0
            if pct > self.MAX_SECTOR_PCT:
                flags.append(ComplianceFlag(
                    rule=f"SECTOR_CAP_{sector.upper()}",
                    severity="BREACH",
                    message=f"{sector} sector exposure {pct:.1f}% exceeds 30% cap (₹{val:,.0f})"
                ))

        # Concentration
        if hhi > self.CONCENTRATION_WARN:
            flags.append(ComplianceFlag(
                rule="CONCENTRATION",
                severity="WARNING",
                message=f"Portfolio concentration HHI={hhi:.3f} (>0.40 indicates high concentration)"
            ))

        return flags
