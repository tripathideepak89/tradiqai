"""
Real-time Web Dashboard for TradiqAI
Provides live visualization of trading activity, positions, and metrics
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer
import uvicorn
from sqlalchemy import create_engine, select, desc, text
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv
from collections import defaultdict
import time

# Import models
from models import Trade, NewsItem, User, DailyMetrics
from brokers.groww import GrowwBroker
from config import settings as config
from utils.timezone import now_ist, format_ist, today_ist, IST

# Import Supabase authentication
from tradiqai_supabase_auth import (
    auth_manager, get_current_user, get_current_active_user,
    UserLogin, UserRegister, UserResponse, Token
)

# Import news system
from news_ingestion_layer import get_news_ingestion_layer
from news_impact_detector import NewsImpactDetector, NewsAction

# Load environment
load_dotenv()

# Custom formatter with IST timezone
class ISTFormatter(logging.Formatter):
    """Logging formatter that displays timestamps in IST"""
    def formatTime(self, record, datefmt=None):
        from utils import now_ist
        dt = now_ist()
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S IST')

# Configure logging for Railway (write to stdout) with IST timestamps
ist_formatter = ISTFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(ist_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler]
)

# Logger
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="TradiqAI Dashboard")

# ── Dividend Radar Engine (DRE) ─────────────────────────────────
def _get_dre_db():
    """Raw psycopg connection for DRE routes (cursor API)."""
    try:
        import psycopg2 as _pg  # type: ignore[import]
    except ImportError:
        import psycopg as _pg  # psycopg v3 (installed as psycopg[binary])
    conn = _pg.connect(os.environ.get("DATABASE_URL", ""))
    try:
        yield conn
    finally:
        conn.close()

try:
    from dividend_scheduler import register_dre_routes
    from tradiqai_supabase_auth import get_current_user as _dre_get_user
    register_dre_routes(app, _get_dre_db, _dre_get_user)
    logger.info("✅ DRE API routes registered (JWT protected)")
except Exception as _dre_err:
    logger.warning(f"⚠️ DRE routes not loaded: {_dre_err}")

@app.get("/dividend-radar")
async def dividend_radar_page():
    """Serve the Dividend Radar Engine dashboard (auth enforced client-side)."""
    try:
        with open("templates/dividend_radar.html", "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(
            content=html,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"}
        )
    except FileNotFoundError:
        return HTMLResponse("<h2>Dividend Radar template not found.</h2>", status_code=404)

# ── Zerodha Kite Connect OAuth ───────────────────────────────────────
@app.get("/api/kite/auth")
async def kite_auth():
    """Redirect to Zerodha login to start OAuth flow."""
    try:
        from kite_client import get_kite
        kite = get_kite()
        if not kite.api_key:
            return JSONResponse(
                {"error": "KITE_API_KEY not set in Railway environment"},
                status_code=503,
            )
        return HTMLResponse(
            f'<html><head><meta http-equiv="refresh" content="0;url={kite.login_url}"></head>'
            f'<body>Redirecting to Zerodha Kite login...</body></html>'
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/kite/callback")
async def kite_callback(request_token: str = None, status: str = None, message: str = None):
    """
    Zerodha redirects here after login.
    Exchanges request_token → access_token, stores in Supabase.
    """
    if status != "success" or not request_token:
        return HTMLResponse(
            f"<h2>Kite login failed</h2><p>{message or 'Unknown error'}</p>",
            status_code=400,
        )
    try:
        from kite_client import get_kite, save_token_to_db
        kite  = get_kite()
        token = kite.generate_session(request_token)

        # Persist token to Supabase so it survives scheduler restarts
        try:
            db_gen = _get_dre_db()
            conn   = next(db_gen)
            save_token_to_db(conn, token)
            try:
                next(db_gen)
            except StopIteration:
                pass
        except Exception as _db_err:
            logger.warning(f"Kite token DB save failed: {_db_err}")

        return HTMLResponse(f"""
        <html><body style="font-family:monospace;background:#0d1117;color:#e6edf3;padding:40px">
          <h2>✅ Kite Connected</h2>
          <p>Access token stored in Supabase.</p>
          <p>Also add this to <strong>Railway → Variables</strong> for persistence across restarts:</p>
          <pre style="background:#161b22;padding:16px;border-radius:8px">KITE_ACCESS_TOKEN={token}</pre>
          <p><a href="/dividend-radar" style="color:#00c4ff">→ Open Dividend Radar</a></p>
        </body></html>
        """)
    except Exception as exc:
        logger.error(f"Kite callback error: {exc}")
        return HTMLResponse(f"<h2>Error: {exc}</h2>", status_code=500)


@app.get("/api/kite/status")
async def kite_status():
    """Check if Kite is connected and token is valid."""
    try:
        from kite_client import get_kite
        kite = get_kite()
        if not kite.is_configured:
            return JSONResponse({"connected": False, "reason": "KITE_API_KEY or KITE_ACCESS_TOKEN not set"})
        # Quick ping — fetch profile
        resp = kite._session.get(
            "https://api.kite.trade/user/profile",
            headers=kite._auth(),
            timeout=5,
        )
        if resp.status_code == 200:
            name = resp.json().get("data", {}).get("user_name", "")
            return JSONResponse({"connected": True, "user": name})
        return JSONResponse({"connected": False, "reason": f"HTTP {resp.status_code}"})
    except Exception as exc:
        return JSONResponse({"connected": False, "reason": str(exc)})
# ────────────────────────────────────────────────────────────────────

# Quote cache (symbol -> {data, timestamp})
quote_cache = {}
QUOTE_CACHE_TTL = 30  # seconds

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Initialize broker
broker = None

# Initialize news system
news_ingestion = None
news_detector = None
news_polling_task = None

# Background sync task
broker_sync_task = None

async def init_broker():
    global broker
    if broker is None:
        broker_config = {
            "api_key": config.groww_api_key,
            "api_secret": config.groww_api_secret,
            "api_url": config.groww_api_url
        }
        broker = GrowwBroker(broker_config)
        await broker.connect()

async def init_news_system():
    global news_ingestion, news_detector, news_polling_task
    if news_ingestion is None:
        news_ingestion = get_news_ingestion_layer()
        news_detector = NewsImpactDetector()
        print("✅ News system initialized for dashboard")
    
    # NOTE: Dashboard does NOT start polling to avoid duplicate NSE requests
    # Main trading system handles polling - dashboard just displays
    # If you want independent polling, uncomment below (may hit rate limits):
    # if news_polling_task is None:
    #     news_polling_task = asyncio.create_task(news_ingestion.start_polling())
    #     print("📡 News polling started for dashboard")


def is_market_open() -> bool:
    """Check if market is currently open (9:15 AM - 3:30 PM IST)"""
    current_time = now_ist()
    # Market hours: 9:15 AM to 3:30 PM IST
    market_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
    
    # Check if it's a weekday (Monday=0, Sunday=6)
    is_weekday = current_time.weekday() < 5
    
    return is_weekday and market_open <= current_time <= market_close


async def sync_broker_data():
    """Sync positions and orders from broker to database"""
    try:
        await init_broker()
        if not broker:
            logger.warning("⚠️ Broker not connected, skipping sync")
            return
        
        from tradiqai_supabase_config import get_supabase_admin
        supabase = get_supabase_admin()
        
        # Get user (assuming single user for now - can be extended for multi-user)
        users_result = supabase.table("users").select("id").limit(1).execute()
        if not users_result.data:
            logger.warning("⚠️ No users found, skipping sync")
            return
        
        user_id = users_result.data[0].get("id")
        
        # Fetch current positions from broker
        logger.info("📊 Syncing broker positions...")
        positions = await broker.get_positions()
        
        # Track symbols with open positions in broker
        broker_symbols = set()
        
        if positions:
            # Update positions in database
            for position in positions:
                broker_symbols.add(position.symbol)
                
                # Get current quote for P&L calculation
                try:
                    quote = await broker.get_quote(position.symbol)
                    current_price = quote.ltp if quote else position.average_price
                except:
                    current_price = position.average_price
                
                # Check if position already exists in database
                existing = supabase.table("trades").select(
                    "id, entry_price, quantity, side"
                ).eq("symbol", position.symbol).eq("user_id", user_id).eq("status", "OPEN").execute()
                
                if existing.data:
                    # UPDATE existing trade with current data
                    trade = existing.data[0]
                    entry_price = trade.get("entry_price", position.average_price)
                    quantity = trade.get("quantity", abs(position.quantity))
                    side = trade.get("side", "BUY")
                    
                    # Calculate unrealized P&L
                    if side == "BUY":
                        pnl = (current_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - current_price) * quantity
                    
                    # Update with latest data (but keep original entry_price)
                    update_data = {
                        "quantity": abs(position.quantity),  # Update quantity if changed
                    }
                    
                    supabase.table("trades").update(update_data).eq("id", trade.get("id")).execute()
                    logger.info(f"  🔄 Updated position: {position.symbol} (P&L: ₹{pnl:.2f})")
                    
                else:
                    # CREATE new trade record for this position
                    trade_data = {
                        "user_id": user_id,
                        "symbol": position.symbol,
                        "side": "BUY" if position.quantity > 0 else "SELL",
                        "entry_price": position.average_price,
                        "quantity": abs(position.quantity),
                        "entry_timestamp": now_ist().isoformat(),
                        "status": "OPEN"
                    }
                    supabase.table("trades").insert(trade_data).execute()
                    logger.info(f"  ✅ Added position: {position.symbol} x {position.quantity}")
        
        # Check for closed positions (in DB but not in broker)
        logger.info("🔍 Checking for closed positions...")
        open_trades = supabase.table("trades").select("id, symbol, entry_price, quantity, side").eq(
            "user_id", user_id
        ).eq("status", "OPEN").execute()
        
        if open_trades.data:
            for trade in open_trades.data:
                symbol = trade.get("symbol")
                if symbol not in broker_symbols:
                    # Position closed - get current price and mark as closed
                    try:
                        quote = await broker.get_quote(symbol)
                        exit_price = quote.ltp if quote else trade.get("entry_price")
                    except:
                        exit_price = trade.get("entry_price")
                    
                    # Calculate realized P&L
                    entry_price = trade.get("entry_price", 0)
                    quantity = trade.get("quantity", 0)
                    side = trade.get("side", "BUY")
                    
                    if side == "BUY":
                        pnl = (exit_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - exit_price) * quantity
                    
                    # Update trade as CLOSED
                    supabase.table("trades").update({
                        "status": "CLOSED",
                        "exit_price": exit_price,
                        "exit_timestamp": now_ist().isoformat()
                    }).eq("id", trade.get("id")).execute()
                    
                    logger.info(f"  ❌ Closed position: {symbol} (Realized P&L: ₹{pnl:.2f})")
        
        # Fetch today's orders and update status
        logger.info("📋 Syncing order status...")
        orders = await broker.get_orders()
        
        if orders:
            for order in orders:
                # Update trade status if order is completed/rejected
                if hasattr(order, 'order_id') and order.order_id:
                    existing_trade = supabase.table("trades").select("id, status").eq(
                        "broker_order_id", order.order_id
                    ).execute()
                    
                    if existing_trade.data:
                        trade = existing_trade.data[0]
                        old_status = trade.get("status")
                        new_status = order.status.upper() if hasattr(order, 'status') else "OPEN"
                        
                        if old_status != new_status:
                            # Update status and add filled data if available
                            update_data = {"status": new_status}
                            
                            # Add execution details if order is filled
                            if new_status in ("COMPLETED", "COMPLETE", "FILLED"):
                                if hasattr(order, 'average_price') and order.average_price:
                                    update_data["entry_price"] = order.average_price
                                if hasattr(order, 'filled_quantity') and order.filled_quantity:
                                    update_data["quantity"] = order.filled_quantity
                            
                            supabase.table("trades").update(update_data).eq(
                                "id", trade.get("id")
                            ).execute()
                            logger.info(f"  ✅ Updated {order.order_id}: {old_status} → {new_status}")
        
        logger.info("✅ Broker sync complete")
        
    except Exception as e:
        logger.error(f"❌ Broker sync error: {e}", exc_info=True)


async def broker_sync_loop():
    """Background task to sync broker data periodically"""
    logger.info("🔄 Starting broker sync loop...")
    
    while True:
        try:
            # Sync broker data
            await sync_broker_data()
            
            # Determine sleep interval based on market hours
            if is_market_open():
                sleep_seconds = 5 * 60  # 5 minutes during market hours
                logger.info(f"💤 Next sync in 5 minutes (market open)")
            else:
                sleep_seconds = 60 * 60  # 1 hour outside market hours
                logger.info(f"💤 Next sync in 1 hour (market closed)")
            
            await asyncio.sleep(sleep_seconds)
            
        except asyncio.CancelledError:
            logger.info("🛑 Broker sync loop cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error in broker sync loop: {e}", exc_info=True)
            # Wait 5 minutes before retrying on error
            await asyncio.sleep(5 * 60)


# ============================================================================
# Startup Event
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on app startup"""
    global broker_sync_task
    
    logger.info("🚀 Starting TradiqAI Dashboard...")
    
    # Initialize database connection and create tables
    try:
        from database import get_engine, init_db
        engine = get_engine()
        logger.info("✅ Database connection established")
        
        # Create all tables if they don't exist
        try:
            init_db()
            logger.info("✅ Database tables initialized")
        except Exception as init_error:
            # Ignore errors about existing types/tables (safe to continue)
            if "already exists" in str(init_error) or "duplicate key" in str(init_error):
                logger.info("ℹ️  Database schema already exists (skipping creation)")
            else:
                raise  # Re-raise other errors
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        logger.warning("⚠️  Some features may be unavailable")
    
    # Start background broker sync task
    if broker_sync_task is None:
        broker_sync_task = asyncio.create_task(broker_sync_loop())
        logger.info("✅ Broker sync task started (5min market hours, 1hr otherwise)")

    # Start DRE background scheduler (runs at 6:30 AM IST daily)
    try:
        from dividend_scheduler import DividendRadarScheduler
        _dre = DividendRadarScheduler()
        _dre.start_background()
        logger.info("✅ DRE background scheduler started (6:30 AM IST daily)")
    except Exception as _e:
        logger.warning(f"⚠️ DRE scheduler not started: {_e}")

    # Load Kite access_token from Supabase (if previously stored via /api/kite/callback)
    try:
        from kite_client import load_token_from_db
        _db_gen = _get_dre_db()
        _conn   = next(_db_gen)
        load_token_from_db(_conn)
        try:
            next(_db_gen)
        except StopIteration:
            pass
    except Exception as _ke:
        logger.debug(f"Kite token not pre-loaded: {_ke}")

    logger.info("✅ Dashboard startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on app shutdown"""
    global broker_sync_task
    
    logger.info("🛑 Shutting down TradiqAI Dashboard...")
    
    # Cancel broker sync task
    if broker_sync_task:
        broker_sync_task.cancel()
        try:
            await broker_sync_task
        except asyncio.CancelledError:
            pass
        logger.info("✅ Broker sync task stopped")
    
    logger.info("✅ Dashboard shutdown complete")


# ============================================================================
# Authentication Routes
# ============================================================================

@app.post("/api/auth/register")
async def register(user_create: UserRegister):
    """Register a new user with Supabase Auth"""
    try:
        result = await auth_manager.register_user(user_create)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@app.post("/api/auth/login", response_model=Token)
async def login(user_login: UserLogin):
    """Login with Supabase Auth and get access token"""
    try:
        token_data = await auth_manager.login_user(user_login)
        return token_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(refresh_request: dict):
    """Refresh access token using refresh token"""
    try:
        refresh_token = refresh_request.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="refresh_token is required"
            )
        
        token_data = await auth_manager.refresh_token(refresh_token)
        return token_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=401, detail="Token refresh failed")


