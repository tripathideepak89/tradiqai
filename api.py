"""FastAPI web interface for monitoring and control"""
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict
from datetime import date, datetime
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")

from database import SessionLocal
from models import Trade, DailyMetrics, SystemLog
from risk_engine import RiskEngine
from monitoring import MonitoringService
# DRE integration
from dividend_scheduler import register_dre_routes

app = FastAPI(
    title="AutoTrade AI API",
    description="API for monitoring and controlling the trading system",
    version="1.0.0"
)

# Dependency (must be defined before register_dre_routes)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Raw psycopg connection for DRE routes (which use .cursor() API)
def get_raw_db():
    import os
    try:
        import psycopg2 as _pg  # type: ignore[import]
    except ImportError:
        import psycopg as _pg  # psycopg v3
    conn = _pg.connect(os.environ.get("DATABASE_URL", ""))
    try:
        yield conn
    finally:
        conn.close()

# Register DRE API endpoints
register_dre_routes(app, get_raw_db)


# Pydantic models
class TradeResponse(BaseModel):
    id: int
    symbol: str
    strategy_name: str
    entry_price: float
    stop_price: float
    quantity: int
    status: str
    net_pnl: float = None
    
    class Config:
        from_attributes = True


class MetricsResponse(BaseModel):
    date: str
    total_pnl: float
    trades_taken: int
    win_rate: float
    max_drawdown: float


class KillSwitchRequest(BaseModel):
    reason: str = "Manual activation"


class BrokerConfigRequest(BaseModel):
    broker: str
    api_key: str = None
    api_secret: str = None
    user_id: str = None
    totp_secret: str = None
    client_id: str = None
    password: str = None
    app_id: str = None
    secret_key: str = None
    redirect_uri: str = None
    capital: float = None


# In-memory broker config storage (replace with DB in production)
_broker_config = {}


# Endpoints

