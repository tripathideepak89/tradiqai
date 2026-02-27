"""Database models for TradiqAI"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from database import Base


class User(Base):
    """User model - stores user accounts and settings"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    
    # Account Status
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # Trading Configuration
    capital = Column(Float, default=50000.0)
    paper_trading = Column(Boolean, default=True)
    broker_name = Column(String(50), default="groww")  # groww, zerodha
    broker_config = Column(Text, nullable=True)  # JSON string with broker credentials (encrypted)
    
    # Risk Settings (override defaults)
    max_daily_loss = Column(Float, default=1500.0)
    max_position_risk = Column(Float, default=400.0)
    max_open_positions = Column(Integer, default=2)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    daily_metrics = relationship("DailyMetrics", back_populates="user", cascade="all, delete-orphan")
    system_logs = relationship("SystemLog", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.username}>"


class TradeStatus(str, enum.Enum):
    """Trade status enumeration"""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradeDirection(str, enum.Enum):
    """Trade direction enumeration"""
    LONG = "long"
    SHORT = "short"


class Trade(Base):
    """Trade model - stores all trade information"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    strategy_name = Column(String(100), nullable=False)
    direction = Column(Enum(TradeDirection), nullable=False)
    
    # Entry
    entry_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Stop Loss & Target
    stop_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=True)
    risk_amount = Column(Float, nullable=False)
    
    # Exit
    exit_price = Column(Float, nullable=True)
    exit_timestamp = Column(DateTime(timezone=True), nullable=True)
    exit_reason = Column(String(100), nullable=True)  # stop_loss, target, manual, etc.
    
    # P&L
    realized_pnl = Column(Float, default=0.0)
    charges = Column(Float, default=0.0)  # brokerage + taxes
    net_pnl = Column(Float, default=0.0)
    
    # Broker Info
    broker_order_id = Column(String(100), nullable=True, index=True)
    broker_entry_id = Column(String(100), nullable=True)
    broker_exit_id = Column(String(100), nullable=True)
    broker_sl_id = Column(String(100), nullable=True)
    
    # Status
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING, index=True)
    
    # Risk Metrics
    risk_reward_ratio = Column(Float, nullable=True)
    actual_risk_reward = Column(Float, nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="trades")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DailyMetrics(Base):
    """Daily trading metrics and performance tracking"""
    __tablename__ = "daily_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), unique=True, nullable=False, index=True)
    
    # P&L Metrics
    total_pnl = Column(Float, default=0.0)
    gross_profit = Column(Float, default=0.0)
    gross_loss = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    
    # Trade Statistics
    trades_taken = Column(Integer, default=0)
    trades_won = Column(Integer, default=0)
    trades_lost = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # Risk Metrics
    max_drawdown = Column(Float, default=0.0)
    max_profit = Column(Float, default=0.0)
    largest_win = Column(Float, default=0.0)
    largest_loss = Column(Float, default=0.0)
    
    # Streak Tracking
    current_streak = Column(Integer, default=0)  # positive for wins, negative for losses
    loss_streak = Column(Integer, default=0)
    win_streak = Column(Integer, default=0)
    
    # Capital
    starting_capital = Column(Float, nullable=False)
    ending_capital = Column(Float, nullable=False)
    capital_deployed = Column(Float, default=0.0)
    
    # Risk Management
    daily_loss_limit_hit = Column(Boolean, default=False)
    trading_halted = Column(Boolean, default=False)
    halt_reason = Column(String(200), nullable=True)
    
    # Performance Ratios
    profit_factor = Column(Float, default=0.0)
    average_win = Column(Float, default=0.0)
    average_loss = Column(Float, default=0.0)
    expected_value = Column(Float, default=0.0)
    
    # Relationships
    user = relationship("User", back_populates="daily_metrics")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SystemLog(Base):
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Nullable for system-wide logs
    """System logs for debugging and auditing"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Log Details
    event_type = Column(String(100), nullable=False, index=True)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # Context
    symbol = Column(String(50), nullable=True, index=True)
    strategy_name = Column(String(100), nullable=True)
    trade_id = Column(Integer, nullable=True, index=True)
    order_id = Column(String(100), nullable=True)
    
    # Additional Data
    
    # Relationships
    user = relationship("User", back_populates="system_logs")
    log_metadata = Column(Text, nullable=True)  # JSON string for additional context
    
    # Error Tracking
    exception_type = Column(String(100), nullable=True)
    stack_trace = Column(Text, nullable=True)


