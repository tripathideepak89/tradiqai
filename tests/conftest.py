"""
Shared test fixtures for TradiqAI E2E / integration tests.

Key fixtures:
  db_session     — in-memory SQLite session (unit tests)
  test_app       — minimal FastAPI app with all routers, auth overridden
  client         — TestClient for test_app
  seeded_db      — db_session with realistic test data pre-populated
  mock_broker    — BaseBroker implementation that returns canned data
  fake_user      — dict that passes auth dependency checks
"""
import os
import sys
import pytest
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

# ── Ensure project root is importable ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Force test environment BEFORE any app imports ────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")  # test DB slot

# ── Stub out supabase package so routers that import it at load time work ────
# api_portfolio imports tradiqai_supabase_auth at module scope via _get_auth().
# Without supabase installed we need a lightweight stub.
from unittest.mock import MagicMock

def _make_supabase_stub():
    stub = MagicMock()
    stub.create_client.return_value = MagicMock()
    return stub


for _mod in ("supabase", "supabase.client", "supabase._sync.client"):
    if _mod not in sys.modules:
        sys.modules[_mod] = _make_supabase_stub()

# Stub tradiqai_supabase_config so tradiqai_supabase_auth can be imported
_config_stub = MagicMock()
_config_stub.get_supabase_client.return_value = MagicMock()
_config_stub.get_supabase_admin.return_value = MagicMock()
sys.modules.setdefault("tradiqai_supabase_config", _config_stub)

# Stub tradiqai_supabase_auth with a real get_current_user async function
async def _stub_get_current_user():
    return {"id": "test-user-uuid-001", "email": "test@example.com", "role": "authenticated"}

_auth_stub = MagicMock()
_auth_stub.get_current_user = _stub_get_current_user
_auth_stub.get_current_active_user = _stub_get_current_user
_auth_stub.auth_manager = MagicMock()
_auth_stub.auth_manager.get_current_user = MagicMock(return_value=_stub_get_current_user())
_auth_stub.UserLogin = MagicMock()
_auth_stub.UserRegister = MagicMock()
_auth_stub.UserResponse = MagicMock()
_auth_stub.Token = MagicMock()
sys.modules.setdefault("tradiqai_supabase_auth", _auth_stub)

# ── SQLAlchemy ────────────────────────────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    """Session-scoped SQLite in-memory engine with all tables created.

    StaticPool forces all connections to share the SAME in-memory database
    instance — without it, each new connection creates a separate empty DB.
    """
    from database import Base
    import models  # register all ORM models with Base.metadata

    eng = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    """Function-scoped DB session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session = TestSession()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ── Test data factories ───────────────────────────────────────────────────────

def make_user(session: Session, **kwargs) -> "models.User":
    from models import User
    defaults = dict(
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$fakehash",
        capital=100_000.0,
        paper_trading=True,
    )
    defaults.update(kwargs)
    user = User(**defaults)
    session.add(user)
    session.flush()
    return user


def make_trade(session: Session, user_id: int, **kwargs) -> "models.Trade":
    from models import Trade, TradeStatus, TradeDirection
    defaults = dict(
        user_id=user_id,
        symbol="RELIANCE",
        strategy_name="SDOE",
        direction=TradeDirection.LONG,
        entry_price=2500.0,
        quantity=4,
        stop_price=2450.0,
        risk_amount=200.0,
        status=TradeStatus.CLOSED,
        exit_price=2600.0,
        exit_timestamp=datetime.utcnow() - timedelta(days=1),
        net_pnl=380.0,
    )
    defaults.update(kwargs)
    trade = Trade(**defaults)
    session.add(trade)
    session.flush()
    return trade


def make_rejected_trade(session: Session, user_id: int, **kwargs) -> "models.RejectedTrade":
    import json
    from models import RejectedTrade
    defaults = dict(
        user_id=str(user_id),
        symbol="INFY",
        strategy_name="SDOE",
        side="BUY",
        order_type="CNC",
        reasons=json.dumps([{
            "code": "SECTOR_CAP_EXCEEDED",
            "message": "IT sector at 28% of capital; limit 25%",
            "rule_name": "sector_cap",
            "rule_value": "30%",
        }]),
    )
    defaults.update(kwargs)
    rt = RejectedTrade(**defaults)
    session.add(rt)
    session.flush()
    return rt


@pytest.fixture
def seeded_db(db_session: Session) -> Session:
    """DB session with 1 user, 15 closed trades, and 3 rejected trades."""
    user = make_user(db_session)

    # 12 winning trades
    for i in range(12):
        make_trade(
            db_session,
            user_id=user.id,
            symbol=f"STOCK{i}",
            net_pnl=300.0 + i * 50,
            risk_amount=200.0,
        )

    # 3 losing trades
    for i in range(3):
        make_trade(
            db_session,
            user_id=user.id,
            symbol=f"LOSER{i}",
            net_pnl=-190.0,
            risk_amount=200.0,
        )

    # 3 rejected trades
    for i in range(3):
        make_rejected_trade(db_session, user_id=user.id, symbol=f"REJECT{i}")

    db_session.commit()
    return db_session


