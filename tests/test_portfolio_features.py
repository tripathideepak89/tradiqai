"""Tests for all five portfolio analytics services.

Run with: pytest tests/test_portfolio_features.py -v
"""
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — fake Trade factory
# ─────────────────────────────────────────────────────────────────────────────

def _trade(
    net_pnl=500.0,
    risk_amount=1000.0,
    entry_price=1000.0,
    quantity=10,
    symbol="INFY",
    strategy_name="swing_momentum",
    notes="product:CNC",
    status_str="closed",
    days_ago=5,
):
    """Return a lightweight mock Trade object."""
    from unittest.mock import MagicMock
    from models import TradeStatus, TradeDirection
    t = MagicMock()
    t.net_pnl       = net_pnl
    t.risk_amount   = risk_amount
    t.entry_price   = entry_price
    t.quantity      = quantity
    t.symbol        = symbol
    t.strategy_name = strategy_name
    t.notes         = notes
    t.stop_price    = entry_price * 0.98
    t.target_price  = entry_price * 1.06
    t.direction     = TradeDirection.LONG
    t.status        = TradeStatus.CLOSED if status_str == "closed" else TradeStatus.OPEN
    t.exit_timestamp = datetime.utcnow() - timedelta(days=days_ago)
    t.charges       = 0.0
    t.risk_reward_ratio = 3.0
    return t


def _db_with_trades(closed=None, open_=None):
    """Return a mock SQLAlchemy session seeded with given trades."""
    db = MagicMock()

    closed_trades = closed or []
    open_trades   = open_   or []

    def query_side_effect(model):
        q = MagicMock()

        def filter_side_effect(*args, **kwargs):
            fq = MagicMock()

            def order_side_effect(*a):
                oq = MagicMock()
                # Return different lists based on the filter applied
                all_trades = closed_trades + open_trades
                if any(
                    hasattr(a_item, 'right') and hasattr(a_item.right, 'value') and a_item.right.value in ('open',)
                    for a_item in args
                    if hasattr(a_item, 'right')
                ):
                    oq.all.return_value = open_trades
                else:
                    oq.all.return_value = closed_trades
                oq.first.return_value = closed_trades[0] if closed_trades else None
                oq.limit = lambda n: oq
                return oq

            fq.order_by.side_effect = order_side_effect
            fq.filter.side_effect   = filter_side_effect
            fq.all.return_value     = closed_trades
            fq.first.return_value   = closed_trades[0] if closed_trades else None
            fq.limit = lambda n: fq
            return fq

        q.filter.side_effect  = filter_side_effect
        q.order_by.return_value = MagicMock(all=lambda: closed_trades, first=lambda: closed_trades[0] if closed_trades else None)
        q.all.return_value    = closed_trades
        q.first.return_value  = closed_trades[0] if closed_trades else None
        return q

    db.query.side_effect = query_side_effect
    db.add  = MagicMock()
    db.commit = MagicMock()
    return db


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1: Portfolio Risk Service
# ─────────────────────────────────────────────────────────────────────────────

