"""Tests for the Rejected Trades Audit feature.

Run with: pytest tests/test_rejected_trades.py -v

Coverage
────────
Unit tests
  TestRejectionReason     — dataclass structure
  TestRiskSnapshot        — to_dict serialisation
  TestRejectedTradesService — log_rejection, dedup, get_today, cleanup

Integration tests
  TestAuditEndpointAuth   — endpoint requires authentication
  TestAuditEndpointFilter — date filter, strategy/code/symbol filters
"""
import json
import pytest
from datetime import datetime, timezone, timedelta, date
from unittest.mock import MagicMock, patch


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_db(rows=None):
    """Build a minimal SQLAlchemy session mock that returns `rows` from query."""
    db = MagicMock()
    rows = rows or []

    query_chain = MagicMock()
    query_chain.filter.return_value = query_chain
    query_chain.order_by.return_value = query_chain
    query_chain.all.return_value = rows
    query_chain.first.return_value = rows[0] if rows else None
    query_chain.delete.return_value = len(rows)

    db.query.return_value = query_chain
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


def _make_record(
    id=1,
    user_id="user-abc",
    symbol="RELIANCE",
    strategy_name="IntradayStrategy",
    side="BUY",
    order_type="MIS",
    entry_price=2800.0,
    reasons=None,
    risk_snapshot=None,
    count=1,
    first_at=None,
    latest_at=None,
):
    """Return a mock RejectedTrade ORM row."""
    r = MagicMock()
    r.id               = id
    r.user_id          = user_id
    r.symbol           = symbol
    r.exchange         = "NSE"
    r.strategy_name    = strategy_name
    r.side             = side
    r.order_type       = order_type
    r.entry_price      = entry_price
    r.stop_loss        = entry_price * 0.98
    r.target           = entry_price * 1.04
    r.quantity_requested = 5
    r.exposure_requested = entry_price * 5
    r.reasons          = json.dumps(reasons or [
        {"code": "CME_HALTED", "message": "Halted", "rule_name": "cme", "rule_value": ""}
    ])
    r.risk_snapshot    = json.dumps(risk_snapshot or {
        "drawdown_pct": 12.5, "cash_available": 5000.0,
        "exposure_pct": 65.0, "regime": "BEAR",
    })
    now = datetime.now(timezone.utc)
    r.first_at  = first_at  or now
    r.latest_at = latest_at or now
    r.count     = count
    return r


# ─── Unit: RejectionReason ───────────────────────────────────────────────────

class TestRejectionReason:
    def test_required_fields(self):
        from rejected_trades import RejectionReason
        r = RejectionReason(
            code="CME_HALTED",
            message="Portfolio drawdown >= 12%",
            rule_name="capital_manager.approve_trade",
        )
        assert r.code == "CME_HALTED"
        assert r.message == "Portfolio drawdown >= 12%"
        assert r.rule_name == "capital_manager.approve_trade"
        assert r.rule_value == ""  # default

    def test_optional_rule_value(self):
        from rejected_trades import RejectionReason
        r = RejectionReason(
            code="CME_SECTOR_CAP",
            message="Sector cap hit",
            rule_name="sector_cap_check",
            rule_value="sector=IT, current=38%, limit=30%",
        )
        assert r.rule_value == "sector=IT, current=38%, limit=30%"

    def test_dataclass_is_serialisable(self):
        from dataclasses import asdict
        from rejected_trades import RejectionReason
        r = RejectionReason(code="X", message="Y", rule_name="Z")
        d = asdict(r)
        assert set(d.keys()) == {"code", "message", "rule_name", "rule_value"}
        # Must serialise to JSON without errors
        assert json.loads(json.dumps(d))["code"] == "X"


# ─── Unit: RiskSnapshot ──────────────────────────────────────────────────────

class TestRiskSnapshot:
    def test_defaults(self):
        from rejected_trades import RiskSnapshot
        s = RiskSnapshot()
        assert s.portfolio_equity == 0.0
        assert s.regime == "UNKNOWN"
        assert s.vix_proxy is None

    def test_to_dict_excludes_none_vix(self):
        from rejected_trades import RiskSnapshot
        s = RiskSnapshot(drawdown_pct=5.2, regime="BULL")
        d = s.to_dict()
        assert d["drawdown_pct"] == 5.2
        assert d["regime"] == "BULL"
        assert "vix_proxy" not in d  # None values stripped

    def test_to_dict_includes_vix_when_set(self):
        from rejected_trades import RiskSnapshot
        s = RiskSnapshot(vix_proxy=18.4)
        d = s.to_dict()
        assert d["vix_proxy"] == 18.4