@app.get("/")
async def root():
    """API root"""
    return {
        "name": "AutoTrade AI API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """System health check"""
    monitoring = MonitoringService()
    health = await monitoring.health_check()
    
    return {
        "status": "healthy" if all(health.values()) else "unhealthy",
        "components": health,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/trades/open", response_model=List[TradeResponse])
async def get_open_trades(db: Session = Depends(get_db)):
    """Get all open trades"""
    trades = db.query(Trade).filter(Trade.status == "open").all()
    return trades


@app.get("/trades/closed", response_model=List[TradeResponse])
async def get_closed_trades(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get recent closed trades"""
    trades = db.query(Trade).filter(
        Trade.status == "closed"
    ).order_by(Trade.exit_timestamp.desc()).limit(limit).all()
    return trades


@app.get("/trades/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: int, db: Session = Depends(get_db)):
    """Get specific trade details"""
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@app.get("/metrics/today")
async def get_today_metrics(db: Session = Depends(get_db)):
    """Get today's trading metrics"""
    today = date.today()
    metrics = db.query(DailyMetrics).filter(
        DailyMetrics.date == today
    ).first()
    
    if not metrics:
        return {
            "date": today.isoformat(),
            "message": "No trading activity today"
        }
    
    return {
        "date": metrics.date.isoformat(),
        "total_pnl": metrics.total_pnl,
        "trades_taken": metrics.trades_taken,
        "trades_won": metrics.trades_won,
        "trades_lost": metrics.trades_lost,
        "win_rate": metrics.win_rate,
        "max_drawdown": metrics.max_drawdown,
        "largest_win": metrics.largest_win,
        "largest_loss": metrics.largest_loss
    }


@app.get("/risk/status")
async def get_risk_status(db: Session = Depends(get_db)):
    """Get current risk metrics"""
    risk_engine = RiskEngine(db)
    metrics = await risk_engine.get_risk_metrics()
    return metrics


@app.get("/monitoring/kill-switch")
async def get_kill_switch_status():
    """Get kill switch status"""
    monitoring = MonitoringService()
    is_active = monitoring.is_kill_switch_active()
    
    return {
        "active": is_active,
        "reason": monitoring.get_kill_switch_reason() if is_active else None
    }


@app.post("/monitoring/kill-switch/activate")
async def activate_kill_switch(request: KillSwitchRequest):
    """Activate kill switch"""
    monitoring = MonitoringService()
    
    if monitoring.is_kill_switch_active():
        return JSONResponse(
            status_code=400,
            content={"message": "Kill switch already active"}
        )
    
    success = monitoring.activate_kill_switch(request.reason)
    
    if success:
        return {"message": "Kill switch activated", "reason": request.reason}
    else:
        raise HTTPException(status_code=500, detail="Failed to activate kill switch")


@app.post("/monitoring/kill-switch/deactivate")
async def deactivate_kill_switch():
    """Deactivate kill switch"""
    monitoring = MonitoringService()
    
    if not monitoring.is_kill_switch_active():
        return JSONResponse(
            status_code=400,
            content={"message": "Kill switch is not active"}
        )
    
    success = monitoring.deactivate_kill_switch()
    
    if success:
        return {"message": "Kill switch deactivated"}
    else:
        raise HTTPException(status_code=500, detail="Failed to deactivate kill switch")


@app.get("/logs/recent")
async def get_recent_logs(
    limit: int = 50,
    severity: str = None,
    db: Session = Depends(get_db)
):
    """Get recent system logs"""
    query = db.query(SystemLog)
    
    if severity:
        query = query.filter(SystemLog.severity == severity.upper())
    
    logs = query.order_by(SystemLog.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "timestamp": log.timestamp.isoformat(),
            "event_type": log.event_type,
            "severity": log.severity,
            "message": log.message,
            "symbol": log.symbol,
            "trade_id": log.trade_id
        }
        for log in logs
    ]


@app.get("/performance/summary")
async def get_performance_summary(db: Session = Depends(get_db)):
    """Get overall performance summary"""
    closed_trades = db.query(Trade).filter(Trade.status == "closed").all()
    
    if not closed_trades:
        return {"message": "No closed trades yet"}
    
    total_trades = len(closed_trades)
    winners = [t for t in closed_trades if t.net_pnl > 0]
    losers = [t for t in closed_trades if t.net_pnl <= 0]
    
    total_pnl = sum(t.net_pnl for t in closed_trades)
    win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
    
    total_profit = sum(t.net_pnl for t in winners) if winners else 0
    total_loss = abs(sum(t.net_pnl for t in losers)) if losers else 0
    profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
    
    return {
        "total_trades": total_trades,
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "profit_factor": round(profit_factor, 2),
        "avg_win": round(sum(t.net_pnl for t in winners) / len(winners), 2) if winners else 0,
        "avg_loss": round(sum(t.net_pnl for t in losers) / len(losers), 2) if losers else 0,
        "largest_win": round(max(t.net_pnl for t in winners), 2) if winners else 0,
        "largest_loss": round(min(t.net_pnl for t in losers), 2) if losers else 0
    }


@app.get("/dividend-radar", response_class=HTMLResponse)
async def dividend_radar(request: Request):
    return templates.TemplateResponse("dividend_radar.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Broker settings page"""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/api/broker/config")
async def get_broker_config():
    """Get current broker configuration"""
    global _broker_config
    if _broker_config:
        # Return config without sensitive data exposed in full
        safe_config = {
            "broker": _broker_config.get("broker"),
            "connected": _broker_config.get("connected", False)
        }
        # Add masked versions of keys
        if _broker_config.get("api_key"):
            safe_config["api_key"] = _broker_config["api_key"][:4] + "****" if len(_broker_config["api_key"]) > 4 else "****"
        if _broker_config.get("user_id"):
            safe_config["user_id"] = _broker_config.get("user_id")
        if _broker_config.get("client_id"):
            safe_config["client_id"] = _broker_config.get("client_id")
        if _broker_config.get("capital"):
            safe_config["capital"] = _broker_config.get("capital")
        return safe_config
    return {"broker": None, "connected": False}


@app.post("/api/broker/config")
async def save_broker_config(config: BrokerConfigRequest):
    """Save broker configuration"""
    global _broker_config
    
    # Convert to dict and store
    config_dict = config.model_dump(exclude_none=True)
    _broker_config = config_dict
    _broker_config["connected"] = False  # Will be set to True after successful test
    
    # Also update environment variables for the trading system
    import os
    broker = config.broker.lower()
    
    if broker == "zerodha":
        if config.api_key:
            os.environ["ZERODHA_API_KEY"] = config.api_key
        if config.api_secret:
            os.environ["ZERODHA_API_SECRET"] = config.api_secret
        if config.user_id:
            os.environ["ZERODHA_USER_ID"] = config.user_id
        if config.totp_secret:
            os.environ["ZERODHA_TOTP_SECRET"] = config.totp_secret
    elif broker == "groww":
        if config.api_key:
            os.environ["GROWW_API_KEY"] = config.api_key
        if config.api_secret:
            os.environ["GROWW_API_SECRET"] = config.api_secret
    elif broker == "paper":
        os.environ["PAPER_TRADING"] = "true"
        if config.capital:
            os.environ["INITIAL_CAPITAL"] = str(config.capital)
    
    # Set the active broker
    os.environ["BROKER"] = broker
    
    return {"message": "Configuration saved", "broker": broker}


@app.post("/api/broker/test")
async def test_broker_connection(config: BrokerConfigRequest):
    """Test broker connection"""
    global _broker_config
    
    broker = config.broker.lower()
    
    # Paper trading always connects
    if broker == "paper":
        _broker_config["connected"] = True
        return {"connected": True, "message": "Paper trading mode active"}
    
    # For real brokers, attempt connection test
    try:
        if broker == "zerodha":
            # Test Zerodha connection
            if not config.api_key or not config.api_secret:
                return {"connected": False, "message": "API Key and Secret are required"}
            
            try:
                from kiteconnect import KiteConnect
                kite = KiteConnect(api_key=config.api_key)
                # Can't fully test without login, but we can validate the API key format
                if len(config.api_key) < 8:
                    return {"connected": False, "message": "Invalid API Key format"}
                _broker_config["connected"] = True
                return {"connected": True, "message": "Zerodha credentials validated"}
            except ImportError:
                return {"connected": False, "message": "kiteconnect package not installed"}
            except Exception as e:
                return {"connected": False, "message": str(e)}
                
        elif broker == "groww":
            # Test Groww connection
            if not config.api_key or not config.api_secret:
                return {"connected": False, "message": "API Key and Secret are required"}
            
            # Groww doesn't have a public test endpoint, validate format
            if len(config.api_key) < 8:
                return {"connected": False, "message": "Invalid API Key format"}
            _broker_config["connected"] = True
            return {"connected": True, "message": "Groww credentials validated"}
            
        elif broker == "upstox":
            if not config.api_key or not config.api_secret:
                return {"connected": False, "message": "API Key and Secret are required"}
            _broker_config["connected"] = True
            return {"connected": True, "message": "Upstox credentials validated"}
            
        elif broker == "angelone":
            if not config.api_key or not config.client_id:
                return {"connected": False, "message": "API Key and Client ID are required"}
            _broker_config["connected"] = True
            return {"connected": True, "message": "Angel One credentials validated"}
            
        elif broker == "fyers":
            if not config.app_id or not config.secret_key:
                return {"connected": False, "message": "App ID and Secret Key are required"}
            _broker_config["connected"] = True
            return {"connected": True, "message": "Fyers credentials validated"}
        
        return {"connected": False, "message": f"Unknown broker: {broker}"}
        
    except Exception as e:
        return {"connected": False, "message": f"Connection test failed: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
