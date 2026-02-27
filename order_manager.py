"""Order Manager - Handles order placement, tracking, and execution"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import asyncio

from models import Trade, TradeStatus, TradeDirection, SystemLog
from brokers.base import BaseBroker, Order, TransactionType, OrderType, OrderStatus
from risk_engine import RiskEngine
from strategies.base import Signal
from config import settings
from transaction_cost_calculator import cost_calculator

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages order lifecycle and execution

    Responsibilities:
    - Place orders via broker
    - Track order status
    - Place and manage stop losses
    - Handle order failures
    - Update trade records
    - Coordinate with risk engine
    - CME gate (capital_manager) enforces portfolio-level rules
    """

    def __init__(
        self,
        broker: BaseBroker,
        risk_engine: RiskEngine,
        db_session: Session,
        capital_manager=None,   # Optional[CapitalManager] — avoids circular import
    ):
        self.broker = broker
        self.risk_engine = risk_engine
        self.db = db_session
        self.capital_manager = capital_manager   # CME gatekeeper
        self.active_orders: Dict[str, Trade] = {}  # order_id -> Trade
        self.position_reconciliation_interval = settings.position_reconciliation_interval
    
    async def execute_signal(self, signal: Signal, strategy_name: str) -> Optional[Trade]:
        """Execute a trading signal
        
        Args:
            signal: Trading signal from strategy
            strategy_name: Name of the strategy generating the signal
            
        Returns:
            Trade object if successful, None otherwise
        """
        try:
            logger.info(f"Executing signal for {signal.symbol}: {signal.action}")
            
            # 0. CRITICAL: Validate intraday trading hours (9:15 AM - 3:20 PM IST)
            # MIS (Margin Intraday Squareoff) orders can only be placed during market hours
            from datetime import time
            from utils import now_ist
            
            current_time = now_ist().time()
            intraday_start = time(9, 15)
            intraday_end = time(15, 20)  # 3:20 PM - last time for new intraday positions
            
            if not (intraday_start <= current_time <= intraday_end):
                logger.error(
                    f"[X] INTRADAY ORDER REJECTED - {signal.symbol}: "
                    f"MIS orders only allowed between 9:15 AM - 3:20 PM IST. "
                    f"Current time: {current_time.strftime('%H:%M:%S')}"
                )
                self._log_event(
                    event_type="TIMING_REJECTED",
                    message=f"Intraday order outside allowed hours (9:15 AM - 3:20 PM IST)",
                    symbol=signal.symbol,
                    severity="WARNING"
                )
                return None
            
            # 1. Check for existing open/pending positions
            # Note: REJECTED and CANCELLED orders are NOT blocked - they can be retried
            existing_position = self.db.query(Trade).filter(
                Trade.symbol == signal.symbol,
                Trade.status.in_([TradeStatus.OPEN, TradeStatus.PENDING])
            ).first()
            
            if existing_position:
                logger.warning(
                    f"Position already exists for {signal.symbol} "
                    f"(ID: {existing_position.id}, Status: {existing_position.status}). "
                    f"Rejecting duplicate signal."
                )
                self._log_event(
                    event_type="DUPLICATE_SIGNAL_REJECTED",
                    message=f"Duplicate position detected for {signal.symbol}",
                    symbol=signal.symbol,
                    severity="WARNING"
                )
                return None
            
            # Check if there was a recent rejected order (for logging/monitoring)
            recent_rejected = self.db.query(Trade).filter(
                Trade.symbol == signal.symbol,
                Trade.status == TradeStatus.REJECTED
            ).order_by(Trade.created_at.desc()).first()
            
            if recent_rejected:
                rejection_reason = recent_rejected.notes or ""
                reason_lower = rejection_reason.lower()
                
                # Special handling for insufficient funds - adjust quantity and retry
                if "insufficient funds" in reason_lower or "balance" in reason_lower:
                    logger.warning(
                        f"⚠️ Previous order rejected for insufficient funds: {signal.symbol}. "
                        f"Attempting to calculate affordable quantity..."
                    )
                    
                    # Update available capital from broker
                    await self.risk_engine.update_available_capital()
                    available = self.risk_engine.available_capital
                    
                    # Reserve 10% buffer for fees/charges
                    usable_capital = available * 0.90
                    
                    # Calculate affordable quantity
                    max_affordable_qty = int(usable_capital / signal.entry_price)
                    
                    # Apply risk management: use only 15% of capital per trade
                    max_per_trade = self.risk_engine.get_max_capital_per_trade()
                    risk_based_qty = int(max_per_trade / signal.entry_price)
                    
                    # Use the smaller of the two
                    affordable_qty = min(max_affordable_qty, risk_based_qty)
                    
                    if affordable_qty < 1:
                        logger.error(
                            f"❌ Cannot afford even 1 share of {signal.symbol} @ Rs{signal.entry_price:.2f}. "
                            f"Available: Rs{available:.2f}, Required: Rs{signal.entry_price:.2f}"
                        )
                        return None
                    
                    # Update signal quantity with affordable amount
                    original_qty = signal.quantity
                    signal.quantity = affordable_qty
                    logger.info(
                        f"[OK] Adjusted quantity for {signal.symbol}: {original_qty} -> {affordable_qty} shares "
                        f"(Cost: Rs{affordable_qty * signal.entry_price:.2f}, Available: Rs{available:.2f})"
                    )
                    # Continue with adjusted quantity
                
                else:
                    # Analyze other rejection reasons
                    non_retryable_keywords = [
                        "invalid symbol",
                        "market closed",
                        "not allowed",
                        "circuit breaker",
                        "banned",
                        "suspended",
                        "quantity limit",
                        "freeze quantity"
                    ]
                    
                    is_non_retryable = any(keyword in reason_lower for keyword in non_retryable_keywords)
                    
                    if is_non_retryable:
                        logger.warning(
                            f"Retry blocked for {signal.symbol}: Previous rejection was non-retryable. "
                            f"Reason: {rejection_reason}"
                        )
                        self._log_event(
                            event_type="RETRY_BLOCKED",
                            message=f"Non-retryable rejection: {rejection_reason}",
                            symbol=signal.symbol,
                            severity="WARNING"
                        )
                        return None
                    else:
                        logger.info(
                            f"Retry allowed for {signal.symbol}: Previous order ID {recent_rejected.id} "
                            f"was REJECTED with retryable reason: {rejection_reason}"
                        )
            
            # 1. COST-AWARE FILTER (CRITICAL)
            # Validate trade can overcome transaction costs BEFORE proceeding
            if signal.target and signal.target > 0:
                expected_move = abs(signal.target - signal.entry_price)
                
                # Validate profitability with transaction costs
                cost_approved, cost_reason, cost_metrics = cost_calculator.validate_trade_profitability(
                    quantity=signal.quantity,
                    entry_price=signal.entry_price,
                    expected_move_per_share=expected_move,
                    max_cost_ratio=0.25  # 25% maximum cost-to-profit ratio
                )
                
                if not cost_approved:
                    logger.error(
                        f"[COST FILTER] {signal.symbol} REJECTED: {cost_reason}"
                    )
                    logger.error(
                        f"  Entry: ₹{signal.entry_price:.2f}, Target: ₹{signal.target:.2f}, Move: ₹{expected_move:.2f}"
                    )
                    logger.error(
                        f"  Total Costs: ₹{cost_metrics.get('total_cost', 0):.2f} "
                        f"(₹{cost_metrics.get('cost_per_share', 0):.2f}/share)"
                    )
                    logger.error(
                        f"  Cost Ratio: {cost_metrics.get('cost_ratio', 0):.1f}% "
                        f"(Threshold: 25%)"
                    )
                    logger.error(
                        f"  Expected Net Profit: ₹{cost_metrics.get('expected_net_profit', 0):.2f}"
                    )
                    
                    self._log_event(
                        event_type="COST_FILTER_REJECTED",
                        message=f"Cost filter: {cost_reason}",
                        symbol=signal.symbol,
                        severity="WARNING"
                    )
                    return None
                
                # Log cost metrics for approved trades
                logger.info(
                    f"[COST FILTER] {signal.symbol} APPROVED ✓"
                )
                logger.info(
                    f"  Expected move: ₹{expected_move:.2f}, "
                    f"Costs: ₹{cost_metrics.get('total_cost', 0):.2f} "
                    f"(₹{cost_metrics.get('cost_per_share', 0):.2f}/share)"
                )
                logger.info(
                    f"  Cost ratio: {cost_metrics.get('cost_ratio', 0):.1f}%, "
                    f"Expected net profit: ₹{cost_metrics.get('expected_net_profit', 0):.2f}"
                )
            else:
                # No target provided - use minimum cost check
                cost_per_share = cost_calculator.get_cost_per_share(signal.quantity, signal.entry_price)
                min_move_required = cost_per_share * 2  # 2x buffer
                
                logger.warning(
                    f"[COST FILTER] {signal.symbol}: No target price provided. "
                    f"Minimum required move: ₹{min_move_required:.2f}/share"
                )
            
            # 1.5 CME GATE — portfolio-level capital & risk rules
            if self.capital_manager is not None:
                cme = self.capital_manager.approve_trade(
                    symbol=signal.symbol,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    strategy_name=strategy_name,
                    product=getattr(signal, 'product', 'CNC'),
                    proposed_quantity=signal.quantity,
                )
                if not cme.approved:
                    logger.warning(f"[CME] {signal.symbol} REJECTED: {cme.reason}")
                    self._log_event(
                        event_type="CME_REJECTED",
                        message=cme.reason,
                        symbol=signal.symbol,
                        severity="WARNING"
                    )
                    return None

                # Apply CME-adjusted quantity (risk-sized, not strategy-sized)
                if cme.adjusted_quantity > 0 and cme.adjusted_quantity != signal.quantity:
                    logger.info(
                        f"[CME] {signal.symbol} quantity adjusted: "
                        f"{signal.quantity} → {cme.adjusted_quantity} "
                        f"(risk=₹{cme.risk_per_trade:.0f}, mode={cme.risk_mode})"
                    )
                    signal.quantity = cme.adjusted_quantity

            # 2. Risk check with cost-awareness
            risk_check = await self.risk_engine.check_trade_approval(
                symbol=signal.symbol,
                quantity=signal.quantity,
                entry_price=signal.entry_price,
                stop_price=signal.stop_loss,
                expected_target=signal.target  # Pass target for enhanced validation
            )
            
            logger.info(f"[DEBUG] Risk check result for {signal.symbol}: approved={risk_check.approved}, reason={risk_check.reason}")
            
            if not risk_check.approved:
                logger.error(
                    f"[X] TRADE REJECTED - {signal.symbol}: {risk_check.reason}"
                )
                self._log_event(
                    event_type="TRADE_REJECTED",
                    message=risk_check.reason,
                    symbol=signal.symbol,
                    severity="WARNING"
                )
                return None
            
            logger.info(f"[DEBUG] Risk check passed for {signal.symbol}, calculating position size...")
            
            # 3. Calculate proper position size based on risk
            trade_risk = abs(signal.entry_price - signal.stop_loss) * signal.quantity
            proper_quantity = self._calculate_position_size(
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                max_risk=settings.max_per_trade_risk
            )
            
            logger.info(f"[DEBUG] Position size calculated for {signal.symbol}: {proper_quantity} shares")
            
            # 4. Check if we're in paper trading mode
            if settings.paper_trading:
                return await self._execute_paper_trade(signal, strategy_name, proper_quantity)
            
            # 5. Place actual order
            direction = TradeDirection.LONG if signal.action == "BUY" else TradeDirection.SHORT
            trade_product = getattr(signal, 'product', 'CNC')  # CNC default = swing

            order = await self.broker.place_order(
                symbol=signal.symbol,
                transaction_type=TransactionType.BUY if signal.action == "BUY" else TransactionType.SELL,
                quantity=proper_quantity,
                order_type=OrderType.LIMIT,
                price=signal.entry_price,
                product=trade_product
            )
            logger.info(f"Order product type: {trade_product} for {signal.symbol}")
            
            # 5a. Handle rejected orders - save to database with reason
            if order.status == OrderStatus.REJECTED:
                rejection_reason = order.message or "Unknown rejection reason"
                logger.error(f"Order rejected by broker: {rejection_reason}")
                
                # Save rejected order to database for tracking
                rejected_trade = Trade(
                    symbol=signal.symbol,
                    strategy_name=strategy_name,
                    direction=direction,
                    entry_price=signal.entry_price,
                    quantity=proper_quantity,
                    stop_price=signal.stop_loss,
                    target_price=signal.target,
                    risk_amount=abs(signal.entry_price - signal.stop_loss) * proper_quantity,
                    broker_order_id=order.order_id,
                    status=TradeStatus.REJECTED,
                    notes=f"REJECTED: {rejection_reason}",
                    risk_reward_ratio=abs(signal.target - signal.entry_price) / abs(signal.entry_price - signal.stop_loss)
                )
                
                try:
                    self.db.add(rejected_trade)
                    self.db.commit()
                    logger.info(f"[OK] Rejected order saved to database: ID={rejected_trade.id}, Reason: {rejection_reason}")
                except Exception as db_error:
                    self.db.rollback()
                    logger.error(f"Failed to save rejected order: {db_error}")
                
                self._log_event(
                    event_type="ORDER_REJECTED",
                    message=f"Order rejected: {rejection_reason}",
                    symbol=signal.symbol,
                    severity="ERROR"
                )
                return None
            
            # 6. Create trade record — stamp product type in notes for exit logic
            trade = Trade(
                symbol=signal.symbol,
                strategy_name=strategy_name,
                direction=direction,
                entry_price=signal.entry_price,
                quantity=proper_quantity,
                stop_price=signal.stop_loss,
                target_price=signal.target,
                risk_amount=abs(signal.entry_price - signal.stop_loss) * proper_quantity,
                broker_order_id=order.order_id,
                status=TradeStatus.PENDING,
                notes=f"product:{trade_product}",
                risk_reward_ratio=abs(signal.target - signal.entry_price) / abs(signal.entry_price - signal.stop_loss)
            )
            
            # 6a. Save to database with error handling
            try:
                self.db.add(trade)
                self.db.commit()
                self.db.refresh(trade)
                logger.info(f"✅ [DATABASE] Trade saved: ID={trade.id}, Symbol={signal.symbol}, Qty={proper_quantity}")
                
                # Verify save
                verify_trade = self.db.query(Trade).filter(Trade.id == trade.id).first()
                if not verify_trade:
                    raise Exception(f"Trade ID={trade.id} not found after commit!")
                    
            except Exception as db_error:
                self.db.rollback()
                logger.error(f"❌ [DATABASE] CRITICAL: Failed to save trade to database: {db_error}")
                logger.error(f"Trade details: {signal.symbol} x {proper_quantity} @ Rs{signal.entry_price}")
                logger.error(f"Database URL: {self.db.bind.url}")
                
                # Try to cancel the broker order since we can't track it
                try:
                    await self.broker.cancel_order(order.order_id)
                    logger.warning(f"Cancelled broker order {order.order_id} due to database error")
                except Exception as cancel_error:
                    logger.error(f"CRITICAL: Failed to cancel order after DB error: {cancel_error}")
                    logger.error(f"MANUAL INTERVENTION REQUIRED: Order {order.order_id} may be active!")
                
                return None
            
            # 7. Track order
            self.active_orders[order.order_id] = trade
            
            # 8. Monitor order status
            asyncio.create_task(self._monitor_order(order.order_id, trade.id))
            
            logger.info(
                f"Order placed for {signal.symbol}: ID={order.order_id}, "
                f"Qty={proper_quantity}, Price=Rs{signal.entry_price:.2f}"
            )
            
            self._log_event(
                event_type="ORDER_PLACED",
                message=f"Order placed: {signal.symbol} x {proper_quantity} @ Rs{signal.entry_price:.2f}",
                symbol=signal.symbol,
                trade_id=trade.id,
                order_id=order.order_id,
                severity="INFO"
            )
            
            return trade
            
        except Exception as e:
            logger.error(f"Failed to execute signal: {e}")
            self._log_event(
                event_type="ORDER_ERROR",
                message=f"Failed to execute signal: {str(e)}",
                symbol=signal.symbol,
                severity="ERROR"
            )
            return None
    
    async def _execute_paper_trade(
        self,
        signal: Signal,
        strategy_name: str,
        quantity: int
    ) -> Trade:
        """Execute a paper trade (simulation)"""
        logger.info(f"[PAPER] Executing signal for {signal.symbol}")
        
        direction = TradeDirection.LONG if signal.action == "BUY" else TradeDirection.SHORT
        
        trade = Trade(
            symbol=signal.symbol,
            strategy_name=strategy_name,
            direction=direction,
            entry_price=signal.entry_price,
            quantity=quantity,
            stop_price=signal.stop_loss,
            target_price=signal.target,
            risk_amount=abs(signal.entry_price - signal.stop_loss) * quantity,
            broker_order_id=f"PAPER_{datetime.now().timestamp()}",
            status=TradeStatus.OPEN,  # Assume immediate fill in paper trading
            risk_reward_ratio=abs(signal.target - signal.entry_price) / abs(signal.entry_price - signal.stop_loss)
        )
        
        try:
            self.db.add(trade)
            self.db.commit()
            self.db.refresh(trade)
            logger.info(f"[OK] [PAPER] Trade record saved: ID={trade.id}, Symbol={signal.symbol}")
        except Exception as db_error:
            self.db.rollback()
            logger.error(f"[PAPER] CRITICAL: Failed to save trade to database: {db_error}")
            raise
        
        # Record with risk engine
        capital_deployed = signal.entry_price * quantity
        await self.risk_engine.record_trade_entry(trade.id, capital_deployed)
        
        logger.info(f"[PAPER] Trade opened: ID={trade.id}")
        return trade
    
    async def _monitor_order(self, order_id: str, trade_id: int) -> None:
        """Monitor order status until filled or cancelled"""
        try:
            max_attempts = 60  # Monitor for up to 60 seconds
            attempt = 0
            
            while attempt < max_attempts:
                await asyncio.sleep(1)
                attempt += 1
                
                # Get order status
                order = await self.broker.get_order_status(order_id)
                trade = self.db.query(Trade).filter(Trade.id == trade_id).first()
                
                if not trade:
                    logger.error(f"Trade not found: {trade_id}")
                    break
                
                # Update trade status based on order status
                if order.status == OrderStatus.COMPLETE:
                    trade.status = TradeStatus.OPEN
                    trade.entry_price = order.average_price
                    trade.broker_entry_id = order.order_id
                    self.db.commit()
                    
                    # Place stop loss
                    await self._place_stop_loss(trade)
                    
                    # Record with risk engine
                    capital_deployed = trade.entry_price * trade.quantity
                    await self.risk_engine.record_trade_entry(trade.id, capital_deployed)
                    
                    logger.info(f"Order filled: {order_id} at Rs{order.average_price:.2f}")
                    
                    self._log_event(
                        event_type="ORDER_FILLED",
                        message=f"Order filled at Rs{order.average_price:.2f}",
                        symbol=trade.symbol,
                        trade_id=trade.id,
                        order_id=order_id,
                        severity="INFO"
                    )
                    
                    break
                    
                elif order.status in [OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    trade.status = TradeStatus.CANCELLED if order.status == OrderStatus.CANCELLED else TradeStatus.REJECTED
                    self.db.commit()
                    
                    logger.warning(f"Order {order.status.value}: {order_id}")
                    
                    self._log_event(
                        event_type=f"ORDER_{order.status.value}",
                        message=order.message or "No message",
                        symbol=trade.symbol,
                        trade_id=trade.id,
                        order_id=order_id,
                        severity="WARNING"
                    )
                    
                    break
            
            # Remove from active orders
            if order_id in self.active_orders:
                del self.active_orders[order_id]
                
        except Exception as e:
            logger.error(f"Error monitoring order {order_id}: {e}")
    
    async def _place_stop_loss(self, trade: Trade) -> bool:
        """Place stop loss order for a trade"""
        try:
            # Place SL-M (Stop Loss Market) order
            sl_order = await self.broker.place_order(
                symbol=trade.symbol,
                transaction_type=TransactionType.SELL if trade.direction == TradeDirection.LONG else TransactionType.BUY,
                quantity=trade.quantity,
                order_type=OrderType.SLM,
                trigger_price=trade.stop_price,
                product="MIS"
            )
            
            trade.broker_sl_id = sl_order.order_id
            self.db.commit()
            
            logger.info(
                f"Stop loss placed for {trade.symbol}: "
                f"Trigger Rs{trade.stop_price:.2f}, Order ID {sl_order.order_id}"
            )
            
            self._log_event(
                event_type="STOP_LOSS_PLACED",
                message=f"SL placed at Rs{trade.stop_price:.2f}",
                symbol=trade.symbol,
                trade_id=trade.id,
                order_id=sl_order.order_id,
                severity="INFO"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to place stop loss for trade {trade.id}: {e}")
            
            # CRITICAL: If SL placement fails, exit position immediately
            await self.close_position(trade.id, reason="SL_PLACEMENT_FAILED")
            
            return False
    
    async def close_position(
        self,
        trade_id: int,
        reason: str = "MANUAL",
        exit_price: Optional[float] = None
    ) -> bool:
        """Close an open position
        
        Args:
            trade_id: Trade ID to close
            reason: Reason for closing
            exit_price: Override exit price (None = market price)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            trade = self.db.query(Trade).filter(Trade.id == trade_id).first()
            
            if not trade or trade.status != TradeStatus.OPEN:
                logger.warning(f"Trade {trade_id} not found or not open")
                return False
            
            # Cancel stop loss if exists
            if trade.broker_sl_id:
                await self.broker.cancel_order(trade.broker_sl_id)
            
            # Get current price if not provided
            if exit_price is None:
                quote = await self.broker.get_quote(trade.symbol)
                exit_price = quote.last_price
            
            # Place exit order
            exit_order = await self.broker.place_order(
                symbol=trade.symbol,
                transaction_type=TransactionType.SELL if trade.direction == TradeDirection.LONG else TransactionType.BUY,
                quantity=trade.quantity,
                order_type=OrderType.MARKET,
                product="MIS"
            )
            
            # Wait for fill
            await asyncio.sleep(2)
            exit_order_status = await self.broker.get_order_status(exit_order.order_id)
            
            if exit_order_status.status == OrderStatus.COMPLETE:
                actual_exit_price = exit_order_status.average_price
            else:
                actual_exit_price = exit_price  # Fallback
            
            # Calculate P&L
            if trade.direction == TradeDirection.LONG:
                pnl = (actual_exit_price - trade.entry_price) * trade.quantity
            else:
                pnl = (trade.entry_price - actual_exit_price) * trade.quantity
            
            # Estimate charges (you should calculate accurately based on broker)
            charges = self._calculate_charges(
                trade.entry_price,
                actual_exit_price,
                trade.quantity
            )
            
            net_pnl = pnl - charges
            
            # Update trade
            trade.exit_price = actual_exit_price
            trade.exit_timestamp = datetime.now()
            trade.exit_reason = reason
            trade.realized_pnl = pnl
            trade.charges = charges
            trade.net_pnl = net_pnl
            trade.status = TradeStatus.CLOSED
            trade.actual_risk_reward = abs(actual_exit_price - trade.entry_price) / abs(trade.entry_price - trade.stop_price)
            trade.broker_exit_id = exit_order.order_id
            
            self.db.commit()
            
            # Update risk engine
            is_winner = net_pnl > 0
            await self.risk_engine.record_trade_exit(trade_id, net_pnl, is_winner)
            
            logger.info(
                f"Position closed: {trade.symbol}, P&L Rs{net_pnl:.2f}, Reason: {reason}"
            )
            
            self._log_event(
                event_type="POSITION_CLOSED",
                message=f"Position closed: P&L Rs{net_pnl:.2f}, Reason: {reason}",
                symbol=trade.symbol,
                trade_id=trade.id,
                severity="INFO"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to close position {trade_id}: {e}")
            return False
    
    async def reconcile_positions(self) -> None:
        """Reconcile positions between database and broker
        
        Critical safety mechanism to detect mismatches
        """
        try:
            # Get open trades from database
            db_positions = self.db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN
            ).all()
            
            # Get positions from broker
            broker_positions = await self.broker.get_positions()
            
            # Create symbol -> quantity maps (sum quantities for multiple trades of same symbol)
            db_map = {}
            for t in db_positions:
                db_map[t.symbol] = db_map.get(t.symbol, 0) + t.quantity
            
            broker_map = {p.symbol: p.quantity for p in broker_positions}
            
            # Check for mismatches
            all_symbols = set(db_map.keys()) | set(broker_map.keys())
            
            for symbol in all_symbols:
                db_qty = db_map.get(symbol, 0)
                broker_qty = broker_map.get(symbol, 0)
                
                if db_qty != broker_qty:
                    logger.critical(
                        f"POSITION MISMATCH: {symbol} - "
                        f"DB: {db_qty}, Broker: {broker_qty}"
                    )
                    
                    self._log_event(
                        event_type="POSITION_MISMATCH",
                        message=f"Mismatch detected: DB={db_qty}, Broker={broker_qty}",
                        symbol=symbol,
                        severity="CRITICAL"
                    )
                    
                    # Handle mismatch - close broker position if exists
                    if broker_qty > 0:
                        logger.critical(f"Flattening broker position for {symbol}")
                        # Implement emergency position flattening here
                        
        except Exception as e:
            logger.error(f"Position reconciliation failed: {e}")
    
    def _calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        max_risk: float
    ) -> int:
        """Calculate position size based on risk and governance limits
        
        Uses AI Investor Governance Policy Section 3 (Capital Allocation)
        """
        # Traditional risk-based calculation
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return 1
        
        risk_based_qty = int(max_risk / risk_per_share)
        
        # Get governance maximum for intraday layer
        from governance import TradingLayer
        governance_max = self.risk_engine.governance.get_layer_max_position_size(
            layer=TradingLayer.INTRADAY,
            entry_price=entry_price
        )
        
        # Apply position size multiplier (drawdown/volatility adjustment)
        multiplier = self.risk_engine.governance.get_position_size_multiplier()
        
        # Take the most conservative limit
        final_qty = min(risk_based_qty, governance_max)
        final_qty = int(final_qty * multiplier)  # Apply multiplier
        
        logger.debug(
            f"Position sizing: risk_based={risk_based_qty}, governance_max={governance_max}, "
            f"multiplier={multiplier:.2f}, final={final_qty}"
        )
        
        return max(final_qty, 1)
    
    def _calculate_charges(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int
    ) -> float:
        """Calculate estimated brokerage and charges
        
        This is a simplified calculation. Implement accurate charges based on your broker.
        Includes: Brokerage, STT, Transaction charges, GST, SEBI charges, Stamp duty
        """
        turnover = (entry_price + exit_price) * quantity
        
        # Zerodha-like charges (approximate)
        brokerage = min(20, turnover * 0.0003) * 2  # Rs20 or 0.03% per order
        stt = exit_price * quantity * 0.00025  # 0.025% on sell
        transaction_charges = turnover * 0.0000345
        gst = brokerage * 0.18
        sebi_charges = turnover * 0.000001
        stamp_duty = turnover * 0.00003
        
        total_charges = brokerage + stt + transaction_charges + gst + sebi_charges + stamp_duty
        
        return round(total_charges, 2)
    
    def _log_event(
        self,
        event_type: str,
        message: str,
        symbol: Optional[str] = None,
        trade_id: Optional[int] = None,
        order_id: Optional[str] = None,
        severity: str = "INFO"
    ) -> None:
        """Log system event to database"""
        try:
            log = SystemLog(
                event_type=event_type,
                message=message,
                severity=severity,
                symbol=symbol,
                trade_id=trade_id,
                order_id=order_id
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
    
    async def sync_broker_positions(self) -> bool:
        """Sync all broker positions to database
        
        This ensures database always reflects actual broker state.
        Call this periodically or when database/broker are out of sync.
        
        Returns:
            True if sync successful, False otherwise
        """
        try:
            logger.info("[SYNC] Starting broker position sync...")
            
            # Get a user_id from the database (use first user if exists)
            from models import User
            user = self.db.query(User).filter(User.is_active == True).first()
            if not user:
                logger.error("No active users found in database - cannot sync positions")
                return False
            user_id = user.id
            
            # Get all broker positions
            broker_positions = await self.broker.get_positions()
            
            if not broker_positions:
                logger.info("No broker positions to sync")
                return True
            
            # Get all open trades from database
            db_open_trades = self.db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN
            ).all()
            
            # Create map of existing trades by symbol
            db_symbol_map = {t.symbol: t for t in db_open_trades}
            
            synced_count = 0
            updated_count = 0
            
            for pos in broker_positions:
                symbol = pos.symbol
                broker_qty = abs(pos.quantity)
                avg_price = pos.average_price
                
                if symbol in db_symbol_map:
                    # Trade exists - verify quantity matches
                    trade = db_symbol_map[symbol]
                    
                    if trade.quantity != broker_qty:
                        logger.warning(
                            f"Quantity mismatch for {symbol}: DB={trade.quantity}, Broker={broker_qty}. "
                            f"Updating database."
                        )
                        trade.quantity = broker_qty
                        updated_count += 1
                    
                    if abs(trade.entry_price - avg_price) > 0.01:
                        logger.warning(
                            f"Price mismatch for {symbol}: DB=Rs{trade.entry_price:.2f}, "
                            f"Broker=Rs{avg_price:.2f}. Updating database."
                        )
                        trade.entry_price = avg_price
                        updated_count += 1
                else:
                    # Trade doesn't exist in DB - create it
                    logger.warning(
                        f"Broker position {symbol} not in database. Creating database record."
                    )
                    
                    direction = TradeDirection.LONG if pos.quantity > 0 else TradeDirection.SHORT
                    
                    new_trade = Trade(
                        user_id=user_id,  # Add user_id for synced positions
                        symbol=symbol,
                        strategy_name="live_simple",  # Default
                        direction=direction,
                        entry_price=avg_price,
                        quantity=broker_qty,
                        entry_timestamp=datetime.now(),
                        stop_price=avg_price * 0.98,  # 2% default SL
                        target_price=avg_price * 1.03,  # 3% default target
                        risk_amount=broker_qty * avg_price * 0.02,
                        status=TradeStatus.OPEN,
                        broker_entry_id=f"SYNC_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        notes=f"Auto-synced from broker at {datetime.now().isoformat()}"
                    )
                    
                    self.db.add(new_trade)
                    synced_count += 1
            
            # Commit all changes
            if synced_count > 0 or updated_count > 0:
                self.db.commit()
                logger.info(
                    f"✅ Broker sync complete: {synced_count} new trades added, "
                    f"{updated_count} trades updated"
                )
            else:
                logger.info("✅ Broker sync complete: Database already in sync")
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Broker position sync failed: {e}")
            import traceback
            traceback.print_exc()
            return False
