"""Risk Engine - Core risk management system with cost-aware filtering"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func

from config import settings
from models import Trade, DailyMetrics, TradeStatus
from database import redis_client
from governance import GovernanceEngine, TradingLayer, SystemMode
from transaction_cost_calculator import cost_calculator

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result of a risk check"""
    approved: bool
    reason: Optional[str] = None
    risk_score: float = 0.0


class RiskEngine:
    """Risk management engine
    
    Enforces:
    - Daily loss limits
    - Per-trade risk limits
    - Position limits
    - Capital exposure limits
    - Consecutive loss limits
    """
    
    def __init__(self, db_session: Session, broker=None):
        self.db = db_session
        self.broker = broker
        self.max_daily_loss = settings.max_daily_loss
        self.max_per_trade_risk = settings.max_per_trade_risk
        self.max_open_trades = settings.max_open_trades
        self.max_capital_per_trade_percent = getattr(settings, 'max_capital_per_trade_percent', 25.0)
        self.max_exposure_percent = settings.max_exposure_percent
        self.consecutive_loss_limit = settings.consecutive_loss_limit
        self.initial_capital = settings.initial_capital  # Fallback value
        self.available_capital = settings.initial_capital  # Will be updated from broker
        
        # Governance engine will be initialized after getting broker capital
        # This prevents false drawdown alerts on startup
        self.governance = None
        logger.info("Risk engine initialized (governance pending capital update)")
        
        # Redis keys for fast access
        self.DAILY_LOSS_KEY = f"risk:daily_loss:{date.today().isoformat()}"
        self.OPEN_POSITIONS_KEY = "risk:open_positions"
        self.CONSECUTIVE_LOSSES_KEY = "risk:consecutive_losses"
        self.TRADING_HALTED_KEY = "risk:trading_halted"
    
    async def update_available_capital(self) -> float:
        """Fetch and update available capital from broker
        
        Returns:
            Available capital in INR
        """
        if self.broker:
            try:
                margins = await self.broker.get_margins()
                self.available_capital = margins.get("available_cash", self.initial_capital)
                
                # Initialize governance engine on first capital update
                if self.governance is None:
                    self.governance = GovernanceEngine(initial_capital=self.available_capital)
                    logger.info("[OK] Governance engine initialized with AI Investor Policy")
                    logger.info(f"  Capital: Rs{self.available_capital:,.2f}")
                else:
                    # Update governance engine with current capital
                    self.governance.update_capital(self.available_capital)
                
                logger.info(f"Updated available capital: Rs{self.available_capital:,.2f}")
                return self.available_capital
            except Exception as e:
                logger.warning(f"Failed to fetch capital from broker: {e}. Using fallback.")
                self.available_capital = self.initial_capital
                
                # Initialize governance with fallback if needed
                if self.governance is None:
                    self.governance = GovernanceEngine(initial_capital=self.available_capital)
                    logger.warning("Governance initialized with fallback capital")
        
        return self.available_capital
    
    def get_max_capital_per_trade(self) -> float:
        """Calculate maximum capital per trade based on available capital
        
        Returns:
            Maximum capital allowed per trade in INR
        """
        # Defensive: ensure attribute exists
        if not hasattr(self, 'max_capital_per_trade_percent'):
            self.max_capital_per_trade_percent = getattr(settings, 'max_capital_per_trade_percent', 25.0)
            logger.warning(f"max_capital_per_trade_percent was missing, set to {self.max_capital_per_trade_percent}%")
        
        return (self.max_capital_per_trade_percent / 100) * self.available_capital
    
    async def check_trade_approval(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        stop_price: float,
        expected_target: float = None
    ) -> RiskCheckResult:
        """Comprehensive pre-trade risk check with cost-awareness
        
        Args:
            symbol: Trading symbol
            quantity: Number of shares
            entry_price: Entry price per share
            stop_price: Stop loss price
            expected_target: Expected target price (for cost validation)
            
        Returns:
            RiskCheckResult with approval status
        """
        
        # GOVERNANCE POLICY CHECK (Section 6 - highest priority)
        # Get current exposure for governance check
        current_exposure = await self._get_current_exposure()
        
        # Use INTRADAY layer by default (current system only has intraday)
        from governance import TradingLayer
        
        if self.governance is None:
            logger.error("Governance engine not initialized - cannot approve trades")
            return RiskCheckResult(
                approved=False,
                reason="Governance engine not initialized",
                risk_score=1.0
            )
        
        gov_approved, gov_reason = self.governance.check_trade_approval(
            layer=TradingLayer.INTRADAY,
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_exposure=current_exposure
        )
        
        if not gov_approved:
            return RiskCheckResult(
                approved=False,
                reason=f"[GOVERNANCE POLICY] {gov_reason}",
                risk_score=1.0
            )
        
        # ========================================================================
        # COST-AWARE FILTER (CRITICAL)
        # ========================================================================
        # This prevents trades that cannot statistically overcome transaction costs
        
        if expected_target is not None:
            # Calculate expected move
            expected_move_per_share = abs(expected_target - entry_price)
            
            # Validate trade profitability
            approved, reason, metrics = cost_calculator.validate_trade_profitability(
                quantity=quantity,
                entry_price=entry_price,
                expected_move_per_share=expected_move_per_share,
                max_cost_ratio=0.25  # Max 25% cost-to-profit ratio
            )
            
            if not approved:
                logger.warning(f"[COST FILTER] {symbol} REJECTED: {reason}")
                logger.warning(f"  Expected move: ₹{expected_move_per_share:.2f}, "
                             f"Breakeven: ₹{metrics.get('breakeven_move', 0):.2f}, "
                             f"Cost ratio: {metrics.get('cost_ratio', 0):.1f}%")
                return RiskCheckResult(
                    approved=False,
                    reason=f"[COST FILTER] {reason}",
                    risk_score=0.9
                )
            
            # Trade passes cost filter
            logger.info(f"[COST FILTER] {symbol} APPROVED: "
                       f"Expected net profit ₹{metrics.get('expected_net_profit', 0):.2f}, "
                       f"Cost ratio {metrics.get('cost_ratio', 0):.1f}%")
        else:
            # No target provided - use minimum cost check
            cost_per_share = cost_calculator.get_cost_per_share(quantity, entry_price)
            min_move = cost_per_share * 2  # Need 2x cost for buffer
            
            # Calculate stop distance to estimate expected move
            stop_distance = abs(entry_price - stop_price)
            
            # Assume target is at least 1.5x stop distance (R:R >= 1.5)
            estimated_move = stop_distance * 1.5
            
            if estimated_move < min_move:
                logger.warning(
                    f"[COST FILTER] {symbol} REJECTED: "
                    f"Estimated move ₹{estimated_move:.2f} < minimum required ₹{min_move:.2f}"
                )
                return RiskCheckResult(
                    approved=False,
                    reason=f"[COST FILTER] Estimated move insufficient to overcome costs (need ₹{min_move:.2f})",
                    risk_score=0.9
                )
        
        # Apply governance position size multiplier (drawdown/volatility adjustment)
        multiplier = self.governance.get_position_size_multiplier()
        if multiplier < 1.0:
            logger.warning(
                f"[GOVERNANCE] Position size multiplier: {multiplier:.0%} "
                f"(Drawdown: {self.governance.state.current_drawdown_percent:.1f}%)"
            )
        
        # 1. Check if trading is halted
        if await self._is_trading_halted():
            return RiskCheckResult(
                approved=False,
                reason="Trading is currently halted",
                risk_score=1.0
            )
        
        # 2. Check daily loss limit
        daily_loss = await self._get_daily_realized_loss()
        if daily_loss >= self.max_daily_loss:
            await self._halt_trading("Daily loss limit reached")
            return RiskCheckResult(
                approved=False,
                reason=f"Daily loss limit reached: Rs{daily_loss:.2f}",
                risk_score=1.0
            )
        
        # 3. Check consecutive losses with pause mechanism
        consecutive_losses = await self._get_consecutive_losses()
        if consecutive_losses >= self.consecutive_loss_limit:
            # Check if pause period has elapsed
            pause_remaining = await self._get_consecutive_loss_pause_remaining()
            if pause_remaining > 0:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Consecutive loss pause active: {pause_remaining} minutes remaining ({consecutive_losses} losses)",
                    risk_score=0.9
                )
            else:
                # Pause period over, reset counter
                await self._reset_consecutive_losses()
                logger.info(f"Consecutive loss pause completed, counter reset")
        
        # 4. Check open positions limit
        open_positions = await self._get_open_positions_count()
        if open_positions >= self.max_open_trades:
            return RiskCheckResult(
                approved=False,
                reason=f"Maximum open positions reached: {open_positions}/{self.max_open_trades}",
                risk_score=0.8
            )
        
        # 5. Calculate trade risk
        trade_risk = abs(entry_price - stop_price) * quantity
        if trade_risk > self.max_per_trade_risk:
            return RiskCheckResult(
                approved=False,
                reason=f"Trade risk Rs{trade_risk:.2f} exceeds limit Rs{self.max_per_trade_risk:.2f}",
                risk_score=0.85
            )
        
        # 6. Check capital per trade
        trade_capital = entry_price * quantity
        max_capital_per_trade = self.get_max_capital_per_trade()
        if trade_capital > max_capital_per_trade:
            return RiskCheckResult(
                approved=False,
                reason=f"Trade capital Rs{trade_capital:.2f} exceeds limit Rs{max_capital_per_trade:.2f} (25% of Rs{self.available_capital:,.2f})",
                risk_score=0.75
            )
        
        # 7. Check total exposure
        current_exposure = await self._get_current_exposure()
        new_exposure = current_exposure + trade_capital
        max_exposure = (self.max_exposure_percent / 100) * self.available_capital
        
        if new_exposure > max_exposure:
            return RiskCheckResult(
                approved=False,
                reason=f"Total exposure Rs{new_exposure:.2f} exceeds limit Rs{max_exposure:.2f}",
                risk_score=0.8
            )
        
        # 8. Additional risk score calculation
        risk_score = self._calculate_risk_score(
            trade_risk=trade_risk,
            trade_capital=trade_capital,
            daily_loss=daily_loss,
            consecutive_losses=consecutive_losses
        )
        
        logger.info(
            f"Trade approved for {symbol}: Risk Rs{trade_risk:.2f}, "
            f"Capital Rs{trade_capital:.2f}, Score {risk_score:.2f}"
        )
        
        return RiskCheckResult(
            approved=True,
            reason="All risk checks passed",
            risk_score=risk_score
        )
    
    async def record_trade_entry(
        self,
        trade_id: int,
        capital_deployed: float
    ) -> None:
        """Record a trade entry for tracking"""
        try:
            # Increment open positions
            redis_client.incr(self.OPEN_POSITIONS_KEY)
            
            # Store trade capital
            redis_client.hset(
                f"risk:trade:{trade_id}",
                mapping={
                    "capital": capital_deployed,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            logger.info(f"Recorded trade entry: ID={trade_id}, Capital=Rs{capital_deployed:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to record trade entry: {e}")
    
    async def record_trade_exit(
        self,
        trade_id: int,
        pnl: float,
        is_winner: bool
    ) -> None:
        """Record a trade exit and update risk metrics"""
        try:
            # Decrement open positions
            redis_client.decr(self.OPEN_POSITIONS_KEY)
            
            # Update daily loss
            current_loss = float(redis_client.get(self.DAILY_LOSS_KEY) or 0)
            if pnl < 0:
                new_loss = current_loss + abs(pnl)
                redis_client.set(self.DAILY_LOSS_KEY, new_loss)
                redis_client.expire(self.DAILY_LOSS_KEY, 86400)  # 24 hours
            
            # Update consecutive losses with pause mechanism
            if not is_winner:
                consecutive_count = redis_client.incr(self.CONSECUTIVE_LOSSES_KEY)
                redis_client.expire(self.CONSECUTIVE_LOSSES_KEY, 86400)
                
                # Trigger 60-minute pause after 3 consecutive losses
                pause_minutes = getattr(settings, 'consecutive_loss_pause_minutes', 60)
                if consecutive_count >= self.consecutive_loss_limit:
                    PAUSE_KEY = "risk:consecutive_loss_pause"
                    pause_until = datetime.now() + timedelta(minutes=pause_minutes)
                    redis_client.set(PAUSE_KEY, pause_until.isoformat())
                    redis_client.expire(PAUSE_KEY, pause_minutes * 60)
                    
                    logger.warning(
                        f"🛑 CONSECUTIVE LOSS LIMIT HIT: {consecutive_count} losses. "
                        f"Trading paused for {pause_minutes} minutes until {pause_until.strftime('%H:%M:%S')}. "
                        f"Prevents revenge trading."
                    )
            else:
                # Reset on win
                redis_client.delete(self.CONSECUTIVE_LOSSES_KEY)
                redis_client.delete("risk:consecutive_loss_pause")
            
            # Remove trade capital tracking
            redis_client.delete(f"risk:trade:{trade_id}")
            
            # Check if we hit daily loss limit after exit
            if pnl < 0:
                total_loss = await self._get_daily_realized_loss()
                if total_loss >= self.max_daily_loss:
                    await self._halt_trading("Daily loss limit reached after trade exit")
            
            logger.info(
                f"Recorded trade exit: ID={trade_id}, P&L=Rs{pnl:.2f}, "
                f"Winner={is_winner}"
            )
            
        except Exception as e:
            logger.error(f"Failed to record trade exit: {e}")
    
    async def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        try:
            daily_loss = await self._get_daily_realized_loss()
            open_positions = await self._get_open_positions_count()
            consecutive_losses = await self._get_consecutive_losses()
            current_exposure = await self._get_current_exposure()
            is_halted = await self._is_trading_halted()
            
            return {
                "daily_loss": daily_loss,
                "daily_loss_limit": self.max_daily_loss,
                "daily_loss_utilization": (daily_loss / self.max_daily_loss) * 100,
                "open_positions": open_positions,
                "max_open_positions": self.max_open_trades,
                "consecutive_losses": consecutive_losses,
                "consecutive_loss_limit": self.consecutive_loss_limit,
                "current_exposure": current_exposure,
                "max_exposure": (self.max_exposure_percent / 100) * self.initial_capital,
                "exposure_utilization": (current_exposure / self.initial_capital) * 100,
                "trading_halted": is_halted,
            }
        except Exception as e:
            logger.error(f"Failed to get risk metrics: {e}")
            return {}
    
    async def reset_daily_metrics(self) -> None:
        """Reset daily risk metrics (call at start of new trading day)"""
        try:
            redis_client.delete(self.DAILY_LOSS_KEY)
            redis_client.delete(self.CONSECUTIVE_LOSSES_KEY)
            redis_client.delete(self.TRADING_HALTED_KEY)
            logger.info("Daily risk metrics reset")
        except Exception as e:
            logger.error(f"Failed to reset daily metrics: {e}")
    
    async def halt_trading_manual(self, reason: str = "Manual halt") -> None:
        """Manually halt trading"""
        await self._halt_trading(reason)
    
    async def resume_trading(self) -> None:
        """Resume trading after halt"""
        try:
            redis_client.delete(self.TRADING_HALTED_KEY)
            logger.info("Trading resumed")
        except Exception as e:
            logger.error(f"Failed to resume trading: {e}")
    
    # Private helper methods
    
    async def _get_daily_realized_loss(self) -> float:
        """Get today's realized losses from database"""
        try:
            today = date.today()
            
            # Get closed trades for today with losses
            result = self.db.query(
                func.sum(Trade.net_pnl)
            ).filter(
                Trade.status == TradeStatus.CLOSED,
                func.date(Trade.exit_timestamp) == today,
                Trade.net_pnl < 0
            ).scalar()
            
            return abs(result) if result else 0.0
            
        except Exception as e:
            logger.error(f"Failed to get daily realized loss: {e}")
            return 0.0
    
    async def _get_open_positions_count(self) -> int:
        """Get count of open positions"""
        try:
            # Check Redis first
            count = redis_client.get(self.OPEN_POSITIONS_KEY)
            if count is not None:
                return int(count)
            
            # Fallback to database
            count = self.db.query(Trade).filter(
                Trade.status == TradeStatus.OPEN
            ).count()
            
            redis_client.set(self.OPEN_POSITIONS_KEY, count)
            return count
            
        except Exception as e:
            logger.error(f"Failed to get open positions count: {e}")
            return 0
    
    async def _get_consecutive_losses(self) -> int:
        """Get current consecutive loss count"""
        try:
            count = redis_client.get(self.CONSECUTIVE_LOSSES_KEY)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Failed to get consecutive losses: {e}")
            return 0
    
    async def _get_consecutive_loss_pause_remaining(self) -> int:
        """Get remaining pause time in minutes after consecutive losses
        
        Returns:
            Minutes remaining in pause, or 0 if no pause active
        """
        try:
            PAUSE_KEY = "risk:consecutive_loss_pause"
            pause_until = redis_client.get(PAUSE_KEY)
            
            if not pause_until:
                return 0
            
            pause_until_dt = datetime.fromisoformat(pause_until)
            now = datetime.now()
            
            if now >= pause_until_dt:
                # Pause expired
                redis_client.delete(PAUSE_KEY)
                return 0
            
            remaining_seconds = (pause_until_dt - now).total_seconds()
            return int(remaining_seconds / 60) + 1  # Round up
            
        except Exception as e:
            logger.error(f"Failed to check consecutive loss pause: {e}")
            return 0
    
    async def _reset_consecutive_losses(self) -> None:
        """Reset consecutive loss counter"""
        try:
            redis_client.delete(self.CONSECUTIVE_LOSSES_KEY)
            redis_client.delete("risk:consecutive_loss_pause")
            logger.info("Consecutive loss counter reset")
        except Exception as e:
            logger.error(f"Failed to reset consecutive losses: {e}")
    
    async def _get_current_exposure(self) -> float:
        """Get total capital currently deployed"""
        try:
            # Sum up all open trade capitals from Redis
            trade_keys = redis_client.keys("risk:trade:*")
            total_exposure = 0.0
            
            for key in trade_keys:
                capital = redis_client.hget(key, "capital")
                if capital:
                    total_exposure += float(capital)
            
            return total_exposure
            
        except Exception as e:
            logger.error(f"Failed to get current exposure: {e}")
            return 0.0
    
    async def _is_trading_halted(self) -> bool:
        """Check if trading is currently halted"""
        try:
            return redis_client.exists(self.TRADING_HALTED_KEY) > 0
        except Exception as e:
            logger.error(f"Failed to check trading halt status: {e}")
            return False
    
    async def _halt_trading(self, reason: str) -> None:
        """Halt all trading"""
        try:
            redis_client.set(
                self.TRADING_HALTED_KEY,
                reason,
                ex=86400  # Expire after 24 hours
            )
            logger.critical(f"TRADING HALTED: {reason}")
            
            # Update daily metrics
            today = date.today()
            metrics = self.db.query(DailyMetrics).filter(
                func.date(DailyMetrics.date) == today
            ).first()
            
            if metrics:
                metrics.trading_halted = True
                metrics.halt_reason = reason
                self.db.commit()
                
        except Exception as e:
            logger.error(f"Failed to halt trading: {e}")
    
    def _calculate_risk_score(
        self,
        trade_risk: float,
        trade_capital: float,
        daily_loss: float,
        consecutive_losses: int
    ) -> float:
        """Calculate overall risk score (0-1, lower is better)"""
        
        # Component scores
        risk_utilization = trade_risk / self.max_per_trade_risk
        capital_utilization = trade_capital / self.get_max_capital_per_trade()
        loss_utilization = daily_loss / self.max_daily_loss
        streak_score = consecutive_losses / self.consecutive_loss_limit
        
        # Weighted average
        risk_score = (
            risk_utilization * 0.3 +
            capital_utilization * 0.2 +
            loss_utilization * 0.3 +
            streak_score * 0.2
        )
        
        return min(risk_score, 1.0)