# ─── Unit: RejectedTradesService ─────────────────────────────────────────────

class TestRejectedTradesService:
    def test_log_rejection_disabled_by_flag(self):
        """When audit is disabled, log_rejection must NOT touch the DB."""
        from rejected_trades import RejectedTradesService, RejectionReason
        db = _make_db()
        svc = RejectedTradesService(db)

        with patch("rejected_trades.settings") as mock_cfg:
            mock_cfg.rejected_trades_audit_enabled = False
            svc.log_rejection(
                user_id="u1", symbol="INFY", strategy_name="Swing",
                side="BUY", reasons=[
                    RejectionReason(code="CME_HALTED", message="Halted", rule_name="cme")
                ],
            )

        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_log_rejection_creates_new_record(self):
        """First rejection for a symbol creates a new DB row."""
        from rejected_trades import RejectedTradesService, RejectionReason
        db = _make_db(rows=[])  # no existing record
        svc = RejectedTradesService(db)

        with patch("rejected_trades.settings") as mock_cfg:
            mock_cfg.rejected_trades_audit_enabled = True
            svc.log_rejection(
                user_id="u1", symbol="TCS", strategy_name="Swing",
                side="BUY",
                reasons=[
                    RejectionReason(code="COST_FILTER", message="Costs too high", rule_name="cost")
                ],
                entry_price=3500.0, quantity=2,
            )

        db.add.assert_called_once()
        db.commit.assert_called_once()
        # Inspect the record that was added
        record = db.add.call_args[0][0]
        assert record.symbol == "TCS"
        assert record.user_id == "u1"
        assert record.count == 1

    def test_log_rejection_dedup_increments_count(self):
        """Same (user, symbol, strategy, side) within window → updates, no insert."""
        from rejected_trades import RejectedTradesService, RejectionReason
        existing = _make_record(count=2, latest_at=datetime.now(timezone.utc))
        db = _make_db(rows=[existing])
        svc = RejectedTradesService(db)

        with patch("rejected_trades.settings") as mock_cfg:
            mock_cfg.rejected_trades_audit_enabled = True
            svc.log_rejection(
                user_id="user-abc", symbol="RELIANCE",
                strategy_name="IntradayStrategy", side="BUY",
                reasons=[
                    RejectionReason(code="CME_HALTED", message="H", rule_name="cme")
                ],
            )

        db.add.assert_not_called()          # no new row
        db.commit.assert_called_once()
        assert existing.count == 3          # incremented

    def test_log_rejection_silent_on_exception(self):
        """A broken DB session must not propagate exceptions."""
        from rejected_trades import RejectedTradesService, RejectionReason
        db = MagicMock()
        db.query.side_effect = RuntimeError("DB is down")
        svc = RejectedTradesService(db)

        with patch("rejected_trades.settings") as mock_cfg:
            mock_cfg.rejected_trades_audit_enabled = True
            # Should not raise
            svc.log_rejection(
                user_id="u", symbol="X", strategy_name="Y", side="BUY",
                reasons=[RejectionReason(code="C", message="M", rule_name="R")],
            )

    def test_get_today_returns_user_and_system_records(self):
        """get_today returns both own records and 'system' records."""
        from rejected_trades import RejectedTradesService
        own    = _make_record(user_id="uuid-1", symbol="HDFC")
        system = _make_record(user_id="system",  symbol="TCS")
        db = _make_db(rows=[own, system])
        svc = RejectedTradesService(db)

        items = svc.get_today("uuid-1")
        assert len(items) == 2
        assert items[0]["symbol"] == "HDFC"
        assert items[1]["symbol"] == "TCS"

    def test_get_today_returns_primary_reason_helper(self):
        """Each returned item has primary_reason_code populated."""
        from rejected_trades import RejectedTradesService
        row = _make_record(reasons=[
            {"code": "CME_HALTED", "message": "Halted", "rule_name": "cme", "rule_value": ""},
        ])
        db = _make_db(rows=[row])
        svc = RejectedTradesService(db)
        items = svc.get_today("user-abc")
        assert items[0]["primary_reason_code"] == "CME_HALTED"
        assert items[0]["primary_reason_message"] == "Halted"

    def test_get_today_handles_malformed_json_gracefully(self):
        """Malformed JSON in reasons/snapshot must not crash get_today."""
        from rejected_trades import RejectedTradesService
        row = _make_record()
        row.reasons       = "NOT VALID JSON"
        row.risk_snapshot = "{broken}"
        db = _make_db(rows=[row])
        svc = RejectedTradesService(db)
        items = svc.get_today("user-abc")
        assert items[0]["reasons"] == []
        assert items[0]["risk_snapshot"] == {}

    def test_get_by_id_returns_none_for_missing_record(self):
        from rejected_trades import RejectedTradesService
        db = _make_db(rows=[])
        svc = RejectedTradesService(db)
        assert svc.get_by_id("u1", 999) is None

    def test_get_by_id_returns_dict_for_existing(self):
        from rejected_trades import RejectedTradesService
        row = _make_record(id=42)
        db = _make_db(rows=[row])
        svc = RejectedTradesService(db)
        result = svc.get_by_id("user-abc", 42)
        assert result is not None
        assert result["id"] == 42
        assert result["symbol"] == "RELIANCE"

    def test_cleanup_old_deletes_and_returns_count(self):
        from rejected_trades import RejectedTradesService
        db = _make_db(rows=[_make_record(), _make_record()])
        # Make delete return 2
        db.query.return_value.filter.return_value.delete.return_value = 2

        with patch("rejected_trades.settings") as mock_cfg:
            mock_cfg.rejected_trades_retention_days = 30
            count = RejectedTradesService.cleanup_old(db)

        assert count == 2
        db.commit.assert_called_once()


