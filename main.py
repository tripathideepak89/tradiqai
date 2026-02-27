"""Main application - Trading system orchestrator"""
import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict
import sys
from sqlalchemy.orm import Session

from config import settings
from database import get_session_local, init_db, redis_client
from brokers.factory import BrokerFactory
from brokers.base import BaseBroker, TransactionType, OrderType
from risk_engine import RiskEngine
from order_manager import OrderManager
from strategies.live_simple import LiveSimpleStrategy
from monitoring import MonitoringService
from models import DailyMetrics, Trade, TradeStatus, TradeDirection
from sqlalchemy import func
from utils.timezone import now_ist, today_ist, format_ist

# News system imports
from news_ingestion_layer import get_news_ingestion_layer, NewsIngestionLayer
from news_impact_detector import NewsImpactDetector, NewsAction
from news_governance import NewsGovernance
from news_intelligence import NewsIntelligenceEngine
from dividend_scheduler import DividendRadarScheduler

# Custom formatter with IST timezone
class ISTFormatter(logging.Formatter):
    """Logging formatter that displays timestamps in IST"""
    def formatTime(self, record, datefmt=None):
        from utils import now_ist
        dt = now_ist()
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S IST')

# Setup logging with IST timestamps
ist_formatter = ISTFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler(f'logs/trading_{date.today()}.log')
file_handler.setFormatter(ist_formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ist_formatter)

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)