class StrategyParameter(Base):
    """Store strategy parameters for tracking and optimization"""
    __tablename__ = "strategy_parameters"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String(100), nullable=False, index=True)
    parameter_name = Column(String(100), nullable=False)
    parameter_value = Column(String(200), nullable=False)
    parameter_type = Column(String(50), nullable=False)  # int, float, bool, string
    
    # Version Control
    version = Column(Integer, default=1)
    active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class NewsItem(Base):
    """News items for cross-process access"""
    __tablename__ = "news_items"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identification
    news_id = Column(String(32), unique=True, nullable=False, index=True)  # Hash-based ID
    source = Column(String(50), nullable=False, index=True)  # NSE, BSE, etc.
    exchange = Column(String(20), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    
    # Content
    headline = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, index=True)  # corporate, earnings, etc.
    
    # Impact Analysis (stored after processing)
    impact_score = Column(Integer, nullable=True)  # 0-100
    direction = Column(String(20), nullable=True)  # BULLISH, BEARISH, NEUTRAL
    action = Column(String(20), nullable=True)  # TRADE, WATCH, IGNORE
    blocked_by = Column(String(200), nullable=True)  # Reasons if blocked
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)  # When news published
    detected_at = Column(DateTime(timezone=True), server_default=func.now())  # When we detected
    
    # Metadata
    attachment_url = Column(String(500), nullable=True)
    raw_data = Column(Text, nullable=True)  # JSON string of raw data
    
    # Housekeeping
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<NewsItem {self.symbol} - {self.headline[:50]}>"


class PortfolioMetrics(Base):
    """Snapshot of CME portfolio state — written after every trade approval/exit.

    Stores the full capital allocation picture so the dashboard can show
    real-time exposure, drawdown, and risk mode without re-computing live.
    """
    __tablename__ = "portfolio_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Capital overview
    total_capital    = Column(Float, nullable=False)
    cash_available   = Column(Float, nullable=False)
    total_exposure   = Column(Float, default=0.0)
    peak_equity      = Column(Float, nullable=False)
    current_equity   = Column(Float, nullable=False)
    drawdown_pct     = Column(Float, default=0.0)

    # Risk mode: NORMAL | REDUCED | HALTED
    risk_mode        = Column(String(20), default="NORMAL")

    # JSON strings: {"SWING": 25000, "INTRADAY": 0, ...}
    strategy_exposure = Column(Text, nullable=True)
    sector_exposure   = Column(Text, nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self):
        return (
            f"<PortfolioMetrics capital=₹{self.total_capital:,.0f} "
            f"drawdown={self.drawdown_pct:.1f}% mode={self.risk_mode}>"
        )


class RebalanceRun(Base):
    """Stores results of each monthly rebalancer run (recommendations only, no auto-trading)."""
    __tablename__ = "rebalance_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    lookback_days = Column(Integer, default=30)

    # JSON: {bucket: score, ...}
    bucket_scores = Column(Text, nullable=True)
    # JSON: {bucket: pct, ...}
    current_allocations = Column(Text, nullable=True)
    # JSON: {bucket: pct, ...}
    recommended_allocations = Column(Text, nullable=True)
    # JSON: [{bucket, old_pct, new_pct, delta_pct, reason}, ...]
    changes = Column(Text, nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<RebalanceRun id={self.id} date={self.run_date}>"


class AllocationTargets(Base):
    """Stores AAE weekly allocation targets (latest row = current targets)."""
    __tablename__ = "allocation_targets"

    id = Column(Integer, primary_key=True, index=True)
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    regime = Column(String(20), default="NEUTRAL")
    lookback_days = Column(Integer, default=30)

    # JSON: {bucket: target_pct, ...}
    targets = Column(Text, nullable=False)
    # JSON: {bucket: delta_pct, ...}
    deltas = Column(Text, nullable=True)

    total_allocated_pct = Column(Float, default=100.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AllocationTargets id={self.id} regime={self.regime} at={self.computed_at}>"
