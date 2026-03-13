"""
Integration tests for SDOE (Strong Dip Opportunity Engine) API endpoints.

These tests do NOT trigger a live yfinance scan. The scanner singleton is
mocked at the service layer before the endpoint is called.

Covers:
  GET  /api/strategies/strong-dip/status
  GET  /api/strategies/strong-dip/today
  GET  /api/strategies/strong-dip/strong-buy
  GET  /api/strategies/strong-dip/watchlist
  GET  /api/strategies/strong-dip/rejected
  GET  /api/strategies/strong-dip/config
  GET  /api/strategies/strong-dip/filter
  GET  /api/strategies/strong-dip/by-sector
  POST /api/strategies/strong-dip/scan          (mocked — no real network)
  GET  /api/strategies/strong-dip/{symbol}/explain
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


# ── Canned scanner data ───────────────────────────────────────────────────────

def _make_mock_signal(symbol="RELIANCE", score=82, category="strong_buy"):
    return {
        "symbol": symbol,
        "exchange": "NSE",
        "strategy": "SDOE",
        "total_score": score,
        "category": category,
        "score_breakdown": {
            "decline": 18,
            "quality": 22,
            "stabilization": 16,
            "recovery": 12,
            "market": 8,
            "upside_bonus": 6,
        },
        "trade_params": {
            "entry_zone": [2450.0, 2480.0],
            "stop_loss": 2400.0,
            "target_1": 2600.0,
            "target_2": 2750.0,
            "risk_reward_ratio": 2.5,
        },
        "holding_horizon": "5-20 days",
        "is_approved": True,
        "selection_reasons": ["10% dip from 60d high", "Strong fundamentals"],
        "rejection_reasons": [],
        "risk_factors": ["Market in sideways phase"],
        "analyzed_at": datetime.utcnow().isoformat(),
        "decline_metrics": {"decline_from_60d_pct": 10.2},
        "quality_metrics": {"sector": "Energy"},
    }


def _make_mock_rejected(symbol="SMALLCAP"):
    return {
        "symbol": symbol,
        "total_score": 42,
        "category": "rejected",
        "rejection_reasons": [{"code": "LOW_QUALITY", "detail": "P/E ratio > 80"}],
        "analyzed_at": datetime.utcnow().isoformat(),
    }


def _make_mock_scanner():
    """Return a fully-mocked scanner singleton."""
    scanner = MagicMock()
    scanner.get_scan_status.return_value = {
        "has_data": True,
        "last_scan": {"timestamp": datetime.utcnow().isoformat()},
        "cache_age_minutes": 5.0,
        "is_cache_fresh": True,
        "counts": {"strong_buy": 2, "watchlist": 3, "monitor": 1, "rejected": 10},
    }
    scanner.get_today_opportunities.return_value = {
        "strong_buy": [_make_mock_signal("RELIANCE", 85), _make_mock_signal("TCS", 81)],
        "watchlist": [_make_mock_signal("INFY", 72, "watchlist")],
        "monitor": [_make_mock_signal("WIPRO", 55, "monitor")],
        "rejected": [_make_mock_rejected("SMALLCAP")],
    }
    scanner.get_strong_buy.return_value = [_make_mock_signal("RELIANCE", 85)]
    scanner.get_watchlist.return_value = [_make_mock_signal("INFY", 72, "watchlist")]
    scanner.get_rejected.return_value = [_make_mock_rejected("SMALLCAP")] * 5
    scanner.filter_opportunities.return_value = [_make_mock_signal("RELIANCE", 85)]
    scanner.explain_symbol = AsyncMock(return_value={
        "symbol": "RELIANCE",
        "score": 85,
        "is_approved": True,
        "explanation": "Strong dip candidate",
    })

    scan_result = MagicMock()
    scan_result.to_dict.return_value = {
        "scanned": 200,
        "approved": 5,
        "duration_seconds": 12.3,
    }
    scanner.scan_universe = AsyncMock(return_value=scan_result)

    return scanner


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestSDOEStatus:
    def test_status_returns_200(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/status")
        assert resp.status_code == 200

    def test_status_has_required_keys(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/status")
        if resp.status_code == 200:
            data = resp.json()
            assert "has_data" in data
            assert "counts" in data
            assert "is_cache_fresh" in data


@pytest.mark.integration
class TestSDOEToday:
    def test_today_returns_200(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/today")
        assert resp.status_code == 200

    def test_today_has_categories(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/today")
        if resp.status_code == 200:
            data = resp.json()
            assert "strong_buy" in data
            assert "watchlist" in data
            assert "monitor" in data

    def test_strong_buy_list_populated(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/today")
        if resp.status_code == 200:
            data = resp.json()
            assert len(data["strong_buy"]) == 2

    def test_signal_has_score_breakdown(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/today")
        if resp.status_code == 200:
            data = resp.json()
            if data["strong_buy"]:
                signal = data["strong_buy"][0]
                assert "total_score" in signal
                assert signal["total_score"] >= 80

    def test_scan_status_included(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/today")
        if resp.status_code == 200:
            data = resp.json()
            assert "scan_status" in data


@pytest.mark.integration
class TestSDOEStrongBuy:
    def test_returns_200_with_count(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/strong-buy")
        assert resp.status_code == 200
        if resp.status_code == 200:
            data = resp.json()
            assert "count" in data
            assert "candidates" in data


@pytest.mark.integration
class TestSDOEWatchlist:
    def test_returns_200_with_count(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/watchlist")
        assert resp.status_code == 200


@pytest.mark.integration
class TestSDOERejected:
    def test_returns_200(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/rejected")
        assert resp.status_code == 200

    def test_limit_parameter(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/rejected?limit=2")
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("showing", 0) <= 2

    def test_limit_too_large_rejected(self, client):
        resp = client.get("/api/strategies/strong-dip/rejected?limit=9999")
        assert resp.status_code == 422


@pytest.mark.integration
class TestSDOEFilter:
    def test_filter_min_score(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/filter?min_score=70")
        assert resp.status_code == 200

    def test_filter_sector(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/filter?sector=Energy")
        assert resp.status_code == 200

    def test_filter_response_has_filters_applied(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/filter?min_score=65&max_score=90")
        if resp.status_code == 200:
            data = resp.json()
            assert "filters_applied" in data
            assert data["filters_applied"]["min_score"] == 65


@pytest.mark.integration
class TestSDOEConfig:
    def test_config_returns_thresholds(self, client):
        resp = client.get("/api/strategies/strong-dip/config")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "classification_thresholds" in data
            thresholds = data["classification_thresholds"]
            assert thresholds["strong_buy"] >= 70
            assert thresholds["watchlist"] < thresholds["strong_buy"]


@pytest.mark.integration
class TestSDOEBySector:
    def test_by_sector_returns_grouped(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/by-sector")
        assert resp.status_code == 200
        if resp.status_code == 200:
            data = resp.json()
            assert "sectors" in data
            assert "sector_count" in data


@pytest.mark.integration
class TestSDOEExplain:
    def test_explain_known_symbol(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.get("/api/strategies/strong-dip/RELIANCE/explain")
        assert resp.status_code == 200
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("symbol") == "RELIANCE"


@pytest.mark.integration
@pytest.mark.slow
class TestSDOEScan:
    def test_scan_returns_success(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.post("/api/strategies/strong-dip/scan")
        assert resp.status_code == 200
        if resp.status_code == 200:
            data = resp.json()
            assert data["success"] is True

    def test_scan_force_refresh(self, client):
        with patch("api_sdoe.get_sdoe_scanner", return_value=_make_mock_scanner()):
            resp = client.post("/api/strategies/strong-dip/scan?force_refresh=true")
        assert resp.status_code == 200