class TradingSystem:
    """Main trading system orchestrator"""
    
    def __init__(self):
        SessionLocal = get_session_local()
        self.db: Session = SessionLocal()
        self.broker: BaseBroker = None
        self.risk_engine: RiskEngine = None
        self.order_manager: OrderManager = None
        self.monitoring: MonitoringService = None
        self.strategies: List = []
        self.is_running = False

        # News system components
        self.news_ingestion: NewsIngestionLayer = None
        self.news_detector: NewsImpactDetector = None
        self.news_governance: NewsGovernance = None
        self.news_intelligence: NewsIntelligenceEngine = None

        # DRE Scheduler
        self.dre_scheduler = None
    
    async def initialize(self) -> bool:
        """Initialize all components"""
        try:
            logger.info("Initializing AutoTrade AI System...")
            
            # 1. Initialize database
            init_db()
            logger.info("[OK] Database initialized")
            
            # 2. Initialize broker
            broker_name = settings.broker.lower()
            logger.info(f"Using broker: {broker_name}")
            
            if broker_name == "zerodha":
                broker_config = {
                    "api_key": settings.zerodha_api_key,
                    "api_secret": settings.zerodha_api_secret,
                    "user_id": settings.zerodha_user_id,
                    "password": settings.zerodha_password,
                    "totp_secret": settings.zerodha_totp_secret
                }
            else:  # groww
                broker_config = {
                    "api_key": settings.groww_api_key,
                    "api_secret": settings.groww_api_secret,
                    "api_url": settings.groww_api_url
                }
            
            self.broker = BrokerFactory.create_broker(broker_name, broker_config)
            
            # Connect to broker
            if not await self.broker.connect():
                logger.error("Failed to connect to broker")
                return False
            
            logger.info("[OK] Broker connected")
            
            # 3. Initialize risk engine with broker for dynamic capital updates
            self.risk_engine = RiskEngine(self.db, broker=self.broker)
            logger.info("[OK] Risk engine initialized")
            
            # Update available capital from broker
            await self.risk_engine.update_available_capital()
            logger.info(f"[OK] Trading capital: Rs{self.risk_engine.available_capital:,.2f}")
            
            # 4. Initialize order manager
            self.order_manager = OrderManager(self.broker, self.risk_engine, self.db)
            logger.info("[OK] Order manager initialized")
            
            # 4a. Sync broker positions to database on startup
            logger.info("[SYNC] Syncing broker positions to database...")
            sync_result = await self.order_manager.sync_broker_positions()
            if sync_result:
                logger.info("[OK] [DATABASE] Broker positions synced successfully")
            else:
                logger.warning("[WARNING] [DATABASE] Broker sync failed - check logs")
            
            # 5. Initialize strategies with broker (for pre-entry checks)
            # Using professional live-quote strategy with pre-entry checklist
            self.strategies.append(LiveSimpleStrategy(broker=self.broker))
            logger.info("[OK] Live Simple strategy loaded with PRE-ENTRY CHECKLIST and ADAPTIVE TARGETS")
            
            # 6. Initialize monitoring
            self.monitoring = MonitoringService()
            logger.info("[OK] Monitoring service initialized")
            
            # 7. Initialize news system (NEW)
            self.news_ingestion = get_news_ingestion_layer()
            self.news_detector = NewsImpactDetector()
            self.news_governance = NewsGovernance()
            self.news_intelligence = NewsIntelligenceEngine()
            logger.info("[OK] [NEWS] News impact detection system initialized")
            logger.info("   → NSE announcements polling enabled")
            logger.info("   → Burst mode detection active")
            logger.info("   → News governance rules enforced")
            logger.info("   → INTELLIGENCE: Sentiment analysis active")
            logger.info("   → INTELLIGENCE: News clustering enabled")
            logger.info("   → INTELLIGENCE: Adaptive position sizing ready")
            
            # 8. Send startup alert
            await self.monitoring.send_alert(
                f"[STARTED] AutoTrade AI System Started\n\n"
                f"Capital: Rs{self.risk_engine.available_capital:,.2f}\n"
                f"Max Per Trade: Rs{self.risk_engine.get_max_capital_per_trade():,.2f} (25%)\n"
                f"Mode: {'PAPER' if settings.paper_trading else 'LIVE'}\n"
                f"Strategies: {len(self.strategies)}",
                severity="INFO"
            )
            
            logger.info("[OK] System initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    def start_dre_scheduler(self):
        """Start the Dividend Radar Engine background scheduler."""
        try:
            from dividend_scheduler import DividendRadarScheduler
            self.dre_scheduler = DividendRadarScheduler()
            self.dre_scheduler.start_background()
            logger.info("[OK] DRE background scheduler started (6:30 AM IST)")
        except Exception as e:
            logger.error(f"Failed to start DRE scheduler: {e}")
    
    async def start(self) -> None:
        """Start the trading system"""
        try:
            if not await self.initialize():
                logger.error("Failed to initialize system")
                return
            
            self.is_running = True

            # Start DRE scheduler (background)
            self.start_dre_scheduler()

            # Start background tasks
            tasks = [
                asyncio.create_task(self.trading_loop()),
                asyncio.create_task(self.position_monitor()),
                asyncio.create_task(self.risk_monitor()),
                asyncio.create_task(self.monitoring.start_monitoring()),
                asyncio.create_task(self.news_processing_loop())  # NEW: News processing
            ]

            # Start news ingestion (separate task)
            news_task = asyncio.create_task(self.news_ingestion.start_polling())
            tasks.append(news_task)

            # Wait for all tasks
            await asyncio.gather(*tasks)
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            await self.shutdown()
        except Exception as e:
            logger.error(f"System error: {e}")
            await self.shutdown()
    
    async def trading_loop(self) -> None:
        """Main trading loop - runs during market hours"""
        logger.info("Trading loop started")
        
        capital_update_counter = 0
        
        while self.is_running:
            try:
                # Update available capital every 10 minutes
                if capital_update_counter % 10 == 0:
                    await self.risk_engine.update_available_capital()
                    logger.debug(f"Capital updated: Rs{self.risk_engine.available_capital:,.2f}")
                capital_update_counter += 1
                
                # Check if market is open
                if not self.monitoring.is_market_open():
                    logger.debug("Market closed, waiting...")
                    await asyncio.sleep(60)
                    continue
                
                # Check kill switch
                if self.monitoring.is_kill_switch_active():
                    reason = self.monitoring.get_kill_switch_reason()
                    logger.warning(f"Kill switch active: {reason}")
                    await asyncio.sleep(60)
                    continue
                
                # Scan for signals
                await self.scan_for_signals()
                
                # Check for exits
                await self.check_exits()
                
                # Wait before next iteration
                await asyncio.sleep(60)  # Scan every minute
                
            except Exception as e:
                logger.error(f"Trading loop error: {e}")
                await asyncio.sleep(60)
    
    async def scan_for_signals(self) -> None:
        """Scan for trading signals"""
        try:
            # Check if new trades are allowed at current time
            from time_filter import TimeFilter
            can_trade, reason = TimeFilter.can_enter_new_trade()
            
            if not can_trade:
                logger.debug(f"Not scanning for signals: {reason}")
                return
            
            # Get watchlist (implement your watchlist logic)
            watchlist = await self.get_watchlist()
            
            for symbol in watchlist:
                for strategy in self.strategies:
                    try:
                        # Get live quote
                        quote = await self.broker.get_quote(symbol)
                        
                        if quote is None or quote.last_price == 0:
                            continue
                        
                        # Convert Quote object to dict for strategy
                        quote_dict = {
                            'ltp': quote.last_price,
                            'open': quote.open,
                            'high': quote.high,
                            'low': quote.low,
                            'close': quote.close,
                            'volume': quote.volume,
                            'avg_volume': getattr(quote, 'avg_volume', quote.volume),
                            'vwap': getattr(quote, 'vwap', quote.last_price)
                        }
                        
                        # Trigger burst mode if unusual activity detected
                        self.news_ingestion.trigger_burst_mode(symbol, quote_dict)
                        
                        # Generate signal
                        signal = await strategy.analyze(quote_dict, symbol)
                        
                        if signal:
                            logger.info(f"Signal generated: {signal.symbol} - {signal.action}")
                            
                            # Execute signal
                            trade = await self.order_manager.execute_signal(
                                signal,
                                strategy.name
                            )
                            
                            if trade:
                                # Send alert
                                await self.monitoring.send_trade_alert({
                                    'action': 'ENTRY',
                                    'symbol': trade.symbol,
                                    'direction': trade.direction.value,
                                    'entry_price': trade.entry_price,
                                    'stop_loss': trade.stop_price,
                                    'target': trade.target_price,
                                    'quantity': trade.quantity,
                                    'risk': trade.risk_amount,
                                    'strategy': trade.strategy_name
                                })
                    
                    except Exception as e:
                        logger.error(f"Error scanning {symbol}: {e}")
        
        except Exception as e:
            logger.error(f"Signal scanning error: {e}")
    
    async def check_exits(self) -> None:
        """Check if any open positions should be exited"""
        try:
            open_trades = self.db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN
            ).all()
            
            for trade in open_trades:
                try:
                    # Get current quote
                    quote = await self.broker.get_quote(trade.symbol)
                    current_price = quote.last_price
                    
                    # Find strategy
                    strategy = next(
                        (s for s in self.strategies if s.name == trade.strategy_name),
                        None
                    )
                    
                    if not strategy:
                        continue
                    
                    # Check exit conditions
                    position = {
                        'symbol': trade.symbol,
                        'entry_price': trade.entry_price,
                        'stop_loss': trade.stop_price,
                        'target': trade.target_price,
                        'entry_timestamp': trade.entry_timestamp
                    }
                    
                    # Convert Quote to dict for strategy
                    quote_dict = {
                        'ltp': quote.last_price,
                        'open': quote.open,
                        'high': quote.high,
                        'low': quote.low,
                        'close': quote.close,
                        'volume': quote.volume
                    }
                    
                    should_exit = await strategy.should_exit(position, quote_dict)
                    
                    if should_exit:
                        await self.order_manager.close_position(
                            trade.id,
                            reason="STRATEGY_EXIT",
                            exit_price=current_price
                        )
                
                except Exception as e:
                    logger.error(f"Error checking exit for {trade.symbol}: {e}")
        
        except Exception as e:
            logger.error(f"Exit check error: {e}")
    
    async def _check_pending_orders(self) -> None:
        """Check pending orders and update status when filled"""
        try:
            pending_trades = self.db.query(Trade).filter(
                Trade.status == TradeStatus.PENDING
            ).all()
            
            if not pending_trades:
                return
            
            logger.debug(f"Checking {len(pending_trades)} pending orders for fills")
            
            # Get broker orders to check status
            broker_orders = await self.broker.get_orders()
            broker_order_map = {order.order_id: order for order in broker_orders}
            
            for trade in pending_trades:
                try:
                    broker_order = broker_order_map.get(trade.broker_entry_id)
                    
                    if broker_order and broker_order.status.name == "COMPLETE":
                        # Order filled! Update database
                        filled_price = broker_order.average_price
                        filled_qty = broker_order.filled_quantity
                        
                        logger.info(f"[MANUAL ORDER FILLED] {trade.symbol}: {filled_qty} @ Rs{filled_price:.2f}")
                        
                        # Update trade record
                        trade.status = TradeStatus.OPEN
                        trade.entry_price = filled_price
                        trade.quantity = filled_qty
                        trade.entry_timestamp = datetime.now()
                        
                        # Apply smart stop/target based on current market
                        await self._apply_smart_stops(trade, filled_price)
                        
                        self.db.commit()
                        
                        # Send alert
                        await self.monitoring.send_alert(
                            f"[MANUAL ORDER FILLED]\n\n"
                            f"Symbol: {trade.symbol}\n"
                            f"Qty: {filled_qty} shares @ Rs{filled_price:.2f}\n"
                            f"Stop Loss: Rs{trade.stop_price:.2f}\n"
                            f"Target: Rs{trade.target_price:.2f}\n"
                            f"Now actively managed by system",
                            severity="INFO"
                        )
                    
                    elif broker_order and broker_order.status.name in ["CANCELLED", "REJECTED"]:
                        # Order cancelled/rejected
                        trade.status = TradeStatus.CANCELLED if broker_order.status.name == "CANCELLED" else TradeStatus.REJECTED
                        trade.notes = (trade.notes or "") + f"\nOrder {broker_order.status.name.lower()} by broker"
                        self.db.commit()
                        logger.info(f"[MANUAL ORDER {broker_order.status.name}] {trade.symbol}")
                
                except Exception as e:
                    logger.error(f"Error checking pending order {trade.symbol}: {e}")
        
        except Exception as e:
            logger.error(f"Error in pending order check: {e}")
    
    async def _apply_smart_stops(self, trade: Trade, entry_price: float) -> None:
        """Apply intelligent stop loss and target based on market conditions"""
        try:
            # Get current quote for volatility assessment
            quote = await self.broker.get_quote(trade.symbol)
            
            if not quote:
                # Fallback to default stop/target
                trade.stop_price = entry_price * 0.98  # 2% SL
                trade.target_price = entry_price * 1.03  # 3% target
                logger.warning(f"No quote for {trade.symbol}, using default 2%/3% stops")
                return
            
            # Calculate intraday range
            if quote.high and quote.low and quote.high > quote.low:
                intraday_range_pct = ((quote.high - quote.low) / entry_price) * 100
            else:
                intraday_range_pct = 2.0  # Default
            
            # Adaptive stop loss based on volatility
            if intraday_range_pct < 1.5:
                # Low volatility: Tighter stops
                stop_pct = 1.5
                target_pct = 3.0  # 2:1 R:R
            elif intraday_range_pct < 3.0:
                # Normal volatility
                stop_pct = 2.0
                target_pct = 4.0  # 2:1 R:R
            else:
                # High volatility: Wider stops
                stop_pct = 2.5
                target_pct = 5.0  # 2:1 R:R
            
            # Apply stops
            if trade.direction == TradeDirection.LONG:
                trade.stop_price = entry_price * (1 - stop_pct / 100)
                trade.target_price = entry_price * (1 + target_pct / 100)
            else:  # SHORT
                trade.stop_price = entry_price * (1 + stop_pct / 100)
                trade.target_price = entry_price * (1 - target_pct / 100)
            
            logger.info(
                f"[SMART STOPS] {trade.symbol}: SL Rs{trade.stop_price:.2f} ({stop_pct}%), "
                f"Target Rs{trade.target_price:.2f} ({target_pct}%), R:R {target_pct/stop_pct:.1f}:1"
            )
            
        except Exception as e:
            logger.error(f"Error applying smart stops for {trade.symbol}: {e}")
            # Fallback to defaults
            trade.stop_price = entry_price * 0.98
            trade.target_price = entry_price * 1.03
    
    async def position_monitor(self) -> None:
        """Monitor and reconcile positions, check for exits"""
        logger.info("Position monitor started")
        
        sync_counter = 0  # Counter for periodic broker sync
        
        while self.is_running:
            try:
                # Position reconciliation - DISABLED to avoid log spam with existing positions
                # await asyncio.sleep(self.order_manager.position_reconciliation_interval)
                # await self.order_manager.reconcile_positions()
                
                # Check pending manual orders for fills
                await self._check_pending_orders()
                
                # Periodic broker sync - TEMPORARILY DISABLED due to database issues
                # sync_counter += 1
                # if sync_counter >= 30:  # Every 5 minutes (30 * 10s = 300s = 5 minutes)
                #     logger.info("[SYNC] Running periodic broker sync...")
                #     sync_result = await self.order_manager.sync_broker_positions()
                #     if sync_result:
                #         logger.info("[OK] Periodic broker sync completed")
                #     else:
                #         logger.warning("[WARNING] Periodic broker sync failed")
                #     
                #     # Cleanup old news clusters
                #     self.news_intelligence.cleanup()
                #     
                #     sync_counter = 0
                
                # Check for exits (targets, stop losses, end of day)
                await self._check_position_exits()
                
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)
    
    async def _check_position_exits(self) -> None:
        """Check if any positions should exit based on target/SL/EOD"""
        from datetime import datetime, time
        from models import Trade, TradeStatus, TradeDirection
        
        # Get all open positions
        open_trades = self.db.query(Trade).filter(
            Trade.status == TradeStatus.OPEN
        ).all()
        
        if not open_trades:
            return
        
        logger.debug(f"Checking exits for {len(open_trades)} open positions")
        
        # Check market time (intraday positions must exit by 15:20) - IST
        current_time = now_ist().time()
        eod_cutoff = time(15, 20)  # 3:20 PM IST
        is_eod = current_time >= eod_cutoff
        
        for trade in open_trades:
            try:
                # Get current price
                quote = await self.broker.get_quote(trade.symbol)
                current_price = quote.last_price if quote else 0
                
                if current_price == 0:
                    logger.warning(f"Could not get price for {trade.symbol}")
                    continue
                
                should_exit = False
                exit_reason = ""

                # Determine if LONG or SHORT
                is_long = trade.direction == TradeDirection.LONG

                # Read product type stamped at entry (MIS = intraday, CNC = swing)
                trade_product = "MIS"
                if trade.notes and "product:CNC" in trade.notes:
                    trade_product = "CNC"

                # Check target hit (applies to both MIS and CNC)
                if trade.target_price:
                    target_hit = (current_price >= trade.target_price) if is_long else (current_price <= trade.target_price)
                    if target_hit:
                        should_exit = True
                        exit_reason = f"TARGET HIT at Rs{current_price:.2f} (target Rs{trade.target_price:.2f})"
                        logger.info(f"[EXIT] {trade.symbol} {exit_reason}")

                # Check stop loss hit (applies to both)
                if not should_exit and trade.stop_price:
                    stop_hit = (current_price <= trade.stop_price) if is_long else (current_price >= trade.stop_price)
                    if stop_hit:
                        should_exit = True
                        exit_reason = f"STOP LOSS at Rs{current_price:.2f} (SL Rs{trade.stop_price:.2f})"
                        logger.warning(f"[EXIT] {trade.symbol} {exit_reason}")

                # MIS: force close at end of day
                if not should_exit and trade_product == "MIS" and is_eod:
                    should_exit = True
                    exit_reason = f"EOD SQUAREOFF (MIS) at Rs{current_price:.2f}"
                    logger.info(f"[EXIT] {trade.symbol} {exit_reason}")

                # CNC swing exits (no EOD force, but time-based limits)
                if not should_exit and trade_product == "CNC" and trade.entry_timestamp:
                    try:
                        entry_ts = trade.entry_timestamp
                        if entry_ts.tzinfo is None:
                            from utils.timezone import IST
                            entry_ts = entry_ts.replace(tzinfo=IST)
                        hold_days = (now_ist() - entry_ts).days

                        # Rule 1: max 3 calendar days
                        if hold_days >= 3:
                            should_exit = True
                            exit_reason = f"MAX SWING HOLD (3 days) at Rs{current_price:.2f}"
                            logger.info(f"[EXIT] {trade.symbol} {exit_reason}")

                        # Rule 2: time-based stop — still in loss after 2 days
                        if not should_exit and hold_days >= 2 and current_price <= trade.entry_price:
                            should_exit = True
                            exit_reason = f"TIME STOP — no gain after 2 days at Rs{current_price:.2f}"
                            logger.info(f"[EXIT] {trade.symbol} {exit_reason}")

                        # Rule 3: gap down below stop at market open (first 15 min)
                        current_hour = now_ist().hour
                        current_min = now_ist().minute
                        is_market_open_window = (current_hour == 9 and current_min <= 30)
                        if not should_exit and is_market_open_window and current_price < trade.stop_price:
                            should_exit = True
                            exit_reason = f"GAP DOWN BELOW STOP at Rs{current_price:.2f}"
                            logger.warning(f"[EXIT] {trade.symbol} {exit_reason}")
                    except Exception as swing_err:
                        logger.warning(f"Swing exit check error for {trade.symbol}: {swing_err}")

                # Place exit order
                if should_exit:
                    # Determine exit transaction type (opposite of entry)
                    transaction_type = TransactionType.SELL if is_long else TransactionType.BUY
                    logger.info(f"Placing {transaction_type.value} order for {trade.symbol}: {trade.quantity} shares @ market [{trade_product}]")

                    # Place market exit order using same product as entry
                    exit_order = await self.broker.place_order(
                        symbol=trade.symbol,
                        quantity=trade.quantity,
                        order_type=OrderType.MARKET,
                        transaction_type=transaction_type,
                        product=trade_product
                    )
                    
                    if exit_order and exit_order.status != "REJECTED":
                        # Update trade status
                        trade.exit_price = current_price
                        trade.status = TradeStatus.CLOSED
                        trade.notes = (trade.notes or "") + f"\n{exit_reason}"
                        
                        # Calculate PnL (considering direction)
                        if is_long:
                            pnl = (current_price - trade.entry_price) * trade.quantity
                        else:  # SHORT
                            pnl = (trade.entry_price - current_price) * trade.quantity
                        trade.realized_pnl = pnl
                        
                        self.db.commit()
                        
                        logger.info(
                            f"[OK] {trade.symbol} SOLD: {trade.quantity} shares @ Rs{current_price:.2f}, "
                            f"PnL: Rs{pnl:.2f} ({exit_reason})"
                        )
                        
                        await self.monitoring.send_alert(
                            f"Position Closed: {trade.symbol}\n"
                            f"Exit: Rs{current_price:.2f}\n"
                            f"PnL: Rs{pnl:.2f}\n"
                            f"Reason: {exit_reason}",
                            severity="INFO"
                        )
                    else:
                        logger.error(f"Failed to place exit order for {trade.symbol}")
                        
            except Exception as e:
                logger.error(f"Error checking exit for {trade.symbol}: {e}")
    
    async def risk_monitor(self) -> None:
        """Monitor risk metrics"""
        logger.info("Risk monitor started")
        
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Get risk metrics
                metrics = await self.risk_engine.get_risk_metrics()
                
                # Check for warnings
                if metrics.get('daily_loss_utilization', 0) > 80:
                    await self.monitoring.send_alert(
                        f"[WARNING] Daily loss limit approaching: {metrics['daily_loss_utilization']:.1f}%",
                        severity="WARNING"
                    )
                
                if metrics.get('consecutive_losses', 0) >= settings.consecutive_loss_limit - 1:
                    await self.monitoring.send_alert(
                        f"[WARNING] Consecutive losses: {metrics['consecutive_losses']}",
                        severity="WARNING"
                    )
            
            except Exception as e:
                logger.error(f"Risk monitor error: {e}")
                await asyncio.sleep(60)
    
    async def get_watchlist(self) -> List[str]:
        """Get dynamic trading watchlist by scanning liquid stocks and finding movers
        
        Strategy:
        - Monitors NIFTY 100/200 liquid stocks in rotation
        - Scans quotes to identify intraday movers (>1% day change)
        - Combines active movers + core liquid stocks
        - Refreshes every 10 minutes
        
        Returns:
            List of stock symbols to monitor
        """
        from datetime import datetime, timedelta
        
        # Check cache (refresh every 10 minutes)
        if hasattr(self, '_watchlist_cache') and hasattr(self, '_watchlist_cache_time'):
            cache_age = now_ist() - self._watchlist_cache_time
            if cache_age < timedelta(minutes=10):
                return self._watchlist_cache
        
        try:
            # Broad universe of liquid stocks from NIFTY 100/200
            # Rotated in batches to avoid overwhelming the API
            liquid_stocks = [
                # Banking & Finance (15)
                "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
                "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "INDUSINDBK",
                "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "PNB", "CANBK",
                
                # IT (8)
                "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "PERSISTENT", "COFORGE",
                
                # Auto (8)
                "MARUTI", "M&M", "TATAMOTORS", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO", "TVSMOTOR", "ASHOKLEY",
                
                # Metals (6)
                "TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "NATIONALUM", "HINDZINC",
                
                # Pharma (6)
                "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA", "TORNTPHARM",
                
                # FMCG & Consumer (8)
                "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "GODREJCP", "TATACONSUM",
                
                # Energy & Oil (6)
                "RELIANCE", "ONGC", "BPCL", "IOC", "GAIL", "ADANIGREEN",
                
                # Cement & Construction (6)
                "ULTRACEMCO", "LT", "GRASIM", "AMBUJACEM", "ACC", "SIEMENS",
                
                # Telecom & Services (5)
                "BHARTIARTL", "INDIGO", "ZOMATO", "NYKAA", "DMART",
                
                # Others (10)
                "ADANIPORTS", "ADANIENT", "NTPC", "POWERGRID", "TITAN", 
                "ASIANPAINT", "PIDILITIND", "BERGEPAINT", "HAVELLS", "VOLTAS"
            ]
            
            # Scan for movers: fetch quotes and identify stocks with >1% day change
            logger.info(f"Scanning {len(liquid_stocks)} liquid stocks for movers...")
            movers = []
            
            # Sample a subset to avoid too many API calls (scan 30 stocks at a time)
            import random
            sample_size = min(30, len(liquid_stocks))
            stocks_to_scan = random.sample(liquid_stocks, sample_size)
            
            for symbol in stocks_to_scan:
                try:
                    quote = await self.broker.get_quote(symbol)
                    if quote:
                        # Calculate day change percentage from quote attributes
                        day_change_pct = ((quote.last_price - quote.close) / quote.close * 100) if quote.close > 0 else 0
                        # Consider stocks with >1% absolute change as active movers
                        if abs(day_change_pct) >= 1.0:
                            movers.append({
                                'symbol': symbol,
                                'change': day_change_pct
                            })
                except Exception as e:
                    logger.debug(f"Error scanning {symbol}: {e}")
                    continue
            
            # Sort movers by absolute change (highest volatility first)
            movers.sort(key=lambda x: abs(x['change']), reverse=True)
            mover_symbols = [m['symbol'] for m in movers[:15]]  # Top 15 movers
            
            # Always include core blue chips for liquidity
            core_stocks = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", 
                          "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "BAJFINANCE"]
            
            # Combine movers + core (remove duplicates, preserve order)
            watchlist = list(dict.fromkeys(mover_symbols + core_stocks))
            
            logger.info(f"✓ Dynamic watchlist: {len(watchlist)} stocks ({len(mover_symbols)} active movers + {len(core_stocks)} core)")
            
            # Cache the result
            self._watchlist_cache = watchlist
            self._watchlist_cache_time = now_ist()
            
            return watchlist
            
        except Exception as e:
            logger.error(f"Error building dynamic watchlist: {e}")
            
            # Fallback: Use curated active stocks
            fallback = [
                "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
                "TATASTEEL", "ITC", "BHARTIARTL", "SBIN", "BAJFINANCE",
                "MARUTI", "M&M", "SUNPHARMA", "HINDUNILVR", "AXISBANK",
                "KOTAKBANK", "ADANIPORTS", "NTPC", "TITAN", "ULTRACEMCO"
            ]
            logger.info(f"Using fallback watchlist: {len(fallback)} stocks")
            return fallback
    
    async def get_market_data(self, symbol: str, strategy_name: str):
        """Get market data for symbol
        
        Note: This method is now deprecated for live-quote strategies.
        Historical data access is not available with current API permissions.
        Keeping for backward compatibility.
        """
        try:
            # Get live quote instead of historical data
            quote = await self.broker.get_quote(symbol)
            return quote
        
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            return None
    
    async def news_processing_loop(self) -> None:
        """
        Process news items from ingestion queue
        Analyzes impact and triggers trades if conditions met
        """
        logger.info("📰 News processing loop started")
        
        while self.is_running:
            try:
                # Check if market is open (news matters most during market hours)
                if not self.monitoring.is_market_open():
                    await asyncio.sleep(60)
                    continue
                
                # Pop news items from queue (process in batches)
                news_items = self.news_ingestion.pop_news_queue(max_items=10)
                
                if not news_items:
                    await asyncio.sleep(5)  # Check queue every 5 seconds
                    continue
                
                logger.info(f"📥 Processing {len(news_items)} news items from queue")
                
                for news in news_items:
                    try:
                        # Get current quote for the symbol
                        quote = await self.broker.get_quote(news.symbol)
                        
                        if not quote:
                            logger.warning(f"[WARNING] Could not get quote for {news.symbol}")
                            continue
                        
                        # Convert to dict
                        quote_dict = {
                            'ltp': quote.last_price,
                            'open': quote.open,
                            'high': quote.high,
                            'low': quote.low,
                            'close': getattr(quote, 'close', quote.last_price),
                            'volume': quote.volume,
                            'avg_volume': getattr(quote, 'avg_volume', quote.volume),
                            'vwap': getattr(quote, 'vwap', quote.last_price)
                        }
                        
                        # Analyze news impact
                        impact_score = await self.news_detector.analyze_news_impact(
                            headline=news.headline,
                            source=news.source,
                            symbol=news.symbol,
                            category=news.category if news.category else self.news_ingestion._infer_category(news.headline),
                            timestamp=news.timestamp,
                            quote=quote_dict
                        )
                        
                        # INTELLIGENCE: Enhanced analysis with sentiment & clustering
                        intelligence_insights = self.news_intelligence.process_news(
                            symbol=news.symbol,
                            headline=news.headline,
                            timestamp=news.timestamp,
                            impact_score=impact_score.total_score
                        )
                        
                        # Log analysis
                        logger.info(f"[NEWS] Analysis: {news.symbol} | Score: {impact_score.total_score}/100 | Action: {impact_score.action.value}")
                        logger.info(f"[INTELLIGENCE] Sentiment: {intelligence_insights['sentiment_label']} | Conviction: {intelligence_insights['conviction']:.1f}")
                        
                        # Check if tradeable (intelligence layer adds extra filtering)
                        if not intelligence_insights['is_tradeable']:
                            logger.info(f"[BLOCKED] News filtered by intelligence layer")
                            continue
                        
                        # If action is TRADE_MODE, check governance and potentially execute
                        if impact_score.action == NewsAction.TRADE_MODE:
                            # Check all governance rules
                            passed, violations = self.news_governance.check_all_news_governance(
                                news_timestamp=news.timestamp,
                                current_price=quote_dict['ltp'],
                                price_at_detection=impact_score.price_at_detection,
                                quote=quote_dict,
                                action="BUY" if impact_score.direction.value == "BULLISH" else "SELL"
                            )
                            
                            if not passed:
                                logger.warning(f"[BLOCKED] News trade BLOCKED by governance: {news.symbol}")
                                for violation in violations:
                                    logger.warning(f"   - {violation}")
                                continue
                            
                            # APPROVED - News trade opportunity
                            logger.info(f"[APPROVED] NEWS TRADE APPROVED: {news.symbol}")
                            logger.info(f"   Headline: {news.headline}")
                            logger.info(f"   Impact Score: {impact_score.total_score}/100")
                            logger.info(f"   Direction: {impact_score.direction.value}")
                            logger.info(f"   Confidence: {impact_score.confidence.value}")
                            
                            # Send alert to user (don't auto-trade yet - Phase 2)
                            await self.monitoring.send_alert(
                                f"� NEWS TRADE OPPORTUNITY\n\n"
                                f"Symbol: {news.symbol}\n"
                                f"Headline: {news.headline[:100]}...\n"
                                f"Impact Score: {impact_score.total_score}/100\n"
                                f"Direction: {impact_score.direction.value}\n"
                                f"Market Reaction: {impact_score.market_reaction}/15\n"
                                f"Action: MANUAL REVIEW REQUIRED",
                                severity="WARNING"
                            )
                            
                            # Phase 2 - Auto-execute news trades (ACTIVE)
                            try:
                                from strategies.base import Signal
                                from datetime import datetime
                                
                                # Determine action based on direction
                                action = "BUY" if impact_score.direction.value == "bullish" else "SELL"
                                
                                # Calculate stop loss and target based on news mode
                                entry_price = quote_dict['ltp']
                                
                                if impact_score.mode.value == "intraday":
                                    # Intraday: Tighter stops, modest targets
                                    stop_loss_pct = 1.5  # 1.5% stop
                                    target_pct = 3.0  # 3% target (2:1 R:R)
                                elif impact_score.mode.value == "swing":
                                    # Swing: Wider stops, bigger targets
                                    stop_loss_pct = 2.5  # 2.5% stop
                                    target_pct = 6.0  # 6% target (2.4:1 R:R)
                                else:  # positional
                                    # Positional: Widest stops, largest targets
                                    stop_loss_pct = 4.0  # 4% stop
                                    target_pct = 10.0  # 10% target (2.5:1 R:R)
                                
                                if action == "BUY":
                                    stop_loss = entry_price * (1 - stop_loss_pct / 100)
                                    target = entry_price * (1 + target_pct / 100)
                                else:  # SELL/SHORT
                                    stop_loss = entry_price * (1 + stop_loss_pct / 100)
                                    target = entry_price * (1 - target_pct / 100)
                                
                                # Create signal
                                signal = Signal(
                                    symbol=news.symbol,
                                    action=action,
                                    entry_price=entry_price,
                                    stop_loss=stop_loss,
                                    target=target,
                                    quantity=0,  # Will be calculated by order manager
                                    confidence=intelligence_insights['conviction'] / 100.0,  # Use conviction score
                                    reason=f"NEWS: {news.headline[:80]}... | Sentiment: {intelligence_insights['sentiment_label']} | Conv: {intelligence_insights['conviction']:.0f}/100",
                                    timestamp=datetime.now()
                                )
                                
                                logger.info(f"[NEWS AUTO-TRADE] Executing: {news.symbol} {action}")
                                logger.info(f"   Entry: Rs{entry_price:.2f} | Stop: Rs{stop_loss:.2f} | Target: Rs{target:.2f}")
                                logger.info(f"   Conviction: {intelligence_insights['conviction']:.1f}/100")
                                logger.info(f"   Sentiment: {intelligence_insights['sentiment_label']} ({intelligence_insights['sentiment_score']:+.2f})")
                                
                                # Mark cluster as traded
                                if intelligence_insights['cluster']:
                                    self.news_intelligence.cluster_manager.mark_trade_triggered(
                                        intelligence_insights['cluster']
                                    )
                                
                                # Execute via order manager
                                trade = await self.order_manager.execute_signal(
                                    signal,
                                    strategy_name="NewsImpact"
                                )
                                
                                if trade:
                                    logger.info(f"[OK] News trade executed: {trade.id} | {news.symbol} | Qty: {trade.quantity}")
                                    
                                    # Update alert with execution details
                                    await self.monitoring.send_alert(
                                        f"[NEWS TRADE EXECUTED]\n\n"
                                        f"Symbol: {news.symbol} {action}\n"
                                        f"Headline: {news.headline[:100]}...\n"
                                        f"Impact Score: {impact_score.total_score}/100\n"
                                        f"Entry: Rs{entry_price:.2f} x {trade.quantity} shares\n"
                                        f"Stop Loss: Rs{stop_loss:.2f}\n"
                                        f"Target: Rs{target:.2f}\n"
                                        f"Mode: {impact_score.mode.value}",
                                        severity="INFO"
                                    )
                                else:
                                    logger.warning(f"[FAIL] News trade rejected by order manager: {news.symbol}")
                            
                            except Exception as trade_error:
                                logger.error(f"[ERROR] News trade execution failed for {news.symbol}: {trade_error}")
                                import traceback
                                traceback.print_exc()
                        
                        elif impact_score.action == NewsAction.WATCH:
                            logger.info(f"[WATCH] {news.symbol} | {news.headline[:60]}...")
                        
                        else:  # IGNORE
                            logger.debug(f"⏭️ IGNORED: {news.symbol} | Score too low ({impact_score.total_score})")
                    
                    except Exception as e:
                        logger.error(f"❌ Error processing news for {news.symbol}: {e}")
                        continue
                
                # Brief pause before next batch
                await asyncio.sleep(1)
            
            except Exception as e:
                logger.error(f"❌ News processing loop error: {e}")
                await asyncio.sleep(10)
        
        logger.info("⏹️ News processing loop stopped")
    
    async def shutdown(self) -> None:
        """Shutdown the system gracefully"""
        logger.info("Shutting down system...")
        
        try:
            self.is_running = False
            
            # Stop news ingestion
            if self.news_ingestion:
                await self.news_ingestion.stop_polling()
            
            # Close all open positions if configured
            # await self.close_all_positions()
            
            # Disconnect broker
            if self.broker:
                await self.broker.disconnect()
            
            # Send shutdown alert
            if self.monitoring:
                await self.monitoring.send_alert(
                    "🛑 AutoTrade AI System Shutdown",
                    severity="INFO"
                )
            
            # Close database
            if self.db:
                self.db.close()
            
            logger.info("System shutdown complete")
        
        except Exception as e:
            logger.error(f"Shutdown error: {e}")


def main():
    """Main entry point"""
    # Create logs directory
    import os
    os.makedirs('logs', exist_ok=True)
    
    # Start system
    system = TradingSystem()
    
    try:
        asyncio.run(system.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    main()
