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

# Raw psycopg2 connection for DRE routes (which use .cursor() API)
def get_raw_db():
    import psycopg2
    import os
    conn = psycopg2.connect(os.environ.get("DATABASE_URL", ""))
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