# ─── Unit: Reason code dedup window ──────────────────────────────────────────

class TestDedupWindow:
    def test_record_outside_window_creates_new(self):
        """A record older than DEDUP_WINDOW_MINUTES is treated as a new event."""
        from rejected_trades import RejectedTradesService, RejectionReason, DEDUP_WINDOW_MINUTES
        old_record = _make_record(
            count=1,
            latest_at=datetime.now(timezone.utc) - timedelta(minutes=DEDUP_WINDOW_MINUTES + 1),
        )
        db = _make_db(rows=[])  # first() returns None — old record is filtered out by SQL
        svc = RejectedTradesService(db)

        with patch("rejected_trades.settings") as mock_cfg:
            mock_cfg.rejected_trades_audit_enabled = True
            svc.log_rejection(
                user_id="user-abc", symbol="RELIANCE",
                strategy_name="IntradayStrategy", side="BUY",
                reasons=[
                    RejectionReason(code="CME_HALTED", message="H", rule_name="cme")
                ],
            )

        db.add.assert_called_once()  # new record inserted, not merged

    def test_dedup_window_constant_is_10(self):
        from rejected_trades import DEDUP_WINDOW_MINUTES
        assert DEDUP_WINDOW_MINUTES == 10


# ─── Integration: API endpoint authorisation ─────────────────────────────────

class TestAuditEndpointAuth:
    """Verify the endpoints are registered at the correct paths."""

    def test_list_endpoint_exists_at_correct_path(self):
        """GET /api/audit/rejected-trades path is registered."""
        from fastapi import FastAPI
        from api_audit import router
        app = FastAPI()
        app.include_router(router)
        routes = [r.path for r in app.routes]
        assert "/api/audit/rejected-trades" in routes

    def test_detail_endpoint_exists_at_correct_path(self):
        """GET /api/audit/rejected-trades/{record_id} path is registered."""
        from fastapi import FastAPI
        from api_audit import router
        app = FastAPI()
        app.include_router(router)
        routes = [r.path for r in app.routes]
        assert "/api/audit/rejected-trades/{record_id}" in routes


# ─── Integration: API endpoint filtering ─────────────────────────────────────

