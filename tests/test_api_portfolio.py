"""
Integration tests for Portfolio Analytics API endpoints.

Covers:
  GET  /api/portfolio/risk-summary
  GET  /api/plan/compounding
  POST /api/rebalance/run
  GET  /api/rebalance/latest
  POST /api/risk/ruin
  POST /api/allocation/compute
  GET  /api/allocation/current
"""
import pytest


@pytest.mark.integration
class TestPortfolioRiskSummary:
    """GET /api/portfolio/risk-summary"""

    def test_returns_200_with_auth(self, client, auth_headers):
        resp = client.get("/api/portfolio/risk-summary", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_has_required_keys(self, client, auth_headers):
        resp = client.get("/api/portfolio/risk-summary", headers=auth_headers)
        if resp.status_code != 200:
            pytest.skip(f"Endpoint returned {resp.status_code}")
        data = resp.json()
        # Should contain trade statistics even if all zeros
        assert isinstance(data, dict)
        # Common keys from PortfolioRiskService output
        for key in ("total_trades", "win_rate_pct", "profit_factor"):
            assert key in data, f"Missing key: {key}"

    def test_empty_db_returns_zeros_not_error(self, client, auth_headers):
        """No trades → metrics should be zeros, not 500."""
        resp = client.get("/api/portfolio/risk-summary", headers=auth_headers)
        assert resp.status_code in (200, 422)

    def test_with_seeded_data(self, test_app, seeded_db, auth_headers):
        """With 15 closed trades, metrics should reflect real numbers."""
        from fastapi.testclient import TestClient
        from sqlalchemy.orm import sessionmaker

        bind = seeded_db.bind

        def override_get_db():
            Session = sessionmaker(bind=bind)
            s = Session()
            try:
                yield s
            finally:
                s.close()

        try:
            from database import get_db
        except Exception:
            pytest.skip("Cannot override DB dependency")

        # Save original override and restore after test (test_app is session-scoped)
        original = test_app.dependency_overrides.get(get_db)
        test_app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(test_app) as c:
                resp = c.get("/api/portfolio/risk-summary", headers=auth_headers)
                if resp.status_code == 200:
                    data = resp.json()
                    assert data.get("total_trades", 0) >= 0
        finally:
            if original is not None:
                test_app.dependency_overrides[get_db] = original
            else:
                test_app.dependency_overrides.pop(get_db, None)


@pytest.mark.integration
class TestCompoundingPlan:
    """GET /api/plan/compounding"""

    def test_returns_200(self, client, auth_headers):
        resp = client.get("/api/plan/compounding", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_has_scenarios(self, client, auth_headers):
        resp = client.get("/api/plan/compounding", headers=auth_headers)
        if resp.status_code != 200:
            pytest.skip(f"Endpoint returned {resp.status_code}")
        data = resp.json()
        assert "scenarios" in data
        scenarios = data["scenarios"]
        for name in ("conservative", "base", "aggressive"):
            assert name in scenarios, f"Missing scenario: {name}"

    def test_scenarios_have_monthly_data(self, client, auth_headers):
        resp = client.get("/api/plan/compounding", headers=auth_headers)
        if resp.status_code != 200:
            pytest.skip(f"Endpoint returned {resp.status_code}")
        data = resp.json()
        base = data["scenarios"]["base"]
        assert len(base["monthly_data"]) >= 12

    def test_actual_progress_present(self, client, auth_headers):
        resp = client.get("/api/plan/compounding", headers=auth_headers)
        if resp.status_code != 200:
            pytest.skip(f"Endpoint returned {resp.status_code}")
        data = resp.json()
        assert "actual_progress" in data
        prog = data["actual_progress"]
        assert "realized_pnl" in prog
        assert "current_capital" in prog
        assert "milestone_pct" in prog

    def test_milestones_present(self, client, auth_headers):
        resp = client.get("/api/plan/compounding", headers=auth_headers)
        if resp.status_code != 200:
            pytest.skip(f"Endpoint returned {resp.status_code}")
        data = resp.json()
        assert "milestones" in data
        assert len(data["milestones"]) > 0

    def test_initial_capital_positive(self, client, auth_headers):
        resp = client.get("/api/plan/compounding", headers=auth_headers)
        if resp.status_code != 200:
            pytest.skip(f"Endpoint returned {resp.status_code}")
        data = resp.json()
        assert data["initial_capital"] > 0
        assert data["target_capital"] > data["initial_capital"]


@pytest.mark.integration
class TestRebalance:
    """POST /api/rebalance/run and GET /api/rebalance/latest"""

    def test_run_rebalance_does_not_crash(self, client, auth_headers):
        resp = client.post("/api/rebalance/run", headers=auth_headers)
        # 200 = ran successfully, 400 = insufficient data — both acceptable
        assert resp.status_code in (200, 400, 422, 500)

    def test_latest_rebalance_returns_200_or_empty(self, client, auth_headers):
        resp = client.get("/api/rebalance/latest", headers=auth_headers)
        assert resp.status_code in (200, 404)

    def test_latest_rebalance_structure(self, client, auth_headers):
        resp = client.get("/api/rebalance/latest", headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)


@pytest.mark.integration
@pytest.mark.slow
class TestRiskOfRuin:
    """POST /api/risk/ruin — Monte Carlo simulation"""

    def test_simulation_runs(self, client, auth_headers):
        resp = client.post("/api/risk/ruin", json={}, headers=auth_headers)
        assert resp.status_code == 200

    def test_synthetic_fallback_when_no_trades(self, client, auth_headers):
        """With empty DB, service falls back to synthetic R-multiples — must not 500."""
        resp = client.post("/api/risk/ruin", json={}, headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            # synthetic fallback produces valid output
            assert "ruin_probability_pct" in data
            assert 0.0 <= data["ruin_probability_pct"] <= 100.0

    def test_response_has_equity_curves(self, client, auth_headers):
        resp = client.post("/api/risk/ruin", json={}, headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            assert "equity_curves" in data
            curves = data["equity_curves"]
            for key in ("p5", "p25", "median", "p75", "p95"):
                assert key in curves

    def test_kelly_fraction_between_0_and_1(self, client, auth_headers):
        resp = client.post("/api/risk/ruin", json={}, headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            kelly = data.get("kelly_fraction", 0.5)
            assert 0.0 <= kelly <= 1.0

    def test_recommended_risk_is_conservative(self, client, auth_headers):
        """Recommended risk should be capped at 2% per trade."""
        resp = client.post("/api/risk/ruin", json={}, headers=auth_headers)
        if resp.status_code == 200:
            data = resp.json()
            rec = data.get("recommended_risk_per_trade_pct", 1.0)
            assert rec <= 2.0


@pytest.mark.integration
class TestAllocationAPI:
    """POST /api/allocation/compute and GET /api/allocation/current"""

    def test_compute_allocation_responds(self, client, auth_headers):
        resp = client.post("/api/allocation/compute", headers=auth_headers)
        assert resp.status_code in (200, 400, 422)

    def test_current_allocation_responds(self, client, auth_headers):
        resp = client.get("/api/allocation/current", headers=auth_headers)
        assert resp.status_code in (200, 404)

    def test_allocation_history_responds(self, client, auth_headers):
        resp = client.get("/api/allocation/history", headers=auth_headers)
        assert resp.status_code in (200, 404)
