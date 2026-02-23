"""Capital Allocation Engine (CAE)
===================================

Professional capital allocation system with:
- Performance-based dynamic allocation
- Multi-layer drawdown protection
- Cost efficiency monitoring
- Strategy kill switches
- Monthly rebalancing with scoring

Base Allocation:
- Intraday: 15%
- Swing: 35%
- Mid-term: 35%
- Long-term: 15%

Dynamic adjustments based on 0-100 performance score.
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy.orm import Session

from performance_tracker import PerformanceTracker, TradingLayer, PerformanceScore
from models import Trade, TradeStatus

logger = logging.getLogger(__name__)


@dataclass
class LayerAllocation:
    """Capital allocation for a trading layer"""
    layer: TradingLayer
    base_percent: float  # Base allocation percentage
    current_percent: float  # After adjustments
    allocated_capital: float
    available_capital: float
    used_capital: float
    performance_score: float  # 0-100
    performance_multiplier: float  # 0.5-1.5
    is_blocked: bool
    block_reason: str
    
    def get_effective_capital(self) -> float:
        """Get effective capital after performance adjustment"""
        return self.allocated_capital * self.performance_multiplier


class CapitalAllocator:
    """Professional Capital Allocation Engine
    
    Features:
    - Dynamic allocation based on performance scoring (0-100)
    - Portfolio-wide drawdown protection
    - Cost efficiency monitoring
    - Strategy kill switches
    - Monthly rebalancing
    - Correlation control
    """
    
    # Base allocation percentages
    BASE_ALLOCATIONS = {
        TradingLayer.INTRADAY: 15.0,
        TradingLayer.SWING: 35.0,
        TradingLayer.MID_TERM: 35.0,
        TradingLayer.LONG_TERM: 15.0
    }
    
    # Allocation constraints
    MIN_ALLOCATION = 10.0  # Minimum 10% per layer
    MAX_ALLOCATION = 50.0  # Maximum 50% per layer
    MAX_ADJUSTMENT_PER_MONTH = 10.0  # Max 10% change per month
    
    # Performance thresholds for adjustment
    HIGH_PERFORMANCE_THRESHOLD = 70.0  # Score >= 70: increase allocation
    LOW_PERFORMANCE_THRESHOLD = 40.0  # Score < 40: decrease allocation
    
    # Drawdown protection triggers
    PORTFOLIO_DRAWDOWN_WARNING = 0.10  # 10%
    PORTFOLIO_DRAWDOWN_CRITICAL = 0.15  # 15%
    
    def __init__(self, db_session: Session, total_capital: float):
        self.db = db_session
        self.total_capital = total_capital
        self.starting_capital = total_capital
        self.current_equity = total_capital
        self.peak_equity = total_capital
        
        # Initialize performance tracker
        self.performance_tracker = PerformanceTracker()
        
        # Layer allocations
        self.layer_allocations: Dict[TradingLayer, LayerAllocation] = {}
        self._initialize_allocations()
        
        # Rebalancing
        self.last_rebalance = datetime.now()
        self.rebalance_interval_days = 30
        
        # Risk budget (2% of capital per day)
        self.daily_risk_budget = total_capital * 0.02
        
        logger.info(f"✅ Capital Allocation Engine initialized: Rs{total_capital:,.2f}")
        logger.info(f"   Daily risk budget: Rs{self.daily_risk_budget:,.2f}")
        self._log_allocations()
    
    def _initialize_allocations(self):
        """Initialize capital allocations for each layer"""
        for layer, base_percent in self.BASE_ALLOCATIONS.items():
            allocated = self.total_capital * (base_percent / 100.0)
            
            self.layer_allocations[layer] = LayerAllocation(
                layer=layer,
                base_percent=base_percent,
                current_percent=base_percent,
                allocated_capital=allocated,
                available_capital=allocated,
                used_capital=0.0,
                performance_score=50.0,  # Neutral start
                performance_multiplier=1.0,
                is_blocked=False,
                block_reason=""
            )
    
    def get_layer_allocation(self, layer: TradingLayer) -> LayerAllocation:
        """Get allocation info for a layer"""
        return self.layer_allocations[layer]
    
    def get_available_capital(self, layer: TradingLayer) -> float:
        """Get available capital for new trades in a layer"""
        allocation = self.layer_allocations[layer]
        
        # Check if layer is blocked
        if allocation.is_blocked:
            return 0.0
        
        return allocation.available_capital * allocation.performance_multiplier
    
    def get_layer_risk_budget(self, layer: TradingLayer) -> float:
        """Get risk budget for a layer based on allocation
        
        Args:
            layer: Trading layer
            
        Returns:
            Risk budget in rupees for this layer
        """
        allocation = self.layer_allocations[layer]
        layer_budget = self.daily_risk_budget * (allocation.current_percent / 100.0)
        return layer_budget
    
    def reserve_capital(self, layer: TradingLayer, amount: float) -> bool:
        """Reserve capital for a new trade
        
        Args:
            layer: Trading layer
            amount: Capital to reserve
            
        Returns:
            True if reservation successful
        """
        allocation = self.layer_allocations[layer]
        
        # Check if blocked
        if allocation.is_blocked:
            logger.warning(f"[{layer.value.upper()}] Layer blocked: {allocation.block_reason}")
            return False
        
        effective_available = allocation.available_capital * allocation.performance_multiplier
        
        if amount > effective_available:
            logger.warning(f"[{layer.value.upper()}] Insufficient capital: "
                          f"requested Rs{amount:.2f}, available Rs{effective_available:.2f}")
            return False
        
        allocation.used_capital += amount
        allocation.available_capital -= amount
        
        logger.info(f"[{layer.value.upper()}] Reserved Rs{amount:.2f}, "
                   f"remaining Rs{allocation.available_capital:.2f}")
        return True
    
    def release_capital(self, layer: TradingLayer, amount: float):
        """Release capital when a trade closes
        
        Args:
            layer: Trading layer
            amount: Capital to release
        """
        allocation = self.layer_allocations[layer]
        allocation.used_capital = max(0, allocation.used_capital - amount)
        allocation.available_capital += amount
        
        logger.info(f"[{layer.value.upper()}] Released Rs{amount:.2f}, "
                   f"available Rs{allocation.available_capital:.2f}")
    
    def update_after_trade(self, layer: TradingLayer, trade: Trade):
        """Update allocator after a trade closes
        
        Args:
            layer: Trading layer
            trade: Closed trade record
        """
        # Update performance tracker
        self.performance_tracker.update_metrics(
            layer=layer,
            trade_pnl=trade.net_pnl or 0.0,
            trade_costs=trade.charges or 0.0,
            current_equity=self.current_equity
        )
        
        # Release capital
        capital_used = trade.entry_price * trade.quantity
        self.release_capital(layer, capital_used)
        
        # Update equity
        self.current_equity += (trade.net_pnl or 0.0)
        self.peak_equity = max(self.peak_equity, self.current_equity)
        
        # Check portfolio drawdown protection
        self._check_portfolio_drawdown()
        
        # Update performance scores
        self._update_performance_scores()
    
    def _update_performance_scores(self):
        """Update performance scores for all layers"""
        for layer, allocation in self.layer_allocations.items():
            score: PerformanceScore = self.performance_tracker.calculate_score(
                layer=layer,
                allocated_capital=allocation.allocated_capital
            )
            allocation.performance_score = score.total_score
            
            logger.debug(f"[{layer.value.upper()}] Performance score: {score.total_score:.1f}/100")
    
    def _check_portfolio_drawdown(self):
        """Check portfolio-level drawdown and apply protection"""
        current_dd = (self.peak_equity - self.current_equity) / self.peak_equity
        
        if current_dd >= self.PORTFOLIO_DRAWDOWN_CRITICAL:
            # CRITICAL: Reduce all risk by 50%, halt intraday
            logger.critical(f"⛔ PORTFOLIO DRAWDOWN CRITICAL: {current_dd*100:.1f}%")
            logger.critical("   Action: Halting intraday, reducing all risk 50%")
            
            for layer, allocation in self.layer_allocations.items():
                if layer == TradingLayer.INTRADAY:
                    allocation.is_blocked = True
                    allocation.block_reason = f"Critical drawdown:{current_dd*100:.1f}%"
                else:
                    allocation.performance_multiplier = min(
                        allocation.performance_multiplier,
                        0.5
                    )
        
        elif current_dd >= self.PORTFOLIO_DRAWDOWN_WARNING:
            # WARNING: Reduce all risk by 50%
            logger.warning(f"⚠️ PORTFOLIO DRAWDOWN WARNING: {current_dd*100:.1f}%")
            logger.warning("   Action: Reducing all layer risk by 50%")
            
            for allocation in self.layer_allocations.values():
                allocation.performance_multiplier = min(
                    allocation.performance_multiplier,
                    0.5
                )
    
    def monthly_rebalance(self):
        """Perform monthly rebalancing based on performance scores
        
        Logic:
        - Score >= 70: Increase allocation by +5%
        - Score < 40: Decrease allocation by -5%
        - Constrained by MIN/MAX allocation limits
        - Max change per month: 10%
        """
        logger.info("\n" + "="*80)
        logger.info("MONTHLY REBALANCING")
        logger.info("="*80)
        
        total_adjustment = 0.0
        adjustments = {}
        
        # Calculate adjustments
        for layer, allocation in self.layer_allocations.items():
            old_percent = allocation.current_percent
            score = allocation.performance_score
            
            if score >= self.HIGH_PERFORMANCE_THRESHOLD:
                # High performance: increase allocation
                adjustment = 5.0
                new_percent = min(
                    self.MAX_ALLOCATION,
                    old_percent + adjustment
                )
            elif score < self.LOW_PERFORMANCE_THRESHOLD:
                # Low performance: decrease allocation
                adjustment = -5.0
                new_percent = max(
                    self.MIN_ALLOCATION,
                    old_percent + adjustment
                )
            else:
                # Neutral: no change
                new_percent = old_percent
            
            # Apply max adjustment limit
            actual_change = new_percent - old_percent
            if abs(actual_change) > self.MAX_ADJUSTMENT_PER_MONTH:
                actual_change = (
                    self.MAX_ADJUSTMENT_PER_MONTH if actual_change > 0 
                    else -self.MAX_ADJUSTMENT_PER_MONTH
                )
                new_percent = old_percent + actual_change
            
            adjustments[layer] = (old_percent, new_percent, score)
            total_adjustment += (new_percent - old_percent)
        
        # Normalize to 100%
        total_new = sum(new for _, new, _ in adjustments.values())
        normalization_factor = 100.0 / total_new if total_new > 0 else 1.0
        
        # Apply adjustments
        for layer, (old_percent, new_percent, score) in adjustments.items():
            normalized_percent = new_percent * normalization_factor
            allocation = self.layer_allocations[layer]
            
            # Update allocation
            allocation.current_percent = normalized_percent
            old_capital = allocation.allocated_capital
            allocation.allocated_capital = self.total_capital * (normalized_percent / 100.0)
            
            # Adjust available capital proportionally
            if old_capital > 0:
                capital_ratio = allocation.allocated_capital / old_capital
                allocation.available_capital = max(0, allocation.available_capital * capital_ratio)
            
            logger.info(f"[{layer.value.upper()}] Score: {score:.1f}/100")
            logger.info(f"   Allocation: {old_percent:.1f}% -> {normalized_percent:.1f}%")
            logger.info(f"   Capital: Rs{old_capital:,.2f} -> Rs{allocation.allocated_capital:,.2f}")
        
        self.last_rebalance = datetime.now()
        logger.info("="*80 + "\n")
    
    def check_and_rebalance(self):
        """Check if rebalancing is needed and execute"""
        days_since_rebalance = (datetime.now() - self.last_rebalance).days
        
        if days_since_rebalance >= self.rebalance_interval_days:
            logger.info(f"📅 Monthly rebalancing triggered ({days_since_rebalance} days)")
            
            # Update scores first
            self._update_performance_scores()
            
            # Check for strategy kill switches
            self._check_kill_switches()
            
            # Rebalance
            self.monthly_rebalance()
    
    def _check_kill_switches(self):
        """Check if any strategy should be killed"""
        for layer in TradingLayer:
            should_kill = self.performance_tracker.should_kill_strategy(layer)
            
            if should_kill:
                allocation = self.layer_allocations[layer]
                allocation.is_blocked = True
                allocation.block_reason = "Poor performance - strategy killed"
                logger.critical(f"🔴 [{layer.value.upper()}] STRATEGY KILLED due to poor performance")
    
    def update_capital(self, new_total_capital: float):
        """Update total capital after deposits/withdrawals or P&L changes
        
        Args:
            new_total_capital: New total capital value
        """
        old_capital = self.total_capital
        self.total_capital = new_total_capital
        
        # Proportionally adjust each layer's allocation
        multiplier = new_total_capital / old_capital if old_capital > 0 else 1.0
        
        for layer, allocation in self.layer_allocations.items():
            allocation.allocated_capital *= multiplier
            allocation.available_capital *= multiplier
            allocation.used_capital *= multiplier
        
        # Update risk budget
        self.daily_risk_budget = new_total_capital * 0.02
        
        logger.info(f"💰 Capital updated: Rs{old_capital:,.2f} -> Rs{new_total_capital:,.2f}")
        self._log_allocations()
    
    def is_layer_blocked(self, layer: TradingLayer) -> Tuple[bool, str]:
        """Check if a layer should be blocked from new trades
        
        Args:
            layer: Trading layer to check
            
        Returns:
            Tuple of (is_blocked, reason)
        """
        allocation = self.layer_allocations[layer]
        
        if allocation.is_blocked:
            return True, allocation.block_reason
        
        # Check if capital is depleted
        if allocation.available_capital < 1000:  # Minimum Rs1000
            return True, "Insufficient capital available"
        
        return False, ""
    
    def get_allocation_summary(self) -> str:
        """Get comprehensive allocation summary report"""
        lines = ["\n" + "="*90]
        lines.append("CAPITAL ALLOCATION ENGINE - STATUS")
        lines.append("="*90)
        
        # Portfolio overview
        portfolio_dd = (self.peak_equity - self.current_equity) / self.peak_equity * 100
        lines.append(f"💰 Total Capital: Rs{self.total_capital:,.2f}")
        lines.append(f"💹 Current Equity: Rs{self.current_equity:,.2f}")
        lines.append(f"📈 Peak Equity: Rs{self.peak_equity:,.2f}")
        lines.append(f"📉 Portfolio Drawdown: {portfolio_dd:.2f}%")
        lines.append(f"🎯 Daily Risk Budget: Rs{self.daily_risk_budget:,.2f}")
        lines.append(f"📅 Last Rebalance: {self.last_rebalance.strftime('%Y-%m-%d')}")
        lines.append("")
        
        # Layer details
        for layer in TradingLayer:
            allocation = self.layer_allocations[layer]
            metrics = self.performance_tracker.get_metrics(layer)
            
            lines.append(f"[{layer.value.upper()}]")
            lines.append(f"  📊 Allocation: {allocation.base_percent:.1f}% -> "
                        f"{allocation.current_percent:.1f}% (Rs{allocation.allocated_capital:,.2f})")
            lines.append(f"  ⚖️ Performance: {allocation.performance_score:.1f}/100 "
                        f"(Multiplier: {allocation.performance_multiplier:.2f}x)")
            lines.append(f"  💵 Available: Rs{allocation.available_capital:,.2f} | "
                        f"In Use: Rs{allocation.used_capital:,.2f}")
            lines.append(f"  📈 Trades: {metrics.total_trades} | "
                        f"Win Rate: {metrics.win_rate:.1f}% | "
                        f"PF: {metrics.profit_factor:.2f}")
            lines.append(f"  💰 P&L: Rs{metrics.net_pnl:,.2f} | "
                        f"Cost Ratio: {metrics.cost_to_profit_ratio*100:.1f}%")
            
            if allocation.is_blocked:
                lines.append(f"  ❌ BLOCKED: {allocation.block_reason}")
            else:
                lines.append(f"  ✅ Active")
            
            lines.append("")
        
        lines.append("="*90)
        return "\n".join(lines)
    
    def _log_allocations(self):
        """Log current allocations"""
        summary = self.get_allocation_summary()
        logger.info(summary)
    
    def get_portfolio_stats(self) -> Dict:
        """Get comprehensive portfolio statistics"""
        total_pnl = sum(
            self.performance_tracker.get_metrics(layer).net_pnl
            for layer in TradingLayer
        )
        
        total_trades = sum(
            self.performance_tracker.get_metrics(layer).total_trades
            for layer in TradingLayer
        )
        
        portfolio_return = (self.current_equity - self.starting_capital) / self.starting_capital * 100
        portfolio_dd = (self.peak_equity - self.current_equity) / self.peak_equity * 100
        
        return {
            "total_capital": self.total_capital,
            "current_equity": self.current_equity,
            "starting_capital": self.starting_capital,
            "peak_equity": self.peak_equity,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "portfolio_return_pct": portfolio_return,
            "portfolio_drawdown_pct": portfolio_dd,
            "last_rebalance": self.last_rebalance.isoformat(),
            "layer_allocations": {
                layer.value: {
                    "base_percent": alloc.base_percent,
                    "current_percent": alloc.current_percent,
                    "allocated": alloc.allocated_capital,
                    "available": alloc.available_capital,
                    "score": alloc.performance_score,
                    "multiplier": alloc.performance_multiplier,
                    "is_blocked": alloc.is_blocked
                }
                for layer, alloc in self.layer_allocations.items()
            }
        }


logger.info("✅ Capital Allocation Engine module loaded")