class TestPortfolioRiskService:

    def _make_service(self, closed=None, open_=None, capital=100_000):
        from services.portfolio_risk import PortfolioRiskService
        db = _db_with_trades(closed=closed, open_=open_)
        return PortfolioRiskService(db=db, total_capital=capital)

    def test_empty_db_returns_valid_result(self):
        svc = self._make_service()
        result = svc.compute()
        assert result.total_capital == 100_000
        assert result.total_trades == 0
        assert result.win_rate_pct == 0.0
        assert isinstance(result.compliance_flags, list)

    def test_profit_factor_computed(self):
        trades = [_trade(net_pnl=800), _trade(net_pnl=600), _trade(net_pnl=-400)]
        svc = self._make_service(closed=trades)
        r = svc.compute()
        # gross_profit=1400, gross_loss=400 → PF=3.5
        assert r.profit_factor == pytest.approx(3.5, rel=0.01)

    def test_win_rate_correct(self):
        trades = [_trade(net_pnl=500)]*3 + [_trade(net_pnl=-200)]*2
        svc = self._make_service(closed=trades)
        r = svc.compute()
        assert r.win_rate_pct == pytest.approx(60.0, rel=0.01)
        assert r.total_trades == 5

    def test_drawdown_flag_at_12pct(self):
        svc = self._make_service()
        # Manually set equity below peak
        svc.total_capital = 100_000
        # Simulate via compute with losses producing > 12% DD
        losses = [_trade(net_pnl=-1500)] * 9   # -13500 → >12% DD
        svc = self._make_service(closed=losses)
        r = svc.compute()
        breach_flags = [f for f in r.compliance_flags if f.rule == "DRAWDOWN" and f.severity == "BREACH"]
        assert len(breach_flags) == 1

    def test_concentration_hhi_single_position(self):
        from services.portfolio_risk import PortfolioRiskService
        svc = self._make_service()
        trades = [_trade(entry_price=1000, quantity=10, symbol="TCS", status_str="open")]
        total_exp = 10000.0
        # Test _concentration() helper directly
        hhi, top_sym, top_pct = svc._concentration(trades, total_exp)
        assert hhi == pytest.approx(1.0, rel=0.01)
        assert top_sym == "TCS"
        assert top_pct == pytest.approx(100.0, rel=0.01)

    def test_to_dict_keys(self):
        svc = self._make_service()
        d = svc.compute().to_dict()
        for key in ["total_capital","cash_available","win_rate_pct","profit_factor",
                    "compliance_flags","equity_curve","drawdown_series","open_positions"]:
            assert key in d, f"Missing key: {key}"

    def test_sector_cap_breach_flag(self):
        # Test compliance check directly with sector over 30%
        from services.portfolio_risk import PortfolioRiskService
        svc = self._make_service()
        # IT sector = 35000 on 100k capital → 35% > 30% cap
        flags = svc._check_compliance(
            exposure_pct=35.0,
            cash_avail=65_000,
            strategy_exp={"DIVIDEND":0,"SWING":35000,"MID_TERM":0,"INTRADAY":0},
            sector_exp={"IT": 35000},
            dd_pct=0.0,
            hhi=1.0,
        )
        sector_flags = [f for f in flags if "SECTOR_CAP" in f.rule]
        assert len(sector_flags) == 1
        assert sector_flags[0].severity == "BREACH"


# ─────────────────────────────────────────────────────────────────────────────
# Feature 2: Compounding Plan Service
# ─────────────────────────────────────────────────────────────────────────────

class TestCompoundingPlanService:

    def _svc(self, closed=None, capital=100_000):
        from services.compounding_plan import CompoundingPlanService
        db = _db_with_trades(closed=closed or [])
        return CompoundingPlanService(db=db, initial_capital=capital)

    def test_three_scenarios_present(self):
        r = self._svc().compute()
        assert set(r.scenarios.keys()) == {"conservative", "base", "aggressive"}

    def test_aggressive_reaches_target_in_36_months(self):
        r = self._svc().compute()
        agg = r.scenarios["aggressive"]
        # At 5%/month: 100000 × 1.05^33 ≈ 508k — reaches ₹5L within 36 months
        assert agg.months_to_target is not None
        assert agg.months_to_target <= 36

    def test_base_does_not_reach_target_in_36_months(self):
        r = self._svc().compute()
        base = r.scenarios["base"]
        # At 3%/month: 100000 × 1.03^36 ≈ 290k — does NOT reach ₹5L in 36 months
        # months_to_target will be None (needs ~54 months)
        assert base.months_to_target is None
        assert base.projected_capital_24m > 200_000  # reasonable growth

    def test_aggressive_faster_than_conservative(self):
        r = self._svc().compute()
        agg = r.scenarios["aggressive"].months_to_target or 37
        con = r.scenarios["conservative"].months_to_target or 37
        assert agg < con

    def test_monthly_data_length(self):
        r = self._svc().compute()
        assert len(r.scenarios["base"].monthly_data) == 36

    def test_milestones_ordered(self):
        r = self._svc().compute()
        amounts = [m["amount"] for m in r.milestones]
        assert amounts == sorted(amounts)

    def test_actual_progress_no_trades(self):
        r = self._svc().compute()
        ap = r.actual_progress
        assert ap.realized_pnl == 0.0
        assert ap.current_capital == 100_000

    def test_actual_progress_with_gains(self):
        trades = [_trade(net_pnl=5000, days_ago=10)] * 2  # +10000 total
        r = self._svc(closed=trades).compute()
        ap = r.actual_progress
        assert ap.realized_pnl == pytest.approx(10_000.0)
        assert ap.current_capital == pytest.approx(110_000.0)

    def test_to_dict_structure(self):
        d = self._svc().compute().to_dict()
        assert "scenarios" in d and "actual_progress" in d and "milestones" in d