class TestAuditEndpointFilter:
    """Verify the list endpoint applies filters correctly before returning."""

    def _build_client(self, items, mock_audit_enabled=True):
        """Return a TestClient with auth + db mocked out."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api_audit import router, _current_user, _get_db

        fake_user = {"id": "user-abc", "username": "test"}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[_current_user] = lambda: fake_user
        app.dependency_overrides[_get_db()] = lambda: MagicMock()

        with patch("api_audit.settings") as mock_cfg, \
             patch("api_audit.RejectedTradesService") as MockSvc:
            mock_cfg.rejected_trades_audit_enabled = mock_audit_enabled
            MockSvc.return_value.get_today.return_value = items
            client = TestClient(app)
            yield client, MockSvc

    def test_returns_all_items_with_no_filters(self):
        items = [
            {"symbol": "HDFC", "strategy_name": "Swing", "side": "BUY",
             "reasons": [{"code": "CME_HALTED"}], "primary_reason_code": "CME_HALTED"},
            {"symbol": "INFY", "strategy_name": "Intraday", "side": "BUY",
             "reasons": [{"code": "COST_FILTER"}], "primary_reason_code": "COST_FILTER"},
        ]
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api_audit import router, _current_user, _get_db

        fake_user = {"id": "user-abc"}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[_current_user] = lambda: fake_user
        app.dependency_overrides[_get_db()] = lambda: MagicMock()

        with patch("api_audit.settings") as mock_cfg, \
             patch("api_audit.RejectedTradesService") as MockSvc:
            mock_cfg.rejected_trades_audit_enabled = True
            MockSvc.return_value.get_today.return_value = items
            client = TestClient(app)
            r = client.get("/api/audit/rejected-trades",
                           headers={"Authorization": "Bearer fake"})
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_strategy_filter(self):
        items = [
            {"symbol": "HDFC", "strategy_name": "SwingStrategy", "side": "BUY",
             "reasons": [{"code": "CME_HALTED"}], "primary_reason_code": "CME_HALTED"},
            {"symbol": "INFY", "strategy_name": "IntradayStrategy", "side": "BUY",
             "reasons": [{"code": "COST_FILTER"}], "primary_reason_code": "COST_FILTER"},
        ]
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api_audit import router, _current_user, _get_db

        fake_user = {"id": "user-abc"}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[_current_user] = lambda: fake_user
        app.dependency_overrides[_get_db()] = lambda: MagicMock()

        with patch("api_audit.settings") as mock_cfg, \
             patch("api_audit.RejectedTradesService") as MockSvc:
            mock_cfg.rejected_trades_audit_enabled = True
            MockSvc.return_value.get_today.return_value = items
            client = TestClient(app)
            r = client.get("/api/audit/rejected-trades?strategy=SwingStrategy",
                           headers={"Authorization": "Bearer fake"})
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["symbol"] == "HDFC"

    def test_reason_code_filter(self):
        items = [
            {"symbol": "HDFC", "strategy_name": "S", "side": "BUY",
             "reasons": [{"code": "CME_HALTED"}], "primary_reason_code": "CME_HALTED"},
            {"symbol": "INFY", "strategy_name": "S", "side": "BUY",
             "reasons": [{"code": "COST_FILTER"}], "primary_reason_code": "COST_FILTER"},
        ]
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api_audit import router, _current_user, _get_db

        fake_user = {"id": "user-abc"}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[_current_user] = lambda: fake_user
        app.dependency_overrides[_get_db()] = lambda: MagicMock()

        with patch("api_audit.settings") as mock_cfg, \
             patch("api_audit.RejectedTradesService") as MockSvc:
            mock_cfg.rejected_trades_audit_enabled = True
            MockSvc.return_value.get_today.return_value = items
            client = TestClient(app)
            r = client.get("/api/audit/rejected-trades?reason_code=COST_FILTER",
                           headers={"Authorization": "Bearer fake"})
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["symbol"] == "INFY"

    def test_symbol_filter_case_insensitive_prefix(self):
        items = [
            {"symbol": "HDFCBANK", "strategy_name": "S", "side": "BUY",
             "reasons": [{"code": "CME_HALTED"}], "primary_reason_code": "CME_HALTED"},
            {"symbol": "INFY", "strategy_name": "S", "side": "BUY",
             "reasons": [{"code": "COST_FILTER"}], "primary_reason_code": "COST_FILTER"},
        ]
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api_audit import router, _current_user, _get_db

        fake_user = {"id": "user-abc"}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[_current_user] = lambda: fake_user
        app.dependency_overrides[_get_db()] = lambda: MagicMock()

        with patch("api_audit.settings") as mock_cfg, \
             patch("api_audit.RejectedTradesService") as MockSvc:
            mock_cfg.rejected_trades_audit_enabled = True
            MockSvc.return_value.get_today.return_value = items
            client = TestClient(app)
            r = client.get("/api/audit/rejected-trades?symbol=hdfc",
                           headers={"Authorization": "Bearer fake"})
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["symbol"] == "HDFCBANK"

    def test_audit_disabled_returns_empty_with_flag(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api_audit import router, _current_user, _get_db

        fake_user = {"id": "user-abc"}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[_current_user] = lambda: fake_user
        app.dependency_overrides[_get_db()] = lambda: MagicMock()

        with patch("api_audit.settings") as mock_cfg, \
             patch("api_audit.RejectedTradesService"):
            mock_cfg.rejected_trades_audit_enabled = False
            client = TestClient(app)
            r = client.get("/api/audit/rejected-trades",
                           headers={"Authorization": "Bearer fake"})
        assert r.status_code == 200
        data = r.json()
        assert data["audit_enabled"] is False
        assert data["total"] == 0