@app.get("/api/auth/me")
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """Get current user information from Supabase"""
    return current_user


@app.put("/api/auth/me/capital")
async def update_capital(
    capital: float,
    current_user: Dict = Depends(get_current_user)
):
    """Update user's trading capital"""
    user_id = current_user["id"]
    await auth_manager.update_user_settings(user_id, {"capital": capital})
    return {"message": "Capital updated", "capital": capital}


@app.put("/api/auth/me/paper-trading")
async def toggle_paper_trading(
    paper_trading: bool,
    current_user: Dict = Depends(get_current_user)
):
    """Toggle paper trading mode"""
    user_id = current_user["id"]
    await auth_manager.update_user_settings(user_id, {"paper_trading": paper_trading})
    return {"message": "Paper trading mode updated", "paper_trading": paper_trading}


# Dashboard HTML
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TradiqAI - Live Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .status {
            display: flex;
            gap: 20px;
            align-items: center;
        }
        
        .status-badge {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
        }
        
        .status-live {
            background: #10b981;
            color: white;
        }
        
        .status-closed {
            background: #ef4444;
            color: white;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 18px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding: 8px;
            background: #f9fafb;
            border-radius: 5px;
        }
        
        .metric-label {
            color: #6b7280;
            font-size: 14px;
        }
        
        .metric-value {
            font-weight: bold;
            font-size: 16px;
        }
        
        .positive {
            color: #10b981;
        }
        
        .negative {
            color: #ef4444;
        }
        
        .neutral {
            color: #6b7280;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            background: #667eea;
            color: white;
            padding: 10px;
            text-align: left;
            font-size: 14px;
        }
        
        td {
            padding: 10px;
            border-bottom: 1px solid #e5e7eb;
            font-size: 13px;
        }
        
        tr:hover {
            background: #f9fafb;
        }
        
        .empty-state {
            text-align: center;
            padding: 30px;
            color: #9ca3af;
        }
        
        .refresh-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #10b981;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.3;
            }
        }
        
        .timestamp {
            color: #9ca3af;
            font-size: 12px;
        }
        
        .large-value {
            font-size: 32px;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
        }
        
        .trade-buy {
            color: #10b981;
            font-weight: bold;
        }
        
        .trade-sell {
            color: #ef4444;
            font-weight: bold;
        }
        
        .position-open {
            background: #dbeafe;
            color: #1e40af;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
        }
        
        .position-closed {
            background: #e5e7eb;
            color: #6b7280;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
        }
        
        .stock-momentum {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .momentum-high {
            background: #dcfce7;
            color: #166534;
        }
        
        .momentum-moderate {
            background: #fef3c7;
            color: #92400e;
        }
        
        .momentum-low {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .stock-symbol {
            font-weight: bold;
            color: #1f2937;
        }
        
        /* News Feed Styles */
        .news-item {
            padding: 12px;
            border-left: 4px solid #e5e7eb;
            margin-bottom: 10px;
            background: #f9fafb;
            border-radius: 5px;
        }
        
        .news-item-trade {
            border-left-color: #10b981;
            background: #ecfdf5;
        }
        
        .news-item-watch {
            border-left-color: #f59e0b;
            background: #fffbeb;
        }
        
        .news-item-ignore {
            border-left-color: #9ca3af;
            background: #f9fafb;
        }
        
        .news-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .news-symbol {
            font-weight: bold;
            color: #1f2937;
            font-size: 14px;
        }
        
        .news-score {
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .news-score-trade {
            background: #10b981;
            color: white;
        }
        
        .news-score-watch {
            background: #f59e0b;
            color: white;
        }
        
        .news-score-ignore {
            background: #9ca3af;
            color: white;
        }
        
        .news-headline {
            font-size: 13px;
            color: #374151;
            margin-bottom: 6px;
            line-height: 1.4;
        }
        
        .news-meta {
            display: flex;
            gap: 15px;
            font-size: 11px;
            color: #6b7280;
        }
        
        .news-direction {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
        }
        
        .news-direction-bullish {
            background: #dcfce7;
            color: #166534;
        }
        
        .news-direction-bearish {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .news-direction-neutral {
            background: #f3f4f6;
            color: #6b7280;
        }
        
        .news-empty {
            text-align: center;
            padding: 20px;
            color: #9ca3af;
            font-size: 13px;
        }
        
        /* Trading Panel Styles */
        .trade-panel {
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
        }
        
        .trade-form {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        .form-group label {
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 5px;
            font-weight: 600;
        }
        
        .form-group input, .form-group select {
            padding: 10px;
            border: 2px solid #e5e7eb;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.2s;
        }
        
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .trade-buttons {
            grid-column: 1 / -1;
            display: flex;
            gap: 10px;
        }
        
        .btn {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-buy {
            background: #10b981;
            color: white;
        }
        
        .btn-buy:hover {
            background: #059669;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
        }
        
        .btn-sell {
            background: #ef4444;
            color: white;
        }
        
        .btn-sell:hover {
            background: #dc2626;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(239, 68, 68, 0.3);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-small {
            padding: 6px 12px;
            font-size: 12px;
            margin: 0 3px;
        }
        
        .action-buttons {
            white-space: nowrap;
        }
        
        .alert {
            padding: 10px;
            border-radius: 6px;
            margin-top: 10px;
            font-size: 13px;
        }
        
        .alert-success {
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
        }
        
        .alert-error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }
        
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgba(0, 0, 0, 0.5);
            animation: fadeIn 0.3s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .modal-content {
            background-color: #ffffff;
            margin: 5% auto;
            border-radius: 12px;
            width: 90%;
            max-width: 600px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            animation: slideDown 0.3s;
        }
        
        @keyframes slideDown {
            from {
                transform: translateY(-50px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }
        
        .modal-header {
            padding: 20px 25px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px 12px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-header h2 {
            margin: 0;
            font-size: 20px;
        }
        
        .close {
            color: white;
            font-size: 32px;
            font-weight: bold;
            cursor: pointer;
            line-height: 1;
            transition: transform 0.2s;
        }
        
        .close:hover,
        .close:focus {
            transform: rotate(90deg);
        }
        
        .modal-body {
            padding: 25px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h1>🚀 TradiqAI - Live Dashboard</h1>
                <div style="display: flex; align-items: center; gap: 15px;">
                    <span id="userInfo" style="color: #667eea; font-weight: bold;"></span>
                    <a href="/dividend-radar" style="padding: 8px 16px; background: #10b981; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;">📡 Dividend Radar</a>
                    <button onclick="logout()" style="padding: 8px 16px; background: #ef4444; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">🔓 Logout</button>
                </div>
            </div>
            <div class="status">
                <span class="status-badge" id="marketStatus">Market Closed</span>
                <span class="refresh-indicator"></span>
                <span class="timestamp" id="lastUpdate">Connecting...</span>
            </div>
        </div>
        
        <!-- Key Metrics -->
        <div class="grid">
            <div class="card">
                <h2>💰 Account</h2>
                <div class="metric">
                    <span class="metric-label">Available Capital</span>
                    <span class="metric-value" id="capital">₹0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Margin Used</span>
                    <span class="metric-value" id="marginUsed">₹0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Exposure</span>
                    <span class="metric-value" id="exposure">0%</span>
                </div>
            </div>
            
            <div class="card">
                <h2>📊 Today's Performance</h2>
                <div class="large-value" id="todayPnL">₹0.00</div>
                <div class="metric">
                    <span class="metric-label">Trades Executed</span>
                    <span class="metric-value" id="tradesCount">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Win Rate</span>
                    <span class="metric-value" id="winRate">0%</span>
                </div>
            </div>
            
            <div class="card">
                <h2>⚡ System Status</h2>
                <div class="metric">
                    <span class="metric-label">Open Positions</span>
                    <span class="metric-value" id="openPositions">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Active Signals</span>
                    <span class="metric-value" id="activeSignals">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Strategy</span>
                    <span class="metric-value">Live Simple</span>
                </div>
            </div>
        </div>
        
        <!-- Monitored Stocks -->
        <div class="card">
            <h2>👁️ Monitored Stocks</h2>
            <div id="monitoredStocksTable">
                <div class="empty-state">Loading stocks...</div>
            </div>
        </div>
        
        <!-- Positions -->
        <div class="card">
            <h2>📈 Active Positions</h2>
            <div id="positionsTable">
                <div class="empty-state">No active positions</div>
            </div>
        </div>
        
        <!-- Recent Trades -->
        <div class="card">
            <h2>📝 Recent Trades (Last 10)</h2>
            <div id="tradesTable">
                <div class="empty-state">No trades yet</div>
            </div>
        </div>
        
        <!-- News Feed -->
        <div class="card">
            <h2>📰 News Feed</h2>
            <div id="newsFeed">
                <div class="news-empty">Loading news feed...</div>
            </div>
        </div>
    </div>
    
    <!-- Trade Modal -->
    <div id="tradeModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modalTitle">💹 Place Order</h2>
                <span class="close" onclick="closeTradeModal()">&times;</span>
            </div>
            <div class="modal-body">
                <form class="trade-form" id="tradeForm">
                    <div class="form-group">
                        <label for="symbol">Symbol</label>
                        <input type="text" id="symbol" name="symbol" placeholder="e.g., RELIANCE" required readonly>
                    </div>
                    
                    <div class="form-group">
                        <label for="currentPrice">Current Price</label>
                        <input type="text" id="currentPrice" name="currentPrice" readonly>
                    </div>
                    
                    <div class="form-group">
                        <label for="quantity">Quantity</label>
                        <input type="number" id="quantity" name="quantity" min="1" value="1" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="orderType">Order Type</label>
                        <select id="orderType" name="orderType">
                            <option value="MARKET">Market</option>
                            <option value="LIMIT">Limit</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="price">Price (Limit orders)</label>
                        <input type="number" id="price" name="price" step="0.05" placeholder="Optional">
                    </div>
                    
                    <div class="form-group">
                        <label for="product">Product Type</label>
                        <select id="product" name="product">
                            <option value="MIS">MIS (Intraday)</option>
                            <option value="CNC">CNC (Delivery)</option>
                        </select>
                    </div>
                    
                    <div class="trade-buttons">
                        <button type="button" class="btn btn-buy" id="modalBuyBtn" onclick="placeTrade('BUY')">🟢 BUY</button>
                        <button type="button" class="btn btn-sell" id="modalSellBtn" onclick="placeTrade('SELL')">🔴 SELL</button>
                    </div>
                </form>
                <div id="tradeAlert"></div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let currentTradeAction = null;
        
        // Check authentication on page load
        function checkAuth() {
            const token = localStorage.getItem('access_token');
            if (!token) {
                console.log('[Auth] No token found, redirecting to login');
                window.location.href = '/login';
                return false;
            }
            return true;
        }
        
        // Get current user info
        async function getUserInfo() {
            const token = await getValidToken();
            if (!token) return;
            
            try {
                const response = await fetch('/api/auth/me', {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                
                if (response.ok) {
                    const user = await response.json();
                    document.getElementById('userInfo').textContent = `👤 ${user.username} | Capital: ₹${user.capital.toLocaleString()}`;
                } else if (response.status === 401) {
                    // Token expired or invalid - try refreshing
                    console.log('[Auth] Token expired, attempting refresh...');
                    const newToken = await refreshAccessToken();
                    if (newToken) {
                        // Retry with new token
                        getUserInfo();
                    }
                }
            } catch (error) {
                console.error('[Auth] Error fetching user info:', error);
            }
        }
        
        // Logout function
        function logout() {
            console.log('[Auth] Logging out');
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            if (ws) {
                ws.close();
            }
            window.location.href = '/login';
        }
        
        async function placeTrade(side) {
            const form = document.getElementById('tradeForm');
            const buyBtn = document.getElementById('modalBuyBtn');
            const sellBtn = document.getElementById('modalSellBtn');
            
            // Get form values
            const symbol = document.getElementById('symbol').value.trim().toUpperCase();
            const quantity = parseInt(document.getElementById('quantity').value);
            const orderType = document.getElementById('orderType').value;
            const price = parseFloat(document.getElementById('price').value) || null;
            const product = document.getElementById('product').value;
            
            // Validation
            if (!symbol) {
                showAlert('Please enter a symbol', 'error');
                return;
            }
            
            if (!quantity || quantity < 1) {
                showAlert('Quantity must be at least 1', 'error');
                return;
            }
            
            if (orderType === 'LIMIT' && (!price || price <= 0)) {
                showAlert('Please enter a valid price for limit order', 'error');
                return;
            }
            
            // Disable buttons
            buyBtn.disabled = true;
            sellBtn.disabled = true;
            
            try {
                // Get valid token (refresh if needed)
                const token = await getValidToken();
                if (!token) {
                    showAlert('❌ Authentication failed. Please login again.', 'error');
                    return;
                }
                
                const response = await fetch('/api/place_order', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        symbol: symbol,
                        side: side,
                        quantity: quantity,
                        order_type: orderType,
                        price: price,
                        product: product
                    })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showAlert(`✅ ${side} order placed successfully! Order ID: ${result.order_id}`, 'success');
                    // Clear form and close modal after 2 seconds
                    setTimeout(() => {
                        form.reset();
                        closeTradeModal();
                    }, 2000);
                } else {
                    showAlert(`❌ Error: ${result.detail || 'Failed to place order'}`, 'error');
                }
            } catch (error) {
                showAlert(`❌ Error: ${error.message}`, 'error');
            } finally {
                // Re-enable buttons
                buyBtn.disabled = false;
                sellBtn.disabled = false;
            }
        }
        
        function showAlert(message, type) {
            const alertDiv = document.getElementById('tradeAlert');
            alertDiv.className = `alert alert-${type}`;
            alertDiv.textContent = message;
            alertDiv.style.display = 'block';
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                alertDiv.style.display = 'none';
            }, 5000);
        }
        
        // Quick trade from monitored stocks table
        async function quickTrade(symbol, side, ltp) {
            currentTradeAction = side;
            
            // Auto-fill the form
            document.getElementById('symbol').value = symbol;
            document.getElementById('currentPrice').value = `₹${ltp.toFixed(2)}`;
            document.getElementById('quantity').value = 1;
            document.getElementById('orderType').value = 'MARKET';
            document.getElementById('price').value = '';
            document.getElementById('product').value = 'MIS';
            
            // Update modal title and button visibility
            document.getElementById('modalTitle').textContent = `${side} ${symbol}`;
            document.getElementById('modalBuyBtn').style.display = side === 'BUY' ? 'block' : 'none';
            document.getElementById('modalSellBtn').style.display = side === 'SELL' ? 'block' : 'none';
            
            // Show modal
            document.getElementById('tradeModal').style.display = 'block';
        }
        
        function closeTradeModal() {
            document.getElementById('tradeModal').style.display = 'none';
            document.getElementById('tradeAlert').innerHTML = '';
            currentTradeAction = null;
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('tradeModal');
            if (event.target == modal) {
                closeTradeModal();
            }
        }
        
        // ============================================================================
        // Token Management
        // ============================================================================
        
        // Decode JWT token and extract expiration time
        function decodeJWT(token) {
            try {
                const base64Url = token.split('.')[1];
                const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
                    return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
                }).join(''));
                return JSON.parse(jsonPayload);
            } catch (error) {
                console.error('[Auth] Error decoding JWT:', error);
                return null;
            }
        }
        
        // Check if token is expired or expiring soon (within 5 minutes)
        function isTokenExpiringSoon(token) {
            const decoded = decodeJWT(token);
            if (!decoded || !decoded.exp) {
                return true; // Assume expired if can't decode
            }
            
            const expirationTime = decoded.exp * 1000; // Convert to milliseconds
            const currentTime = Date.now();
            const fiveMinutes = 5 * 60 * 1000;
            
            // Token expires soon if it expires within 5 minutes
            return (expirationTime - currentTime) < fiveMinutes;
        }
        
        // Refresh the access token using refresh_token
        async function refreshAccessToken() {
            const refreshToken = localStorage.getItem('refresh_token');
            if (!refreshToken) {
                console.error('[Auth] No refresh token found');
                window.location.href = '/login';
                return null;
            }
            
            try {
                console.log('[Auth] Refreshing access token...');
                const response = await fetch('/api/auth/refresh', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ refresh_token: refreshToken })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    localStorage.setItem('access_token', data.access_token);
                    if (data.refresh_token) {
                        localStorage.setItem('refresh_token', data.refresh_token);
                    }
                    console.log('[Auth] ✅ Token refreshed successfully');
                    return data.access_token;
                } else {
                    console.error('[Auth] Failed to refresh token, status:', response.status);
                    // Refresh token expired or invalid - redirect to login
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('refresh_token');
                    window.location.href = '/login';
                    return null;
                }
            } catch (error) {
                console.error('[Auth] Error refreshing token:', error);
                window.location.href = '/login';
                return null;
            }
        }
        
        // Get valid token (refresh if needed)
        async function getValidToken() {
            let token = localStorage.getItem('access_token');
            
            if (!token) {
                console.error('[Auth] No access token found');
                window.location.href = '/login';
                return null;
            }
            
            // Check if token is expired or expiring soon
            if (isTokenExpiringSoon(token)) {
                console.log('[Auth] Token expiring soon, refreshing...');
                token = await refreshAccessToken();
            }
            
            return token;
        }
        
        // ============================================================================
        // WebSocket Connection with Token Refresh
        // ============================================================================
        
        async function connect() {
            // Get valid token (refresh if needed)
            const token = await getValidToken();
            if (!token) {
                console.error('[WebSocket] No valid auth token found');
                return;
            }
            
            // Use wss:// for HTTPS (production), ws:// for HTTP (localhost)
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${window.location.host}/ws?token=${token}`;
            console.log('[WebSocket] Attempting to connect to', wsUrl);
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('[WebSocket] ✅ Connected successfully!');
                document.getElementById('lastUpdate').textContent = 'Connected';
                document.getElementById('lastUpdate').style.color = 'green';
            };
            
            ws.onmessage = (event) => {
                console.log('[WebSocket] 📦 Received message, size:', event.data.length, 'bytes');
                try {
                    const data = JSON.parse(event.data);
                    console.log('[WebSocket] ✅ Parsed data:', {
                        account: data.account ? 'present' : 'missing',
                        positions: data.positions ? data.positions.length : 0,
                        trades: data.trades ? data.trades.length : 0,
                        stocks: data.monitored_stocks ? data.monitored_stocks.length : 0,
                        news: data.news_feed ? data.news_feed.length : 0
                    });
                    updateDashboard(data);
                    console.log('[WebSocket] ✅ Dashboard updated');
                } catch (e) {
                    console.error('[WebSocket] ❌ Error parsing/updating:', e);
                }
            };
            
            ws.onclose = (event) => {
                console.warn('[WebSocket] ⚠️ Connection closed, code:', event.code, 'reason:', event.reason);
                document.getElementById('lastUpdate').textContent = 'Reconnecting...';
                document.getElementById('lastUpdate').style.color = 'orange';
                
                // If closed due to auth failure (403), refresh token and reconnect
                if (event.code === 1008 || event.reason.includes('403') || event.reason.includes('auth')) {
                    console.log('[WebSocket] Auth failure detected, refreshing token...');
                    setTimeout(async () => {
                        await refreshAccessToken();
                        connect();
                    }, 1000);
                } else {
                    // Normal reconnection
                    setTimeout(connect, 3000);
                }
            };
            
            ws.onerror = (error) => {
                console.error('[WebSocket] ❌ Error:', error);
                document.getElementById('lastUpdate').textContent = 'Error';
                document.getElementById('lastUpdate').style.color = 'red';
            };
        }
        
        function updateDashboard(data) {
            console.log('[Dashboard] Starting update with data:', data);
            
            // Update timestamp
            const now = new Date().toLocaleTimeString();
            console.log('[Dashboard] Setting timestamp:', now);
            document.getElementById('lastUpdate').textContent = now;
            document.getElementById('lastUpdate').style.color = 'black';
            
            // Update market status
            console.log('[Dashboard] Updating market status:', data.market_open);
            const statusBadge = document.getElementById('marketStatus');
            if (data.market_open) {
                statusBadge.className = 'status-badge status-live';
                statusBadge.textContent = 'Market Open';
            } else {
                statusBadge.className = 'status-badge status-closed';
                statusBadge.textContent = 'Market Closed';
            }
            
            // Update account metrics
            console.log('[Dashboard] Updating account:', data.account);
            if (data.account) {
                document.getElementById('capital').textContent = 
                    '₹' + data.account.capital.toFixed(2);
                document.getElementById('marginUsed').textContent = 
                    '₹' + data.account.margin_used.toFixed(2);
                document.getElementById('exposure').textContent = 
                    data.account.exposure.toFixed(1) + '%';
            }
            
            // Update performance
            console.log('[Dashboard] Updating performance:', data.performance);
            if (data.performance) {
                const pnlElement = document.getElementById('todayPnL');
                const pnl = data.performance.today_pnl;
                pnlElement.textContent = '₹' + pnl.toFixed(2);
                pnlElement.className = pnl >= 0 ? 'large-value positive' : 'large-value negative';
                
                document.getElementById('tradesCount').textContent = 
                    data.performance.trades_count;
                document.getElementById('winRate').textContent = 
                    data.performance.win_rate.toFixed(1) + '%';
            }
            
            // Update system status
            console.log('[Dashboard] Updating system status');
            document.getElementById('openPositions').textContent = 
                data.positions ? data.positions.length : 0;
            document.getElementById('activeSignals').textContent = 
                data.signals || 0;
            
            // Update positions table
            console.log('[Dashboard] Updating positions table:', data.positions ? data.positions.length : 0, 'positions');
            updatePositionsTable(data.positions);
            
            // Update trades table
            console.log('[Dashboard] Updating trades table:', data.trades ? data.trades.length : 0, 'trades');
            updateTradesTable(data.trades);
            
            // Update monitored stocks
            console.log('[Dashboard] Updating monitored stocks:', data.monitored_stocks ? data.monitored_stocks.length : 0, 'stocks');
            updateMonitoredStocks(data.monitored_stocks);
            
            // Update news feed
            console.log('[Dashboard] Updating news feed:', data.news_feed ? data.news_feed.length : 0, 'items');
            updateNewsFeed(data.news_feed);
            
            console.log('[Dashboard] ✅ Update complete!');
        }
        
        function updatePositionsTable(positions) {
            const container = document.getElementById('positionsTable');
            
            if (!positions || positions.length === 0) {
                container.innerHTML = '<div class="empty-state">No active positions</div>';
                return;
            }
            
            let html = '<table><thead><tr>';
            html += '<th>Symbol</th><th>Side</th><th>Qty</th><th>Avg Price</th>';
            html += '<th>LTP</th><th>P&L</th><th>Status</th></tr></thead><tbody>';
            
            positions.forEach(pos => {
                const pnl = pos.unrealized_pnl || 0;
                const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                
                html += '<tr>';
                html += `<td><strong>${pos.symbol}</strong></td>`;
                html += `<td class="${pos.side === 'BUY' ? 'trade-buy' : 'trade-sell'}">${pos.side}</td>`;
                html += `<td>${pos.quantity}</td>`;
                html += `<td>₹${pos.average_price.toFixed(2)}</td>`;
                html += `<td>₹${(pos.current_price || 0).toFixed(2)}</td>`;
                html += `<td class="${pnlClass}">₹${pnl.toFixed(2)}</td>`;
                html += `<td><span class="position-open">OPEN</span></td>`;
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        function updateTradesTable(trades) {
            const container = document.getElementById('tradesTable');
            
            if (!trades || trades.length === 0) {
                container.innerHTML = '<div class="empty-state">No trades yet</div>';
                return;
            }
            
            let html = '<table><thead><tr>';
            html += '<th>Time</th><th>Symbol</th><th>Side</th><th>Qty</th>';
            html += '<th>Price</th><th>P&L</th><th>Status</th></tr></thead><tbody>';
            
            trades.forEach(trade => {
                const pnl = trade.pnl || 0;
                const pnlClass = pnl >= 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral';
                
                html += '<tr>';
                html += `<td>${new Date(trade.timestamp).toLocaleTimeString()}</td>`;
                html += `<td>${trade.symbol}</td>`;
                html += `<td class="${trade.side === 'BUY' ? 'trade-buy' : 'trade-sell'}">${trade.side}</td>`;
                html += `<td>${trade.quantity}</td>`;
                html += `<td>₹${trade.price.toFixed(2)}</td>`;
                html += `<td class="${pnlClass}">₹${pnl.toFixed(2)}</td>`;
                html += `<td>${trade.status}</td>`;
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        function updateMonitoredStocks(stocks) {
            const container = document.getElementById('monitoredStocksTable');
            
            if (!stocks || stocks.length === 0) {
                container.innerHTML = '<div class="empty-state">No stocks being monitored</div>';
                return;
            }
            
            let html = '<table><thead><tr>';
            html += '<th>Symbol</th><th>LTP</th><th>Day Change</th><th>Momentum</th><th>Signal</th><th>Actions</th></tr></thead><tbody>';
            
            stocks.forEach(stock => {
                const changePercent = stock.day_change_percent || 0;
                const changeClass = changePercent >= 0 ? 'positive' : 'negative';
                const ltp = stock.ltp || 0;
                
                // Determine momentum class
                let momentumClass = 'momentum-low';
                let momentumText = 'Low';
                if (Math.abs(changePercent) >= 1.5) {
                    momentumClass = 'momentum-high';
                    momentumText = changePercent >= 0 ? 'Strong Up' : 'Strong Down';
                } else if (Math.abs(changePercent) >= 0.8) {
                    momentumClass = 'momentum-moderate';
                    momentumText = 'Moderate';
                }
                
                html += '<tr>';
                html += `<td class="stock-symbol">${stock.symbol}</td>`;
                html += `<td>₹${ltp.toFixed(2)}</td>`;
                html += `<td class="${changeClass}">${changePercent.toFixed(2)}%</td>`;
                html += `<td><span class="stock-momentum ${momentumClass}">${momentumText}</span></td>`;
                html += `<td>${stock.signal || 'No Signal'}</td>`;
                html += `<td class="action-buttons">`;
                html += `<button class="btn btn-buy btn-small" onclick="quickTrade('${stock.symbol}', 'BUY', ${ltp})">🟢 BUY</button>`;
                html += `<button class="btn btn-sell btn-small" onclick="quickTrade('${stock.symbol}', 'SELL', ${ltp})">🔴 SELL</button>`;
                html += `</td>`;
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        function updateNewsFeed(news) {
            const container = document.getElementById('newsFeed');
            
            if (!news || news.length === 0) {
                container.innerHTML = '<div class="news-empty">No news items yet. System is polling NSE announcements...</div>';
                return;
            }
            
            let html = '';
            
            news.forEach(item => {
                const actionClass = item.action.toLowerCase();
                const scoreClass = `news-score-${actionClass}`;
                const itemClass = `news-item news-item-${actionClass}`;
                
                // Direction styling
                let directionClass = 'news-direction-neutral';
                let directionText = 'NEUTRAL';
                if (item.direction) {
                    if (item.direction === 'BULLISH') {
                        directionClass = 'news-direction-bullish';
                        directionText = '📈 BULLISH';
                    } else if (item.direction === 'BEARISH') {
                        directionClass = 'news-direction-bearish';
                        directionText = '📉 BEARISH';
                    }
                }
                
                html += `<div class="${itemClass}">`;
                html += '<div class="news-header">';
                html += `<span class="news-symbol">${item.symbol}</span>`;
                html += `<span class="news-score ${scoreClass}">${item.score}/100 - ${item.action}</span>`;
                html += '</div>';
                html += `<div class="news-headline">${item.headline}</div>`;
                html += '<div class="news-meta">';
                html += `<span class="news-direction ${directionClass}">${directionText}</span>`;
                html += `<span>⏰ ${new Date(item.timestamp).toLocaleTimeString()}</span>`;
                html += `<span>📊 ${item.category || 'general'}</span>`;
                if (item.blocked_by) {
                    html += `<span>🚫 ${item.blocked_by}</span>`;
                }
                html += '</div>';
                html += '</div>';
            });
            
            container.innerHTML = html;
        }
        
        // Initialize on page load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                if (checkAuth()) {
                    getUserInfo();
                    connect();
                    
                    // Start periodic token refresh (every 30 minutes)
                    setInterval(async () => {
                        const token = localStorage.getItem('access_token');
                        if (token && isTokenExpiringSoon(token)) {
                            console.log('[Auth] Proactive token refresh...');
                            await refreshAccessToken();
                        }
                    }, 30 * 60 * 1000); // 30 minutes
                }
            });
        } else {
            // DOM already loaded
            if (checkAuth()) {
                getUserInfo();
                connect();
                
                // Start periodic token refresh (every 30 minutes)
                setInterval(async () => {
                    const token = localStorage.getItem('access_token');
                    if (token && isTokenExpiringSoon(token)) {
                        console.log('[Auth] Proactive token refresh...');
                        await refreshAccessToken();
                    }
                }, 30 * 60 * 1000); // 30 minutes
            }
        }
    </script>
</body>
</html>
"""

@app.get("/login")
async def get_login_page():
    """Serve the login page"""
    try:
        with open("templates/login.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Login page not found</h1>", status_code=500)

@app.get("/")
async def get_dashboard():
    """Serve the dashboard HTML with no-cache headers"""
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return HTMLResponse(content=HTML_TEMPLATE, headers=headers)

@app.get("/health")
async def health_check_root():
    """Health check endpoint for Railway/load balancers"""
    try:
        # Try to check database status without crashing
        db_status = "unknown"
        try:
            from database import _engine
            if _engine is None:
                db_status = "not_initialized"
            else:
                db_status = "connected"
        except:
            db_status = "unknown"
        
        return {
            "status": "healthy",
            "timestamp": now_ist().isoformat(),
            "database": db_status,
            "app": "tradiqai-dashboard"
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        # Still return healthy even if there's an error
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/api/debug/env-check")
async def env_check():
    """
    Diagnostic endpoint to check if Supabase environment variables are loaded
    SECURITY: This should be removed or protected in production!
    """
    import os
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "")
    return {
        "SUPABASE_URL": "✅ SET" if os.getenv("SUPABASE_URL") else "❌ MISSING",
        "SUPABASE_ANON_KEY": "✅ SET" if os.getenv("SUPABASE_ANON_KEY") else "❌ MISSING",
        "SUPABASE_SERVICE_KEY": "✅ SET" if service_key else "❌ MISSING",
        "SUPABASE_SERVICE_KEY_LENGTH": len(service_key),
        "SUPABASE_SERVICE_KEY_PREFIX": service_key[:20] if service_key else "MISSING",
        "SUPABASE_SERVICE_KEY_SUFFIX": service_key[-20:] if len(service_key) > 40 else "N/A",
        "SUPABASE_SERVICE_KEY_PARTS": service_key.count('.') if service_key else 0,  # JWT should have 2 dots
        "SUPABASE_SERVICE_KEY_VALID_JWT": len(service_key.split('.')) == 3 if service_key else False,
        "ENV": os.getenv("ENV", "not_set"),
        "DATABASE_URL": "✅ SET" if os.getenv("DATABASE_URL") else "❌ MISSING"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": now_ist().isoformat()}

@app.post("/api/place_order")
async def place_order(
    order_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Place a new order (protected route)"""
    try:
        logger.info(f"📝 Order request from user: {current_user.get('email', 'unknown')}")
        logger.debug(f"Order data: {order_data}")
        # Initialize broker if needed
        await init_broker()
        
        if not broker:
            return {"success": False, "detail": "Broker not connected"}
        
        # Extract order details
        symbol = order_data.get("symbol", "").upper()
        side = order_data.get("side", "BUY")  # BUY or SELL
        quantity = order_data.get("quantity", 0)
        order_type = order_data.get("order_type", "MARKET")  # MARKET or LIMIT
        price = order_data.get("price")  # Optional for MARKET orders
        product = order_data.get("product", "MIS")  # MIS or CNC
        
        # Validation
        if not symbol:
            return {"success": False, "detail": "Symbol is required"}
        
        if quantity <= 0:
            return {"success": False, "detail": "Quantity must be greater than 0"}
        
        if order_type == "LIMIT" and (not price or price <= 0):
            return {"success": False, "detail": "Price is required for limit orders"}
        
        # Import enums
        from brokers.base import TransactionType, OrderType as BrokerOrderType
        
        # Convert side to TransactionType
        transaction_type = TransactionType.BUY if side == "BUY" else TransactionType.SELL
        
        # Convert order type
        broker_order_type = BrokerOrderType.MARKET if order_type == "MARKET" else BrokerOrderType.LIMIT
        
        # Place order through broker
        logger.info(f"📝 Placing {side} order: {symbol} x {quantity} @ {order_type} ({product})")
        
        order_result = await broker.place_order(
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=broker_order_type,
            price=price,
            product=product
        )
        
        if order_result and order_result.order_id:
            logger.info(f"✅ Order placed successfully: {order_result.order_id}")
            
            # Save trade to Supabase database
            try:
                from tradiqai_supabase_config import get_supabase_admin
                supabase = get_supabase_admin()
                
                # Get current price (use price from order or fetch from broker)
                entry_price = price if price else order_result.average_price if hasattr(order_result, 'average_price') else 0.0
                
                # If still no price, try to fetch current quote
                if not entry_price:
                    try:
                        quote = await broker.get_quote(symbol)
                        entry_price = quote.ltp if quote else 0.0
                    except:
                        entry_price = 0.0
                
                # Create trade record - use only fields that exist in Supabase
                # Supabase schema: id, user_id, symbol, side, entry_price, quantity,
                # entry_timestamp, broker_order_id, status, exit_price, exit_timestamp, created_at
                trade_data = {
                    "user_id": current_user.get("id"),
                    "symbol": symbol,
                    "side": side.upper(),  # Use 'side' not 'direction'
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "entry_timestamp": now_ist().isoformat(),
                    "broker_order_id": order_result.order_id,
                    "status": "OPEN"
                }
                
                result = supabase.table("trades").insert(trade_data).execute()
                logger.info(f"💾 Trade saved to database: {result.data[0].get('id') if result.data else 'unknown'}")
                
            except Exception as db_error:
                logger.error(f"⚠️ Failed to save trade to database: {db_error}", exc_info=True)
                # Don't fail the order placement - broker order succeeded
            
            return {
                "success": True,
                "order_id": order_result.order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                "product": product
            }
        else:
            logger.error(f"❌ Order placement failed: No order ID returned")
            return {"success": False, "detail": "Order placement failed - no order ID returned"}
            
    except HTTPException:
        # Re-raise HTTP exceptions from get_current_user
        raise
    except Exception as e:
        logger.error(f"❌ Error placing order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Order placement failed: {str(e)}"
        )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    print("📡 New WebSocket connection attempt...")
    
    # Get token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        print("❌ No token provided in WebSocket connection")
        await websocket.close(code=1008)  # Policy violation
        return
    
    # Verify token and get user from Supabase
    try:
        from tradiqai_supabase_config import get_supabase_client, get_supabase_admin
        supabase = get_supabase_client()
        supabase_admin = get_supabase_admin()
        
        # Get user from Supabase using JWT token
        auth_response = supabase.auth.get_user(token)
        
        if not auth_response or not auth_response.user:
            print(f"❌ Invalid token")
            await websocket.close(code=1008)
            return
        
        user_id = auth_response.user.id
        
        # Get user profile using admin client (bypasses RLS)
        profile = supabase_admin.table("users").select("*").eq("id", user_id).execute()
        
        if not profile.data:
            print(f"❌ User profile not found: user_id={user_id}")
            await websocket.close(code=1008)
            return
        
        user = profile.data[0]
        
        # Check if user is active (default to True if not set)
        is_active = user.get("is_active", True)
        if not is_active:
            print(f"❌ User account is deactivated: user_id={user_id}")
            await websocket.close(code=1008)
            return
        
        print(f"✅ WebSocket authenticated: user_id={user_id}, username={user.get('username', 'unknown')}")
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        await websocket.close(code=1008)
        return
    
    await manager.connect(websocket)
    print("✅ WebSocket connected")
    
    try:
        # Initialize broker and news system if not already done
        print("🔧 Initializing broker...")
        await init_broker()
        print(f"✅ Broker initialized: {broker is not None}")
        
        print("📰 Initializing news system...")
        await init_news_system()
        print("✅ News system initialized")
        
        while True:
            print(f"📊 Fetching dashboard data for user_id={user_id}...")
            # Gather all data for this user
            data = await get_dashboard_data(user_id)
            print(f"✅ Data gathered: {len(data.get('monitored_stocks', []))} stocks, {len(data.get('positions', []))} positions")

            # Send to client — check connection state first
            if websocket.client_state.value != 1:  # 1 = CONNECTED
                break
            await websocket.send_json(data)
            print("✅ Data sent to client")

            # Wait before next update (fetch takes ~7s so 30s total cycle is fine)
            await asyncio.sleep(30)

    except WebSocketDisconnect:
        print("⚠️ WebSocket disconnected (client navigated away)")
        manager.disconnect(websocket)
    except Exception as e:
        # Suppress noisy traceback for normal client-disconnect exceptions
        err_str = str(type(e).__name__)
        if "ClientDisconnected" in err_str or "ConnectionClosed" in err_str:
            print(f"⚠️ WebSocket client disconnected during send")
        else:
            print(f"❌ WebSocket error: {e}")
            import traceback
            traceback.print_exc()
        manager.disconnect(websocket)

async def get_dashboard_data(user_id: str) -> Dict:
    """Gather all dashboard data for a specific user (Supabase version)"""
    start_time = time.time()
    try:
        # Always sync broker data before fetching dashboard data
        try:
            await sync_broker_data()
        except Exception as sync_exc:
            print(f"⚠️ Broker sync failed: {sync_exc}")
        from tradiqai_supabase_config import get_supabase_client, get_supabase_admin
        supabase = get_supabase_admin()  # Use admin client to bypass RLS
        
        print(f"  [1/6] Fetching user data for user_id={user_id}...")
        # Get user from Supabase
        user_response = supabase.table("users").select("*").eq("id", user_id).execute()
        if not user_response.data:
            logger.error(f"User not found: {user_id}")
            return {}
        
        user_data = user_response.data[0]
        logger.debug(f"⏱️ User fetched: {time.time() - start_time:.3f}s")
        
        print("  [2/6] Checking market status...")
        # Check if market is open (IST)
        now = now_ist()
        from datetime import time as dt_time
        market_open_time = dt_time(*map(int, config.market_open_time.split(":")))
        market_close_time = dt_time(*map(int, config.market_close_time.split(":")))
        
        market_open = (
            now.weekday() < 5 and  # Monday to Friday
            market_open_time <= now.time() <= market_close_time
        )
        print(f"     Market open: {market_open}")
        
        print("  [3/6] Fetching account margins...")
        # Get account data from user settings
        account_start = time.time()
        account_data = {
            "capital": user_data["capital"],
            "margin_used": 0.0,
            "exposure": 0.0
        }
        
        # Optionally fetch live margins from broker if connected
        if broker:
            try:
                # Add timeout to prevent hanging
                margins = await asyncio.wait_for(broker.get_margins(), timeout=5.0)
                print(f"     Margins fetched in {time.time() - account_start:.3f}s")
                logger.debug(f"⏱️ Margins fetched: {time.time() - account_start:.3f}s")
                if margins:
                    # Use broker data if available, otherwise use user settings
                    account_data = {
                        "capital": margins.get("available_cash", user_data["capital"]),
                        "margin_used": margins.get("margin_used", 0.0),
                        "exposure": margins.get("margin_used", 0.0) / max(margins.get("available_cash", user_data["capital"]), 1.0) * 100
                    }
            except asyncio.TimeoutError:
                print(f"     ⚠️ Margins fetch timed out after 5s, using user settings")
                logger.warning("Margins fetch timed out")
            except Exception as e:
                print(f"     ⚠️ Margins fetch error: {e}, using user settings")
                logger.error(f"Error fetching margins: {e}")
        
        # Get active positions from broker
        positions_start = time.time()
        positions_data = []
        total_unrealized_pnl = 0.0
        
        print("  [4/6] Fetching active positions...")
        if broker:
            try:
                positions = await asyncio.wait_for(broker.get_positions(), timeout=5.0)
                print(f"     Positions fetched in {time.time() - positions_start:.3f}s: {len(positions) if positions else 0} positions")
                logger.debug(f"⏱️ Positions fetched: {time.time() - positions_start:.3f}s")
                if positions:
                    for pos in positions:
                        # Calculate unrealized P&L
                        quantity = pos.quantity
                        avg_price = pos.average_price
                        ltp = pos.last_price if pos.last_price else avg_price
                        
                        if quantity > 0:  # Long position
                            unrealized_pnl = (ltp - avg_price) * quantity
                            side = "BUY"
                        else:  # Short position
                            unrealized_pnl = (avg_price - ltp) * abs(quantity)
                            side = "SELL"
                        
                        total_unrealized_pnl += unrealized_pnl
                        
                        positions_data.append({
                            "symbol": pos.symbol,
                            "side": side,
                            "quantity": abs(quantity),
                            "average_price": avg_price,
                            "current_price": ltp,
                            "unrealized_pnl": unrealized_pnl,
                            "entry_time": None
                        })
            except asyncio.TimeoutError:
                print(f"     ⚠️ Positions fetch timed out after 5s")
                logger.warning("Positions fetch timed out")
            except Exception as e:
                print(f"     ⚠️ Positions fetch error: {e}")
                logger.error(f"Error fetching positions: {e}")
        
        # Get monitored stocks with live quotes (CACHED for performance)
        # NIFTY 50 universe - system will show current movers
        quotes_start = time.time()
        monitored_stocks_data = []
        print("  [5/6] Fetching live quotes for 48 NIFTY 50 stocks (with cache)...")
        watchlist = [
            # IT (6)
            "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM",
            # Banking & Finance (10)
            "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
            "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "LICI",
            # Energy & Oil (3)
            "RELIANCE", "ONGC", "BPCL",
            # Auto (4)
            "MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT",
            # Metals (3)
            "TATASTEEL", "HINDALCO", "JSWSTEEL",
            # Pharma (4)
            "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB",
            # FMCG (5)
            "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR",
            # Cement & Constr (3)
            "ULTRACEMCO", "LT", "GRASIM",
            # Telecom (1)
            "BHARTIARTL",
            # Others (9)
            "ADANIENT", "ADANIPORTS", "NTPC", "POWERGRID", "TITAN",
            "ASIANPAINT", "INDIGO", "COALINDIA", "TATACONSUM"
        ]
        
        current_time = time.time()
        cache_hits = 0
        cache_misses = 0
        
        if broker:
            # Fetch quotes concurrently in batches to speed up
            async def fetch_quote_safe(symbol):
                try:
                    # Check cache first
                    if symbol in quote_cache:
                        cache_entry = quote_cache[symbol]
                        if current_time - cache_entry['timestamp'] < QUOTE_CACHE_TTL:
                            return ('cached', cache_entry['data'])
                    
                    # Cache miss - fetch fresh data
                    quote = await asyncio.wait_for(broker.get_quote(symbol), timeout=3.0)
                    if quote:
                        ltp = quote.last_price
                        prev_close = quote.close
                        day_change = ltp - prev_close if prev_close > 0 else 0
                        day_change_percent = (day_change / prev_close * 100) if prev_close > 0 else 0
                        
                        signal = "No Signal"
                        if day_change_percent >= 1.5:
                            signal = "BUY Signal"
                        elif day_change_percent <= -2.0:
                            signal = "Avoid"
                        
                        quote_data = {
                            "symbol": symbol,
                            "ltp": ltp,
                            "day_change": day_change,
                            "day_change_percent": day_change_percent,
                            "signal": signal
                        }
                        
                        # Cache the data
                        quote_cache[symbol] = {
                            'data': quote_data,
                            'timestamp': current_time
                        }
                        
                        return ('fetched', quote_data)
                    return ('error', symbol, "No quote data")
                except asyncio.TimeoutError:
                    return ('timeout', symbol)
                except Exception as e:
                    return ('error', symbol, str(e))
            
            # Fetch all quotes concurrently (max 10 at a time to avoid overwhelming API)
            batch_size = 10
            for i in range(0, len(watchlist), batch_size):
                batch = watchlist[i:i+batch_size]
                results = await asyncio.gather(*[fetch_quote_safe(symbol) for symbol in batch], return_exceptions=True)
                
                for result in results:
                    if isinstance(result, tuple):
                        if result[0] == 'cached':
                            cache_hits += 1
                            monitored_stocks_data.append(result[1])
                        elif result[0] == 'fetched':
                            cache_misses += 1
                            monitored_stocks_data.append(result[1])
                        elif result[0] in ('timeout', 'error'):
                            symbol = result[1]
                            error_data = {
                                "symbol": symbol,
                                "ltp": 0,
                                "day_change": 0,
                                "day_change_percent": 0,
                                "signal": "Timeout" if result[0] == 'timeout' else "Error"
                            }
                            monitored_stocks_data.append(error_data)
        
        print(f"     Quotes fetched in {time.time() - quotes_start:.3f}s (cache hits: {cache_hits}, misses: {cache_misses})")
        logger.debug(f"⏱️ Quotes fetched: {time.time() - quotes_start:.3f}s (cache hits: {cache_hits}, misses: {cache_misses})")
        
        # Get today's trades for this user from Supabase (IST)
        print(f"  [6/6] Fetching today's trades for user_id={user_id}...")
        trades_start = time.time()
        today_start = today_ist().isoformat()
        

        trades_response = supabase.table("trades").select("*").eq("user_id", user_id).gte("entry_timestamp", today_start).order("entry_timestamp", desc=True).limit(10).execute()
        trades = trades_response.data if trades_response.data else []
        logger.debug(f"⏱️ Trades query: {time.time() - trades_start:.3f}s")

        trades_data = []
        total_realized_pnl = 0.0
        winning_trades = 0

        # --- Automatic P&L fix for closed trades ---
        for trade in trades:
            pnl = trade.get("pnl", 0.0) or 0.0
            status = trade.get("status", "OPEN")
            entry_price = trade.get("entry_price")
            exit_price = trade.get("exit_price")
            quantity = trade.get("quantity")
            side = trade.get("side", "BUY")

            # If trade is CLOSED and pnl is missing/zero, but exit_price exists, calculate and update
            if status == "CLOSED" and (pnl == 0 or pnl is None) and entry_price is not None and exit_price is not None and quantity:
                try:
                    if side == "BUY":
                        pnl = (exit_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - exit_price) * quantity
                    # Update Supabase with calculated pnl
                    supabase.table("trades").update({"pnl": pnl}).eq("id", trade.get("id")).execute()
                except Exception as e:
                    print(f"⚠️ Failed to auto-update P&L for trade {trade.get('id')}: {e}")

            total_realized_pnl += pnl
            if pnl > 0:
                winning_trades += 1

            trades_data.append({
                "timestamp": trade.get("entry_timestamp"),
                "symbol": trade.get("symbol"),
                "side": side,
                "quantity": quantity,
                "price": entry_price,
                "pnl": pnl,
                "status": status
            })

        # Calculate performance metrics
        total_pnl = total_realized_pnl + total_unrealized_pnl
        win_rate = (winning_trades / len(trades) * 100) if trades else 0
        
        # Sort monitored stocks by day change % (highest first) - shows top movers at top
        monitored_stocks_data.sort(key=lambda x: x.get('day_change_percent', 0), reverse=True)
        
        # News feed - Dashboard uses Supabase, not local SQLite
        # TODO: Implement news feed from Supabase when news_items table is ready
        news_feed_data = []
        
        total_time = time.time() - start_time
        print(f"✅ Dashboard data complete in {total_time:.3f}s - returning {len(monitored_stocks_data)} stocks, {len(positions_data)} positions, {len(trades_data)} trades")
        logger.info(f"📊 Dashboard data fetched in {total_time:.3f}s")
        
        return {
            "timestamp": now_ist().isoformat(),
            "market_open": market_open,
            "account": account_data,
            "performance": {
                "today_pnl": total_pnl,
                "realized_pnl": total_realized_pnl,
                "unrealized_pnl": total_unrealized_pnl,
                "trades_count": len(trades),
                "win_rate": win_rate
            },
            "positions": positions_data,
            "trades": trades_data,
            "monitored_stocks": monitored_stocks_data,
            "news_feed": news_feed_data,
            "signals": 0,  # We can add signal tracking later
            # Dividend Radar Engine candidates (if scheduler has run)
            "dividend_radar": []
        }
        
    except Exception as e:
        print(f"Error gathering dashboard data: {e}")
        import traceback
        traceback.print_exc()
        return {
            "timestamp": now_ist().isoformat(),
            "market_open": False,
            "account": {"capital": 0, "margin_used": 0, "exposure": 0},
            "performance": {"today_pnl": 0, "trades_count": 0, "win_rate": 0},
            "positions": [],
            "trades": [],
            "monitored_stocks": [],
            "news_feed": [],
            "signals": 0
        }

def run_dashboard(host: str = "0.0.0.0", port: int = 8080):
    """Run the dashboard server"""
    print(f"🚀 Starting TradiqAI Dashboard on http://{host}:{port}")
    print(f"📊 Open http://localhost:{port} in your browser")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_dashboard(port=9000)