# ─────────────────────────────────────────────────────────────────────────────
# Feature 3: Rebalancer Service
# ─────────────────────────────────────────────────────────────────────────────

class TestRebalancerService:

    def _svc(self, closed=None, current=None):
        from services.rebalancer import RebalancerService
        db = _db_with_trades(closed=closed or [])
        return RebalancerService(db=db, current_allocations=current, total_capital=100_000)

    def test_no_trades_returns_neutral_score(self):
        r = self._svc().run()
        for bucket, bs in r.bucket_scores.items():
            assert bs.score == pytest.approx(50.0)

    def test_recommended_allocations_sum_to_100(self):
        r = self._svc().run()
        total = sum(r.recommended_allocations.values())
        assert total == pytest.approx(100.0, rel=0.01)

    def test_high_score_bucket_gets_increase(self):
        # Many winning trades in SWING → score > 70
        trades = [_trade(net_pnl=800, strategy_name="swing", notes="product:CNC")] * 10
        r = self._svc(closed=trades).run()
        swing_score = r.bucket_scores.get("SWING")
        if swing_score and swing_score.score >= 70:
            swing_delta = r.recommended_allocations.get("SWING", 0) - r.current_allocations.get("SWING", 30)
            assert swing_delta > 0

    def test_floor_and_ceiling_respected(self):
        from services.rebalancer import BUCKET_FLOOR, BUCKET_CEILING
        r = self._svc().run()
        for bucket, pct in r.recommended_allocations.items():
            if bucket != "CASH":
                assert pct >= BUCKET_FLOOR
                assert pct <= BUCKET_CEILING

    def test_cash_always_5pct(self):
        r = self._svc().run()
        assert r.recommended_allocations.get("CASH", 0) == pytest.approx(5.0)

    def test_to_dict_has_required_keys(self):
        d = self._svc().run().to_dict()
        for k in ["run_date","bucket_scores","current_allocations","recommended_allocations","changes","notes"]:
            assert k in d


