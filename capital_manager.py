"""Capital Management Engine (CME)
===================================

Portfolio-level capital allocator for ₹1,00,000 capital.

Rules enforced:
  1. Max 1% risk per trade  (₹1,000 on ₹1L capital)
  2. Max 30% allocation per strategy bucket
  3. Max 30% per-sector exposure
  4. Min 10% cash reserve always maintained
  5. Drawdown >= 8%  → reduce risk per trade by 50%
  6. Drawdown >= 12% → block all new trades
  7. Market regime (50DMA / 200DMA) adjusts bucket allocation multipliers

CME acts as a gatekeeper BEFORE RiskEngine and broker interaction.
Call  capital_manager.approve_trade(...)  from OrderManager.execute_signal().
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Sector Map
# ─────────────────────────────────────────────────────────────────────────────
# Maps NSE symbols → sector names for sector-exposure enforcement.
# Add symbols here as the watchlist grows.

SECTOR_MAP: Dict[str, str] = {
    # Banking & Finance
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "KOTAKBANK": "Banking",
    "AXISBANK": "Banking", "SBIN": "Banking", "BAJFINANCE": "Banking",
    "BAJAJFINSV": "Banking", "HDFCLIFE": "Banking", "SBILIFE": "Banking",
    "INDUSINDBK": "Banking", "BANDHANBNK": "Banking", "FEDERALBNK": "Banking",
    "IDFCFIRSTB": "Banking", "PNB": "Banking", "CANBK": "Banking",
    "LICI": "Banking",
    # Information Technology
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT",
    "TECHM": "IT", "LTIM": "IT", "PERSISTENT": "IT", "COFORGE": "IT",
    # Automobiles
    "MARUTI": "Auto", "M&M": "Auto", "TATAMOTORS": "Auto",
    "BAJAJ-AUTO": "Auto", "EICHERMOT": "Auto", "HEROMOTOCO": "Auto",
    "TVSMOTOR": "Auto", "ASHOKLEY": "Auto",
    # Metals & Mining
    "TATASTEEL": "Metals", "HINDALCO": "Metals", "JSWSTEEL": "Metals",
    "VEDL": "Metals", "NATIONALUM": "Metals", "HINDZINC": "Metals",
    # Pharmaceuticals
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
    "DIVISLAB": "Pharma", "AUROPHARMA": "Pharma", "TORNTPHARM": "Pharma",
    # FMCG & Consumer Staples
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG",
    "BRITANNIA": "FMCG", "DABUR": "FMCG", "MARICO": "FMCG",
    "GODREJCP": "FMCG", "TATACONSUM": "FMCG",
    # Energy & Oil
    "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy",
    "IOC": "Energy", "GAIL": "Energy", "ADANIGREEN": "Energy",
    "COALINDIA": "Energy", "HINDPETRO": "Energy",
    # Cement & Construction
    "ULTRACEMCO": "Cement", "LT": "Cement", "GRASIM": "Cement",
    "AMBUJACEM": "Cement", "ACC": "Cement", "SIEMENS": "Cement",
    # Telecom
    "BHARTIARTL": "Telecom",
    # Services & Consumer Discretionary
    "INDIGO": "Services", "ZOMATO": "Services",
    "NYKAA": "Services", "DMART": "Services",
    # Infrastructure & Power
    "ADANIPORTS": "Infrastructure", "ADANIENT": "Infrastructure",
    "NTPC": "Power", "POWERGRID": "Power",
    # Consumer Goods
    "TITAN": "Consumer", "ASIANPAINT": "Consumer",
    "PIDILITIND": "Consumer", "BERGEPAINT": "Consumer",
    "HAVELLS": "Consumer", "VOLTAS": "Consumer",
}


def get_sector(symbol: str) -> str:
    """Return sector for a symbol, defaulting to 'Other'."""
    return SECTOR_MAP.get(symbol, "Other")


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TradeApproval:
    """Result returned by CapitalManager.approve_trade()."""
    approved: bool
    reason: str
    adjusted_quantity: int = 0       # CME-sized qty (use this instead of signal.quantity)
    risk_per_trade: float = 0.0      # Rupee risk used for sizing
    risk_mode: str = "NORMAL"        # NORMAL | REDUCED | HALTED
    strategy_bucket: str = "SWING"
    sector: str = "Other"


@dataclass
class PortfolioSnapshot:
    """Lightweight portfolio state for dashboard and logging."""
    total_capital: float
    cash_available: float
    total_exposure: float
    exposure_pct: float
    peak_equity: float
    current_equity: float
    drawdown_pct: float
    risk_mode: str
    strategy_exposure: Dict[str, float]  # bucket  → ₹ deployed
    sector_exposure: Dict[str, float]    # sector  → ₹ deployed
    regime: str
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "total_capital": round(self.total_capital, 2),
            "cash_available": round(self.cash_available, 2),
            "total_exposure": round(self.total_exposure, 2),
            "exposure_pct": round(self.exposure_pct, 2),
            "peak_equity": round(self.peak_equity, 2),
            "current_equity": round(self.current_equity, 2),
            "drawdown_pct": round(self.drawdown_pct, 2),
            "risk_mode": self.risk_mode,
            "strategy_exposure": {k: round(v, 2) for k, v in self.strategy_exposure.items()},
            "sector_exposure": {k: round(v, 2) for k, v in self.sector_exposure.items()},
            "regime": self.regime,
            "updated_at": self.updated_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Capital Management Engine
# ─────────────────────────────────────────────────────────────────────────────

class CapitalManager:
    """Capital Management Engine — portfolio-level trade gatekeeper.

    Sits above RiskEngine.  Call approve_trade() from OrderManager.execute_signal()
    BEFORE the existing risk-engine check.

    Args:
        db_session     : SQLAlchemy session (read-only; queries open trades).
        total_capital  : Total portfolio capital (default ₹1,00,000).
        regime         : Initial market regime string (BULL/BEAR/SIDEWAYS/NEUTRAL).
    """

    # ── Core rule parameters ──────────────────────────────────────────────────
    RISK_PER_TRADE_PCT  = 1.0    # 1% of capital per trade  → ₹1,000
    CASH_RESERVE_PCT    = 10.0   # Minimum cash floor        → ₹10,000
    SECTOR_CAP_PCT      = 30.0   # Max single-sector exposure → ₹30,000
    DRAWDOWN_REDUCE_PCT = 8.0    # Drawdown ≥ 8%  → halve risk
    DRAWDOWN_BLOCK_PCT  = 12.0   # Drawdown ≥ 12% → block new trades

    # ── Strategy bucket caps (% of total capital) ─────────────────────────────
    STRATEGY_CAPS: Dict[str, float] = {
        "DIVIDEND": 30.0,   # max ₹30,000 in dividend plays
        "SWING":    30.0,   # max ₹30,000 in 3-day swing
        "MID_TERM": 30.0,   # max ₹30,000 in medium-term
        "INTRADAY": 10.0,   # max ₹10,000 intraday (MIS)
    }

    # ── Regime multipliers: applied to STRATEGY_CAPS per regime ───────────────
    # BEAR  → all buckets get 50% of their normal cap
    # SIDEWAYS → intraday gets 50%, others full cap
    # NEUTRAL  → intraday 25%, swing/mid 75%
    REGIME_MULTIPLIERS: Dict[str, Dict[str, float]] = {
        "BULL":     {"DIVIDEND": 1.0, "SWING": 1.0, "MID_TERM": 1.0, "INTRADAY": 1.0},
        "BEAR":     {"DIVIDEND": 0.5, "SWING": 0.5, "MID_TERM": 0.5, "INTRADAY": 0.5},
        "SIDEWAYS": {"DIVIDEND": 1.0, "SWING": 1.0, "MID_TERM": 1.0, "INTRADAY": 0.5},
        "NEUTRAL":  {"DIVIDEND": 1.0, "SWING": 0.75, "MID_TERM": 0.75, "INTRADAY": 0.25},
    }

    def __init__(
        self,
        db_session: Session,
        total_capital: float = 100_000.0,
        regime: str = "BULL",
    ) -> None:
        self.db = db_session
        self.total_capital  = total_capital
        self.peak_equity    = total_capital
        self.current_equity = total_capital
        self._regime        = regime if regime in self.REGIME_MULTIPLIERS else "NEUTRAL"
        self._realized_pnl  = 0.0

        logger.info(
            f"[CME] Capital Management Engine initialized — "
            f"capital=₹{total_capital:,.0f}, regime={self._regime}"
        )
        self._log_limits()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_regime(self, regime: str) -> None:
        """Update market regime (BULL / BEAR / SIDEWAYS / NEUTRAL)."""
        prev = self._regime
        self._regime = regime if regime in self.REGIME_MULTIPLIERS else "NEUTRAL"
        if prev != self._regime:
            logger.info(f"[CME] Regime updated: {prev} → {self._regime}")

    def update_equity(self, unrealized_pnl: float = 0.0, realized_pnl: float = 0.0) -> None:
        """Refresh current equity and peak for drawdown calculation.

        Call this on every WebSocket tick with fresh P&L values.
        """
        self._realized_pnl  = realized_pnl
        self.current_equity = self.total_capital + realized_pnl + unrealized_pnl
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

    def approve_trade(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        strategy_name: str,
        product: str = "CNC",       # "MIS" or "CNC"
        proposed_quantity: int = 0,  # strategy's own size (informational only)
    ) -> TradeApproval:
        """Gate check before order placement.

        Returns TradeApproval.  If approved:
            - use  adjusted_quantity  (CME-sized, may differ from signal.quantity)
            - log  risk_mode          (NORMAL / REDUCED / HALTED)

        The caller (OrderManager) should override signal.quantity with
        approval.adjusted_quantity before sending to the broker.
        """
        sector  = get_sector(symbol)
        bucket  = self._map_to_bucket(strategy_name, product)
        dd_pct  = self._drawdown_pct()
        mode    = self._risk_mode(dd_pct)

        # ── Rule 6: Drawdown block ──────────────────────────────────────────
        if mode == "HALTED":
            return TradeApproval(
                approved=False,
                reason=(
                    f"CME: Trading HALTED — portfolio drawdown {dd_pct:.1f}% "
                    f">= {self.DRAWDOWN_BLOCK_PCT}% threshold"
                ),
                risk_mode="HALTED",
                strategy_bucket=bucket,
                sector=sector,
            )

        # ── Rule 1: Compute risk amount & position size ─────────────────────
        base_risk = self.total_capital * self.RISK_PER_TRADE_PCT / 100.0  # ₹1,000
        if mode == "REDUCED":
            base_risk *= 0.5   # ₹500 when drawdown 8–12%
            logger.info(f"[CME] Risk REDUCED to ₹{base_risk:.0f} (drawdown {dd_pct:.1f}%)")

        stop_dist = entry_price - stop_loss
        if stop_dist <= 0:
            return TradeApproval(
                approved=False,
                reason=(
                    f"CME: Invalid stop loss — stop ₹{stop_loss:.2f} must be "
                    f"strictly below entry ₹{entry_price:.2f}"
                ),
                risk_mode=mode,
                strategy_bucket=bucket,
                sector=sector,
            )

        qty        = int(base_risk / stop_dist)
        trade_val  = qty * entry_price

        if qty < 1:
            return TradeApproval(
                approved=False,
                reason=(
                    f"CME: Position too small — ₹{base_risk:.0f} risk / "
                    f"₹{stop_dist:.2f} stop = {base_risk / stop_dist:.2f} shares (< 1)"
                ),
                risk_mode=mode,
                strategy_bucket=bucket,
                sector=sector,
            )

        # ── Rule 4: Cash reserve ────────────────────────────────────────────
        open_exp   = self._total_exposure()
        cash_avail = max(0.0, self.total_capital - open_exp)
        min_cash   = self.total_capital * self.CASH_RESERVE_PCT / 100.0  # ₹10,000

        if cash_avail - trade_val < min_cash:
            max_deploy = cash_avail - min_cash
            if max_deploy <= 0:
                return TradeApproval(
                    approved=False,
                    reason=(
                        f"CME: Cash reserve floor hit — "
                        f"available ₹{cash_avail:,.0f}, "
                        f"reserve min ₹{min_cash:,.0f}"
                    ),
                    risk_mode=mode,
                    strategy_bucket=bucket,
                    sector=sector,
                )
            qty       = int(max_deploy / entry_price)
            trade_val = qty * entry_price
            if qty < 1:
                return TradeApproval(
                    approved=False,
                    reason=f"CME: Cash reserve floor clips position below 1 share",
                    risk_mode=mode,
                    strategy_bucket=bucket,
                    sector=sector,
                )

        # ── Rule 2: Strategy bucket cap (regime-adjusted) ──────────────────
        regime_m  = self.REGIME_MULTIPLIERS.get(self._regime, self.REGIME_MULTIPLIERS["NEUTRAL"])
        base_cap  = self.STRATEGY_CAPS.get(bucket, 30.0)
        eff_cap   = base_cap * regime_m.get(bucket, 1.0)
        cap_val   = self.total_capital * eff_cap / 100.0

        bucket_exp = self._strategy_exposure(bucket)
        if bucket_exp + trade_val > cap_val:
            allowed   = max(0.0, cap_val - bucket_exp)
            qty       = int(allowed / entry_price)
            trade_val = qty * entry_price
            if qty < 1:
                return TradeApproval(
                    approved=False,
                    reason=(
                        f"CME: Strategy bucket '{bucket}' cap {eff_cap:.0f}% "
                        f"(₹{cap_val:,.0f}) reached — "
                        f"currently ₹{bucket_exp:,.0f} deployed"
                    ),
                    risk_mode=mode,
                    strategy_bucket=bucket,
                    sector=sector,
                )

        # ── Rule 3: Sector cap ──────────────────────────────────────────────
        sec_cap_val  = self.total_capital * self.SECTOR_CAP_PCT / 100.0  # ₹30,000
        sec_exp      = self._sector_exposure(sector)
        if sec_exp + trade_val > sec_cap_val:
            allowed   = max(0.0, sec_cap_val - sec_exp)
            qty       = int(allowed / entry_price)
            trade_val = qty * entry_price
            if qty < 1:
                return TradeApproval(
                    approved=False,
                    reason=(
                        f"CME: Sector '{sector}' 30% cap "
                        f"(₹{sec_cap_val:,.0f}) reached — "
                        f"currently ₹{sec_exp:,.0f} deployed"
                    ),
                    risk_mode=mode,
                    strategy_bucket=bucket,
                    sector=sector,
                )

        # ── Approved ────────────────────────────────────────────────────────
        logger.info(
            f"[CME] {symbol} APPROVED — qty={qty}, val=₹{trade_val:,.0f}, "
            f"risk=₹{base_risk:.0f}, mode={mode}, bucket={bucket}, sector={sector}"
        )
        return TradeApproval(
            approved=True,
            reason=(
                f"CME approved — qty {qty}, risk ₹{base_risk:.0f}, "
                f"mode {mode}, bucket {bucket}, sector {sector}"
            ),
            adjusted_quantity=qty,
            risk_per_trade=base_risk,
            risk_mode=mode,
            strategy_bucket=bucket,
            sector=sector,
        )

    def get_snapshot(self) -> PortfolioSnapshot:
        """Return current portfolio state for dashboard / WebSocket payload."""
        open_exp   = self._total_exposure()
        cash_avail = max(0.0, self.total_capital - open_exp)
        dd_pct     = self._drawdown_pct()
        mode       = self._risk_mode(dd_pct)

        return PortfolioSnapshot(
            total_capital=self.total_capital,
            cash_available=cash_avail,
            total_exposure=open_exp,
            exposure_pct=(open_exp / self.total_capital * 100) if self.total_capital else 0.0,
            peak_equity=self.peak_equity,
            current_equity=self.current_equity,
            drawdown_pct=dd_pct,
            risk_mode=mode,
            strategy_exposure=self._all_strategy_exposures(),
            sector_exposure=self._all_sector_exposures(),
            regime=self._regime,
            updated_at=datetime.utcnow(),
        )

    def save_snapshot(self) -> None:
        """Persist current snapshot to portfolio_metrics table."""
        try:
            from models import PortfolioMetrics
            snap = self.get_snapshot()
            row = PortfolioMetrics(
                total_capital=snap.total_capital,
                cash_available=snap.cash_available,
                total_exposure=snap.total_exposure,
                peak_equity=snap.peak_equity,
                current_equity=snap.current_equity,
                drawdown_pct=snap.drawdown_pct,
                risk_mode=snap.risk_mode,
                strategy_exposure=json.dumps(snap.strategy_exposure),
                sector_exposure=json.dumps(snap.sector_exposure),
            )
            self.db.add(row)
            self.db.commit()
            logger.debug("[CME] Portfolio snapshot saved to DB")
        except Exception as e:
            logger.warning(f"[CME] Could not save portfolio snapshot: {e}")
            self.db.rollback()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _drawdown_pct(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - self.current_equity) / self.peak_equity * 100.0)

    def _risk_mode(self, drawdown_pct: float) -> str:
        if drawdown_pct >= self.DRAWDOWN_BLOCK_PCT:
            return "HALTED"
        if drawdown_pct >= self.DRAWDOWN_REDUCE_PCT:
            return "REDUCED"
        return "NORMAL"

    @staticmethod
    def _map_to_bucket(strategy_name: str, product: str) -> str:
        """Map a strategy_name + product type to a CME strategy bucket."""
        name_lo = (strategy_name or "").lower()
        if "dividend" in name_lo or "dre" in name_lo:
            return "DIVIDEND"
        if product == "MIS":
            return "INTRADAY"
        if "mid" in name_lo or "medium" in name_lo or "midterm" in name_lo:
            return "MID_TERM"
        # Default: 3-day swing (CNC)
        return "SWING"

    @staticmethod
    def _product_from_notes(notes: str) -> str:
        """Parse product type from trade notes field."""
        if notes and "product:MIS" in notes:
            return "MIS"
        return "CNC"

    def _open_trades(self) -> list:
        """Return all OPEN trades from local DB (read-only)."""
        try:
            from models import Trade, TradeStatus
            return (
                self.db.query(Trade)
                .filter(Trade.status == TradeStatus.OPEN)
                .all()
            )
        except Exception as e:
            logger.warning(f"[CME] Could not query open trades: {e}")
            return []

    def _total_exposure(self) -> float:
        """Sum of (entry_price × quantity) across all open trades."""
        return sum(
            (t.entry_price or 0.0) * (t.quantity or 0)
            for t in self._open_trades()
        )

    def _strategy_exposure(self, bucket: str) -> float:
        """Capital deployed in a specific strategy bucket."""
        total = 0.0
        for t in self._open_trades():
            product = self._product_from_notes(t.notes or "")
            if self._map_to_bucket(t.strategy_name or "", product) == bucket:
                total += (t.entry_price or 0.0) * (t.quantity or 0)
        return total

    def _sector_exposure(self, sector: str) -> float:
        """Capital deployed in a specific sector."""
        return sum(
            (t.entry_price or 0.0) * (t.quantity or 0)
            for t in self._open_trades()
            if get_sector(t.symbol) == sector
        )

    def _all_strategy_exposures(self) -> Dict[str, float]:
        result: Dict[str, float] = {b: 0.0 for b in self.STRATEGY_CAPS}
        for t in self._open_trades():
            product = self._product_from_notes(t.notes or "")
            bucket  = self._map_to_bucket(t.strategy_name or "", product)
            val     = (t.entry_price or 0.0) * (t.quantity or 0)
            result[bucket] = result.get(bucket, 0.0) + val
        return result

    def _all_sector_exposures(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for t in self._open_trades():
            sec = get_sector(t.symbol)
            val = (t.entry_price or 0.0) * (t.quantity or 0)
            result[sec] = result.get(sec, 0.0) + val
        return result

    def _log_limits(self) -> None:
        caps = {b: f"₹{self.total_capital * c / 100:,.0f} ({c}%)"
                for b, c in self.STRATEGY_CAPS.items()}
        logger.info(f"[CME] Strategy caps: {caps}")
        logger.info(
            f"[CME] Sector cap: ₹{self.total_capital * self.SECTOR_CAP_PCT / 100:,.0f} (30%)"
        )
        logger.info(
            f"[CME] Cash reserve: ₹{self.total_capital * self.CASH_RESERVE_PCT / 100:,.0f} (10%)"
        )
        logger.info(
            f"[CME] Risk per trade: ₹{self.total_capital * self.RISK_PER_TRADE_PCT / 100:,.0f} (1%)"
        )


logger.info("✅ Capital Management Engine module loaded")