# ── Fake auth user ────────────────────────────────────────────────────────────

FAKE_USER = {
    "id": "test-user-uuid-001",
    "email": "test@example.com",
    "role": "authenticated",
}


async def fake_get_current_user() -> dict:
    return FAKE_USER


# ── Mock Broker ───────────────────────────────────────────────────────────────

class MockBroker:
    """Fake broker that returns canned data — no network calls."""

    is_connected = True

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> bool:
        return True

    async def get_margins(self) -> dict:
        return {"available": 95_000.0, "used": 5_000.0}

    async def get_positions(self) -> list:
        return []

    async def get_orders(self) -> list:
        return []

    async def get_holdings(self) -> list:
        return []

    async def get_quote(self, symbol: str):
        from brokers.base import Quote
        return Quote(
            symbol=symbol,
            last_price=2500.0,
            bid=2499.0,
            ask=2501.0,
            volume=500_000,
            timestamp=datetime.utcnow(),
            open=2480.0,
            high=2520.0,
            low=2470.0,
            close=2500.0,
        )

    async def get_historical_data(self, symbol, from_date, to_date, interval="day") -> list:
        # Return 60 days of synthetic OHLCV
        data = []
        price = 2500.0
        for i in range(60):
            dt = from_date + timedelta(days=i)
            data.append({
                "date": dt,
                "open": price * 0.99,
                "high": price * 1.01,
                "low": price * 0.98,
                "close": price,
                "volume": 500_000,
            })
            price *= 1.001
        return data

    async def place_order(self, *args, **kwargs):
        from brokers.base import Order, OrderStatus, TransactionType, OrderType
        return Order(
            order_id="MOCK-ORDER-001",
            symbol=kwargs.get("symbol", "RELIANCE"),
            transaction_type=TransactionType.BUY,
            quantity=kwargs.get("quantity", 1),
            price=kwargs.get("price", 2500.0),
            order_type=OrderType.MARKET,
            status=OrderStatus.COMPLETE,
            filled_quantity=kwargs.get("quantity", 1),
            average_price=kwargs.get("price", 2500.0),
            timestamp=datetime.utcnow(),
        )

    async def modify_order(self, *args, **kwargs):
        return await self.place_order(**kwargs)

    async def cancel_order(self, order_id: str) -> bool:
        return True

    async def get_order_status(self, order_id: str):
        return await self.place_order()

    def subscribe_quotes(self, symbols, callback) -> bool:
        return True

    def unsubscribe_quotes(self, symbols) -> bool:
        return True


@pytest.fixture
def mock_broker() -> MockBroker:
    return MockBroker()


# ── Minimal FastAPI test app ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_app(engine):
    """
    Minimal FastAPI app with all API routers registered.
    Auth is overridden with fake_get_current_user.
    DB dependency is overridden with test SQLite session.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI(title="TradiqAI Test App")

    # ── Register routers ──────────────────────────────────────────────────────
    try:
        from api_portfolio import router as portfolio_router
        app.include_router(portfolio_router)
    except Exception as e:
        import logging
        logging.warning(f"Could not register portfolio router: {e}")

    try:
        from api_audit import router as audit_router
        app.include_router(audit_router)
    except Exception as e:
        import logging
        logging.warning(f"Could not register audit router: {e}")

    try:
        from api_sdoe import router as sdoe_router
        app.include_router(sdoe_router)
    except Exception as e:
        import logging
        logging.warning(f"Could not register SDOE router: {e}")

    # ── Health endpoint ───────────────────────────────────────────────────────
    @app.get("/health")
    def health():
        return {"status": "ok", "service": "tradiqai-test"}

    @app.get("/api/auth/me")
    async def auth_me():
        return FAKE_USER

    # ── Override auth dependencies ────────────────────────────────────────────
    # 1. api_portfolio uses tradiqai_supabase_auth.get_current_user
    try:
        from tradiqai_supabase_auth import get_current_user
        app.dependency_overrides[get_current_user] = fake_get_current_user
    except Exception:
        pass  # supabase not available in test env

    # 2. api_audit uses its own _current_user (lazy HTTPBearer pattern)
    try:
        import api_audit
        app.dependency_overrides[api_audit._current_user] = fake_get_current_user
    except Exception:
        pass

    # ── Override DB dependency ────────────────────────────────────────────────
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    try:
        from database import get_db
        app.dependency_overrides[get_db] = override_get_db
    except Exception:
        pass

    return app


@pytest.fixture(scope="session")
def client(test_app):
    """Session-scoped TestClient."""
    from fastapi.testclient import TestClient
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict:
    """Bearer token headers for authenticated requests."""
    return {"Authorization": "Bearer fake-test-jwt-token"}