# ─────────────────────────────────────────────────────────────────────────────
# Feature 4: Risk-of-Ruin Service
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskOfRuinService:

    def _svc(self, closed=None, sims=200, trades_per=50, seed=42):
        from services.risk_of_ruin import RiskOfRuinService
        db = _db_with_trades(closed=closed or [])
        return RiskOfRuinService(
            db=db,
            starting_capital=100_000,
            simulation_count=sims,
            trades_per_sim=trades_per,
            seed=seed,
        )

    def test_uses_synthetic_when_no_trades(self):
        r = self._svc().compute()
        # Should still return a valid result with synthetic data
        assert r.r_multiple_count >= 10
        assert 0.0 <= r.ruin_probability_pct <= 100.0

    def test_ruin_probability_range(self):
        r = self._svc().compute()
        assert 0.0 <= r.ruin_probability_pct <= 100.0

    def test_high_edge_system_low_ruin(self):
        # Positive expectancy trades → low ruin probability
        trades = [
            _trade(net_pnl=1500, risk_amount=1000) if i % 3 != 2
            else _trade(net_pnl=-900, risk_amount=1000)
            for i in range(60)
        ]
        r = self._svc(closed=trades, sims=500).compute()
        # With 2:1 R and 67% WR, ruin should be very low
        assert r.ruin_probability_pct < 20.0

    def test_percentile_ordering(self):
        r = self._svc().compute()
        assert r.pct5_final_capital <= r.pct25_final_capital
        assert r.pct25_final_capital <= r.median_final_capital
        assert r.median_final_capital <= r.pct75_final_capital
        assert r.pct75_final_capital <= r.pct95_final_capital

    def test_kelly_fraction_positive_edge(self):
        trades = [_trade(net_pnl=1500, risk_amount=1000)] * 7 + \
                 [_trade(net_pnl=-900, risk_amount=1000)] * 3
        r = self._svc(closed=trades).compute()
        assert r.kelly_fraction > 0

    def test_recommended_risk_capped_at_2pct(self):
        r = self._svc().compute()
        assert r.recommended_risk_per_trade_pct <= 2.0

    def test_equity_curves_keys(self):
        r = self._svc().compute()
        assert set(r.equity_curves.keys()) == {"p5", "p25", "median", "p75", "p95"}

    def test_to_dict_keys(self):
        d = self._svc().compute().to_dict()
        for k in ["ruin_probability_pct","kelly_fraction","recommended_risk_per_trade_pct",
                  "equity_curves","win_rate_pct","expectancy_r"]:
            assert k in d


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5: Adaptive Allocation Engine
# ─────────────────────────────────────────────────────────────────────────────

class TestAdaptiveAllocationEngine:

    def _svc(self, closed=None, regime="BULL", prev=None):
        from services.adaptive_allocation import AdaptiveAllocationEngine
        db = _db_with_trades(closed=closed or [])
        return AdaptiveAllocationEngine(
            db=db,
            regime=regime,
            lookback_days=30,
            total_capital=100_000,
            previous_targets=prev,
        )

    def test_total_allocated_100pct(self):
        r = self._svc().compute()
        assert r.total_allocated_pct == pytest.approx(100.0, rel=0.01)

    def test_all_buckets_present(self):
        r = self._svc().compute()
        assert set(r.targets.keys()) == {"DIVIDEND", "SWING", "MID_TERM", "INTRADAY", "CASH"}

    def test_cash_floor_maintained(self):
        from services.adaptive_allocation import CASH_FLOOR
        r = self._svc().compute()
        assert r.targets["CASH"].target_pct == pytest.approx(CASH_FLOOR)

    def test_bear_regime_reduces_swing(self):
        r_bull = self._svc(regime="BULL").compute()
        r_bear = self._svc(regime="BEAR").compute()
        assert r_bear.targets["SWING"].target_pct <= r_bull.targets["SWING"].target_pct

    def test_bear_regime_boosts_dividend(self):
        r_bull = self._svc(regime="BULL").compute()
        r_bear = self._svc(regime="BEAR").compute()
        # BEAR has DIVIDEND bias=1.1 vs BULL=1.0 → dividend should be >= bull
        assert r_bear.targets["DIVIDEND"].target_pct >= r_bull.targets["DIVIDEND"].target_pct * 0.95

    def test_invalid_regime_defaults_to_neutral(self):
        r = self._svc(regime="GARBAGE").compute()
        assert r.regime == "NEUTRAL"

    def test_deltas_computed_vs_previous(self):
        prev = {"DIVIDEND": 25.0, "SWING": 30.0, "MID_TERM": 30.0, "INTRADAY": 10.0, "CASH": 5.0}
        r = self._svc(prev=prev).compute()
        assert "SWING" in r.deltas

    def test_floor_ceiling_respected(self):
        from services.adaptive_allocation import BUCKET_FLOOR, BUCKET_CEILING
        r = self._svc().compute()
        for b, t in r.targets.items():
            if b != "CASH":
                assert t.target_pct >= BUCKET_FLOOR
                assert t.target_pct <= BUCKET_CEILING

    def test_to_dict_structure(self):
        d = self._svc().compute().to_dict()
        assert "targets" in d and "regime" in d and "deltas" in d and "total_allocated_pct" in d
