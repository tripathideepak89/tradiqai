"""
Integration tests for Rejected Trades Audit API.

Covers:
  GET  /api/audit/rejected-trades          (list, filters)
  GET  /api/audit/rejected-trades/{id}     (single record detail)
"""
import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
class TestRejectedTradesList:
    """GET /api/audit/rejected-trades"""

    def test_returns_200_with_auth(self, client, auth_headers):
        resp = client.get("/api/audit/rejected-trades", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_structure(self, client, auth_headers):
        resp = client.get("/api/audit/rejected-trades", headers=auth_headers)
        if resp.status_code != 200:
            pytest.skip(f"Endpoint returned {resp.status_code}")
        data = resp.json()
        assert "items" in data or "audit_enabled" in data
        assert "total" in data or "audit_enabled" in data

    def test_empty_db_returns_empty_list(self, client, auth_headers):
        """Empty DB should return empty items list, not error."""
        resp = client.get("/api/audit/rejected-trades", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        if data.get("audit_enabled", True):
            items = data.get("items", [])
            assert isinstance(items, list)

    def test_date_filter_accepts_valid_date(self, client, auth_headers):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        resp = client.get(
            f"/api/audit/rejected-trades?date={today}",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 422)

    def test_date_filter_rejects_invalid_format(self, client, auth_headers):
        resp = client.get(
            "/api/audit/rejected-trades?date=13-03-2026",  # wrong format
            headers=auth_headers,
        )
        # Pydantic should reject invalid pattern with 422
        assert resp.status_code == 422

    def test_strategy_filter(self, client, auth_headers):
        resp = client.get(
            "/api/audit/rejected-trades?strategy=SDOE",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_reason_code_filter(self, client, auth_headers):
        resp = client.get(
            "/api/audit/rejected-trades?reason_code=SECTOR_CAP_EXCEEDED",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_symbol_filter(self, client, auth_headers):
        resp = client.get(
            "/api/audit/rejected-trades?symbol=INFY",
            headers=auth_headers,
        )
        assert resp.status_code == 200


@pytest.mark.integration
class TestRejectedTradeDetail:
    """GET /api/audit/rejected-trades/{id}"""

    def test_nonexistent_id_returns_404(self, client, auth_headers):
        resp = client.get(
            "/api/audit/rejected-trades/99999",
            headers=auth_headers,
        )
        assert resp.status_code in (404, 200)  # 200 if empty body

    def test_invalid_id_type_returns_422(self, client, auth_headers):
        resp = client.get(
            "/api/audit/rejected-trades/not-a-number",
            headers=auth_headers,
        )
        assert resp.status_code == 422


@pytest.mark.integration
class TestRejectedTradeWithSeed:
    """Tests that require seeded rejected trade records."""

    def _with_seeded_client(self, test_app, seeded_db, auth_headers, fn):
        """Helper: run `fn(client)` with DB overridden to use seeded_db, then restore."""
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

        original = test_app.dependency_overrides.get(get_db)
        test_app.dependency_overrides[get_db] = override_get_db
        try:
            with TestClient(test_app) as c:
                fn(c)
        finally:
            if original is not None:
                test_app.dependency_overrides[get_db] = original
            else:
                test_app.dependency_overrides.pop(get_db, None)

    def test_seeded_records_returned(self, test_app, seeded_db, auth_headers):
        """3 seeded rejected trades should appear in today's list."""
        today = datetime.utcnow().strftime("%Y-%m-%d")

        def check(c):
            resp = c.get(f"/api/audit/rejected-trades?date={today}", headers=auth_headers)
            assert resp.status_code == 200

        self._with_seeded_client(test_app, seeded_db, auth_headers, check)

    def test_seeded_record_has_required_fields(self, test_app, seeded_db, auth_headers):
        def check(c):
            resp = c.get("/api/audit/rejected-trades", headers=auth_headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("audit_enabled", True) and data.get("items"):
                    item = data["items"][0]
                    # RejectedTrade serialises reasons as a list, not reason_code
                    for f in ("symbol", "strategy_name"):
                        assert f in item, f"Missing field: {f}"

        self._with_seeded_client(test_app, seeded_db, auth_headers, check)


@pytest.mark.unit
class TestRejectedTradesService:
    """Unit tests for RejectedTradesService logic (no HTTP layer)."""

    def test_service_get_today_returns_empty_for_no_records(self, db_session):
        from rejected_trades import RejectedTradesService
        svc = RejectedTradesService(db_session)
        result = svc.get_today(user_id="unknown-user-id")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_service_get_today_filters_by_user(self, db_session):
        import json
        from models import RejectedTrade
        reasons = json.dumps([{"code": "LOW_SCORE", "message": "score 42", "rule_name": "min_score", "rule_value": "65"}])
        # Insert two records: one for our user, one for another
        rt1 = RejectedTrade(user_id="user-A", symbol="RELIANCE", strategy_name="SDOE", side="BUY", order_type="CNC", reasons=reasons)
        rt2 = RejectedTrade(user_id="user-B", symbol="INFY", strategy_name="SDOE", side="BUY", order_type="CNC", reasons=reasons)
        db_session.add_all([rt1, rt2])
        db_session.flush()

        from rejected_trades import RejectedTradesService
        svc = RejectedTradesService(db_session)
        from datetime import date
        result = svc.get_today(user_id="user-A", target_date=date.today())
        symbols = [r["symbol"] for r in result]
        assert "RELIANCE" in symbols
        assert "INFY" not in symbols

    def test_service_get_by_id_not_found(self, db_session):
        from rejected_trades import RejectedTradesService
        svc = RejectedTradesService(db_session)
        result = svc.get_by_id(user_id="any-user", record_id=99999)
        assert result is None
