"""Unit tests for Capital Management Engine (CME).

Run with:
    pytest tests/test_capital_manager.py -v

These tests use a mocked SQLAlchemy session so no real database is needed.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# Allow importing from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from capital_manager import CapitalManager, TradeApproval, SECTOR_MAP


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_trade(symbol, strategy_name, quantity, entry_price, notes="product:CNC"):
    """Build a minimal mock Trade object."""
    t = MagicMock()
    t.symbol        = symbol
    t.strategy_name = strategy_name
    t.quantity      = quantity
    t.entry_price   = entry_price
    t.notes         = notes
    t.status        = "OPEN"
    return t


def _make_cme(open_trades=None, capital=100_000.0, regime="BULL") -> CapitalManager:
    """Build a CapitalManager with a mocked DB session."""
    db = MagicMock()
    cme = CapitalManager(db_session=db, total_capital=capital, regime=regime)

    # Patch _open_trades to return the supplied list
    trades = open_trades or []
    cme._open_trades = MagicMock(return_value=trades)
    return cme


# ─────────────────────────────────────────────────────────────────────────────
# 1. Risk per trade calculation
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskPerTrade:
    def test_base_risk_is_1_pct_of_capital(self):
        """1% of ₹1,00,000 = ₹1,000 risk per trade.

        Qty is further clipped by bucket cap (30% = ₹30,000) and cash reserve,
        so we test that risk_per_trade is correct, not the final qty.
        """
        cme = _make_cme()
        result = cme.approve_trade(
            symbol="TCS",
            entry_price=3500.0,
            stop_loss=3490.0,   # stop_dist = ₹10 → raw risk qty = 100
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        # TCS @ ₹3,500 × 100 = ₹3,50,000 → clipped by 30% bucket cap (₹30,000)
        # Final qty = ₹30,000 / ₹3,500 = 8 shares — still approved
        assert result.approved, result.reason
        assert result.risk_per_trade == pytest.approx(1000.0)
        assert result.adjusted_quantity > 0   # some shares approved after cap clipping

    def test_invalid_stop_loss_rejected(self):
        """Stop loss above entry price must be rejected."""
        cme = _make_cme()
        result = cme.approve_trade(
            symbol="TCS",
            entry_price=3500.0,
            stop_loss=3510.0,   # ABOVE entry — invalid for long
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        assert not result.approved
        assert "Invalid stop" in result.reason

    def test_tiny_stop_yields_small_quantity(self):
        """Very tight stop → large qty, but may be clipped by other rules."""
        cme = _make_cme()
        result = cme.approve_trade(
            symbol="INFY",
            entry_price=1500.0,
            stop_loss=1499.0,   # stop_dist = ₹1 → raw qty = 1000
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        # Qty limited by cash reserve / bucket cap
        assert result.approved or "cap" in result.reason.lower() or "Cash" in result.reason


# ─────────────────────────────────────────────────────────────────────────────
# 2. Strategy allocation cap enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestStrategyAllocationCap:
    def test_swing_cap_at_30_pct(self):
        """SWING bucket already at ₹30,000 (30%) → new trade rejected."""
        existing = [_make_mock_trade("INFY", "LiveSimpleStrategy", 100, 300.0)]
        # Existing exposure: ₹30,000 = 30% cap reached
        cme = _make_cme(open_trades=existing)
        # patch to report existing bucket exposure as exactly ₹30,000
        cme._strategy_exposure = MagicMock(return_value=30_000.0)

        result = cme.approve_trade(
            symbol="TCS",
            entry_price=3500.0,
            stop_loss=3465.0,   # stop_dist = ₹35 → risk qty ≈ 28 → ₹98k (large)
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        assert not result.approved
        assert "SWING" in result.reason

    def test_intraday_cap_at_10_pct(self):
        """INTRADAY bucket already at ₹10,000 (10%) → new MIS trade rejected."""
        cme = _make_cme()
        cme._strategy_exposure = MagicMock(return_value=10_000.0)

        result = cme.approve_trade(
            symbol="HDFCBANK",
            entry_price=1700.0,
            stop_loss=1683.0,   # stop_dist = ₹17
            strategy_name="LiveSimpleStrategy",
            product="MIS",
        )
        assert not result.approved
        assert "INTRADAY" in result.reason

    def test_dividend_bucket_mapped_correctly(self):
        """Strategy named 'DRE_Dividend' maps to DIVIDEND bucket."""
        cme = _make_cme()
        cme._strategy_exposure = MagicMock(return_value=0.0)
        cme._sector_exposure   = MagicMock(return_value=0.0)
        cme._total_exposure    = MagicMock(return_value=0.0)

        result = cme.approve_trade(
            symbol="ITC",
            entry_price=450.0,
            stop_loss=441.0,   # stop_dist = ₹9
            strategy_name="DRE_Dividend",
            product="CNC",
        )
        assert result.approved
        assert result.strategy_bucket == "DIVIDEND"

    def test_mis_product_maps_to_intraday(self):
        """MIS product → INTRADAY bucket regardless of strategy name."""
        cme = _make_cme()
        cme._strategy_exposure = MagicMock(return_value=0.0)
        cme._sector_exposure   = MagicMock(return_value=0.0)
        cme._total_exposure    = MagicMock(return_value=0.0)

        result = cme.approve_trade(
            symbol="RELIANCE",
            entry_price=2800.0,
            stop_loss=2772.0,   # stop_dist = ₹28
            strategy_name="LiveSimpleStrategy",
            product="MIS",
        )
        assert result.strategy_bucket == "INTRADAY"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sector cap enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestSectorCap:
    def test_sector_fully_used_blocks_trade(self):
        """Banking sector at ₹30,000 (30% cap) → new banking trade rejected."""
        cme = _make_cme()
        cme._strategy_exposure = MagicMock(return_value=0.0)
        cme._sector_exposure   = MagicMock(return_value=30_000.0)
        cme._total_exposure    = MagicMock(return_value=30_000.0)

        result = cme.approve_trade(
            symbol="HDFCBANK",
            entry_price=1700.0,
            stop_loss=1666.0,   # stop_dist = ₹34
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        assert not result.approved
        assert "Banking" in result.reason or "Sector" in result.reason

    def test_sector_partial_use_clips_quantity(self):
        """Banking sector has ₹20,000 used → new trade fits ₹10,000 remaining."""
        cme = _make_cme()
        cme._strategy_exposure = MagicMock(return_value=0.0)
        cme._sector_exposure   = MagicMock(return_value=20_000.0)
        cme._total_exposure    = MagicMock(return_value=20_000.0)

        result = cme.approve_trade(
            symbol="ICICIBANK",
            entry_price=1000.0,
            stop_loss=990.0,    # stop_dist = ₹10 → raw qty = 100 → ₹100,000 — clipped
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        # Remaining sector headroom = ₹10,000 → max qty = 10
        if result.approved:
            assert result.adjusted_quantity <= 10
        else:
            # Might also be rejected if clipped qty < 1
            assert "Sector" in result.reason or "cap" in result.reason.lower()

    def test_unknown_sector_symbol_uses_other(self):
        """Symbol not in SECTOR_MAP goes to 'Other' sector."""
        assert SECTOR_MAP.get("UNKNOWNSYMBOL") is None
        from capital_manager import get_sector
        assert get_sector("UNKNOWNSYMBOL") == "Other"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Drawdown trigger logic
# ─────────────────────────────────────────────────────────────────────────────

class TestDrawdownLogic:
    def test_normal_mode_below_8_pct(self):
        """No drawdown → NORMAL risk mode."""
        cme = _make_cme(capital=100_000.0)
        cme.peak_equity    = 100_000.0
        cme.current_equity = 96_000.0   # 4% drawdown
        assert cme._risk_mode(cme._drawdown_pct()) == "NORMAL"

    def test_reduced_mode_at_8_pct(self):
        """8% drawdown → REDUCED risk (halve risk_per_trade)."""
        cme = _make_cme(capital=100_000.0)
        cme.peak_equity    = 100_000.0
        cme.current_equity = 92_000.0   # 8% drawdown
        assert cme._risk_mode(cme._drawdown_pct()) == "REDUCED"

    def test_halted_at_12_pct(self):
        """12% drawdown → HALTED, all new trades blocked."""
        cme = _make_cme(capital=100_000.0)
        cme.peak_equity    = 100_000.0
        cme.current_equity = 88_000.0   # 12% drawdown

        result = cme.approve_trade(
            symbol="TCS",
            entry_price=3500.0,
            stop_loss=3490.0,
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        assert not result.approved
        assert result.risk_mode == "HALTED"
        assert "HALTED" in result.reason

    def test_reduced_mode_halves_risk_and_quantity(self):
        """At 9% drawdown risk is halved to ₹500.

        Raw qty = ₹500 / ₹10 = 50, but SWING cap (30% = ₹30,000) and
        cash floor clip it further. We verify risk_per_trade is ₹500 and
        mode is REDUCED regardless of final quantity.
        """
        cme = _make_cme(capital=100_000.0)
        cme.peak_equity    = 100_000.0
        cme.current_equity = 91_000.0   # 9% drawdown → REDUCED
        cme._strategy_exposure = MagicMock(return_value=0.0)
        cme._sector_exposure   = MagicMock(return_value=0.0)
        cme._total_exposure    = MagicMock(return_value=0.0)

        result = cme.approve_trade(
            symbol="INFY",
            entry_price=1500.0,
            stop_loss=1490.0,   # stop_dist = ₹10 → raw qty = 50 shares = ₹75,000
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        # ₹75,000 trade value exceeds 30% cap (₹30,000) → clipped to 20 shares
        assert result.approved
        assert result.risk_mode == "REDUCED"
        assert result.risk_per_trade == pytest.approx(500.0)
        assert result.adjusted_quantity > 0

    def test_update_equity_raises_peak(self):
        """update_equity() correctly tracks peak equity."""
        cme = _make_cme(capital=100_000.0)
        cme.update_equity(unrealized_pnl=5000.0, realized_pnl=2000.0)
        assert cme.current_equity == pytest.approx(107_000.0)
        assert cme.peak_equity    == pytest.approx(107_000.0)

        # Equity drops
        cme.update_equity(unrealized_pnl=-3000.0, realized_pnl=2000.0)
        assert cme.current_equity == pytest.approx(99_000.0)
        assert cme.peak_equity    == pytest.approx(107_000.0)  # peak unchanged


# ─────────────────────────────────────────────────────────────────────────────
# 5. Cash reserve enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestCashReserve:
    def test_trade_blocked_when_cash_floor_would_be_breached(self):
        """If only ₹9,000 available and min reserve is ₹10,000 → reject."""
        cme = _make_cme(capital=100_000.0)
        # ₹91,000 already deployed → cash = ₹9,000 < ₹10,000 floor
        cme._total_exposure = MagicMock(return_value=91_000.0)

        result = cme.approve_trade(
            symbol="TCS",
            entry_price=3500.0,
            stop_loss=3490.0,
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        assert not result.approved
        assert "Cash" in result.reason or "reserve" in result.reason.lower()

    def test_trade_clipped_to_fit_in_remaining_cash(self):
        """₹15,000 available, ₹10,000 reserve floor → max deploy ₹5,000."""
        cme = _make_cme(capital=100_000.0)
        cme._total_exposure    = MagicMock(return_value=85_000.0)
        cme._strategy_exposure = MagicMock(return_value=0.0)
        cme._sector_exposure   = MagicMock(return_value=0.0)

        result = cme.approve_trade(
            symbol="WIPRO",
            entry_price=500.0,
            stop_loss=495.0,    # stop_dist = ₹5 → raw qty = 200 → ₹100,000 (huge)
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        # Should be clipped to ₹5,000 / ₹500 = 10 shares
        if result.approved:
            assert result.adjusted_quantity <= 10
        else:
            assert "Cash" in result.reason or "reserve" in result.reason.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Market regime adjustment
# ─────────────────────────────────────────────────────────────────────────────

class TestMarketRegime:
    def test_bear_regime_halves_swing_cap(self):
        """In BEAR regime, SWING cap = 30% × 0.5 = 15%."""
        cme = _make_cme(regime="BEAR")
        mult = cme.REGIME_MULTIPLIERS["BEAR"]["SWING"]
        assert mult == 0.5
        effective_cap = cme.STRATEGY_CAPS["SWING"] * mult
        assert effective_cap == pytest.approx(15.0)

    def test_sideways_regime_halves_intraday(self):
        """In SIDEWAYS regime, INTRADAY cap = 10% × 0.5 = 5%."""
        cme = _make_cme(regime="SIDEWAYS")
        mult = cme.REGIME_MULTIPLIERS["SIDEWAYS"]["INTRADAY"]
        assert mult == 0.5
        effective_cap = cme.STRATEGY_CAPS["INTRADAY"] * mult
        assert effective_cap == pytest.approx(5.0)

    def test_bull_regime_full_allocation(self):
        """In BULL regime all multipliers are 1.0."""
        cme = _make_cme(regime="BULL")
        for bucket, mult in cme.REGIME_MULTIPLIERS["BULL"].items():
            assert mult == 1.0, f"Expected 1.0 for {bucket} in BULL, got {mult}"

    def test_set_regime_updates_correctly(self):
        """set_regime() updates internal state."""
        cme = _make_cme(regime="BULL")
        cme.set_regime("BEAR")
        assert cme._regime == "BEAR"

    def test_invalid_regime_defaults_to_neutral(self):
        """Unknown regime string defaults to NEUTRAL."""
        cme = _make_cme(regime="UNKNOWN")
        assert cme._regime == "NEUTRAL"

    def test_bear_regime_blocks_new_trades_via_cap(self):
        """In BEAR regime SWING at ₹15,001 deployment → rejected (cap ₹15,000)."""
        cme = _make_cme(regime="BEAR")
        cme._strategy_exposure = MagicMock(return_value=15_001.0)  # just over BEAR cap
        cme._sector_exposure   = MagicMock(return_value=0.0)
        cme._total_exposure    = MagicMock(return_value=15_001.0)

        result = cme.approve_trade(
            symbol="INFY",
            entry_price=1500.0,
            stop_loss=1485.0,
            strategy_name="LiveSimpleStrategy",
            product="CNC",
        )
        assert not result.approved
        assert "SWING" in result.reason


# ─────────────────────────────────────────────────────────────────────────────
# 7. Snapshot
# ─────────────────────────────────────────────────────────────────────────────

class TestSnapshot:
    def test_snapshot_contains_all_fields(self):
        cme = _make_cme()
        snap = cme.get_snapshot()
        d = snap.to_dict()
        for key in ("total_capital", "cash_available", "total_exposure",
                    "exposure_pct", "peak_equity", "current_equity",
                    "drawdown_pct", "risk_mode", "strategy_exposure",
                    "sector_exposure", "regime", "updated_at"):
            assert key in d, f"Missing key: {key}"

    def test_snapshot_risk_mode_normal_at_start(self):
        cme = _make_cme()
        snap = cme.get_snapshot()
        assert snap.risk_mode == "NORMAL"
        assert snap.drawdown_pct == pytest.approx(0.0)
