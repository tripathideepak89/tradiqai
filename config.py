"""Configuration management for AutoTrade AI"""
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    env: str = os.getenv("ENV", "development")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Trading Configuration
    # Professional Risk Management Rules (Survival > Consistency > Growth)
    # Based on ₹50k capital model
    initial_capital: float = 50000.0  # User's available capital
    
    # Risk Tolerance: 0-100 (affects all risk parameters dynamically)
    risk_tolerance: int = 50  # 0=Ultra Safe, 50=Balanced, 100=Aggressive
    
    # Risk Per Trade: Fixed ₹400 for ₹50k (0.8%)
    max_per_trade_risk: float = 400.0
    
    # Daily Loss Stop: ₹1,500 for ₹50k (3%)
    max_daily_loss: float = 1500.0
    
    # Position Limits: Max 2 open positions (avoid overexposure)
    max_open_trades: int = 2
    
    # Capital Per Trade: 25% of available capital max
    max_capital_per_trade_percent: float = 25.0
    
    # Total Exposure: 60% max (conservative)
    max_exposure_percent: float = 60.0
    
    # Consecutive Loss Stop: 3 losses = 60 minute pause (prevents revenge trading)
    consecutive_loss_limit: int = 3
    consecutive_loss_pause_minutes: int = 60
    
    # Broker Selection
    broker: str = "zerodha"  # zerodha or groww
    
    # Zerodha
    zerodha_api_key: Optional[str] = None
    zerodha_api_secret: Optional[str] = None
    zerodha_user_id: Optional[str] = None
    zerodha_password: Optional[str] = None
    zerodha_totp_secret: Optional[str] = None
    
    # Groww
    groww_api_key: Optional[str] = None
    groww_api_secret: Optional[str] = None
    groww_api_url: str = "https://api.groww.in/v1"
    
    # Database
    database_url: str = "sqlite:///./autotrade.db"  # Local SQLite for development
    redis_url: str = "redis://localhost:6379/0"
    
    # Supabase
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_db_password: Optional[str] = None
    
    # Monitoring
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    enable_alerts: bool = True
    
    # Trading Hours
    market_open_time: str = "09:15"
    market_close_time: str = "15:30"
    
    # Strategy
    enable_intraday: bool = True
    enable_swing: bool = False
    paper_trading: bool = False  # LIVE TRADING ENABLED - Real orders to broker
    
    # Safety
    enable_kill_switch: bool = True
    position_reconciliation_interval: int = 10

    # Capital Management Engine (CME)
    cme_total_capital: float = 100_000.0  # ₹1,00,000 portfolio capital

    # ── Rejected Trades Audit ────────────────────────────────────────────────
    # Set REJECTED_TRADES_AUDIT_ENABLED=false to disable logging + UI entirely.
    rejected_trades_audit_enabled: bool = True
    # How many days to retain rejected-trade records before the cleanup job
    # deletes them (configurable via REJECTED_TRADES_RETENTION_DAYS env var).
    rejected_trades_retention_days: int = 30
    # Supabase UUID of the primary trading account owner.  When the trading
    # system logs a rejection it tags it with this ID so the audit UI can
    # filter correctly.  Leave empty to tag with "system".
    trading_account_user_id: Optional[str] = None

    # ── Strong Dip Opportunity Engine (SDOE) ─────────────────────────────────
    # Enable SDOE strategy alongside or instead of existing strategies
    sdoe_enabled: bool = True
    # Minimum score for SDOE signals to be considered actionable
    sdoe_min_score: int = 65
    # Maximum number of SDOE signals to generate per day
    sdoe_max_signals_per_day: int = 5
    # Decline thresholds (from 60-day high)
    sdoe_decline_min_pct: float = 5.0   # Min decline to be considered
    sdoe_decline_max_pct: float = 35.0  # Max decline (avoid falling knives)
    # Quality thresholds
    sdoe_min_market_cap_cr: float = 5000.0  # Min market cap in crores
    sdoe_min_avg_volume_cr: float = 10.0    # Min avg traded value in crores
    # Position sizing in bearish market (multiplier)
    sdoe_bearish_size_multiplier: float = 0.5
    # Auto-run SDOE scan at market open
    sdoe_auto_scan_enabled: bool = True
    # Scan cache TTL in minutes
    sdoe_cache_ttl_minutes: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields not defined in Settings


settings = Settings()
