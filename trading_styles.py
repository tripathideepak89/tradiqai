"""Multi-Timeframe Trading Styles Framework
===========================================

Implements 4 distinct trading styles with proper capital allocation:
1. Intraday (20% allocation)
2. Short-Term Swing (30% allocation)
3. Mid-Term Trend (30% allocation)
4. Long-Term Position (20% allocation)

Expected realistic returns:
- Intraday: 15% annually
- Swing: 25% annually
- Mid-Term: 30% annually
- Long-Term: 18% annually
- Combined: ~23% annually

CRITICAL: Each style is independent with its own rules, risk, and capital
"""
import logging
from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TradingStyle(Enum):
    """Trading style types"""
    INTRADAY = "intraday"
    SWING = "swing"
    MIDTERM = "midterm"
    LONGTERM = "longterm"


class MarketRegime(Enum):
    """Market regime states"""
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    HIGH_VOLATILITY = "high_volatility"


@dataclass
class StyleAllocation:
    """Capital allocation for each trading style"""
    style: TradingStyle
    allocation_percent: float
    expected_annual_return: float
    max_drawdown_percent: float
    volatility: str  # "Low", "Medium", "High"
    holding_period: str  # e.g., "Minutes-Hours", "3-10 Days", etc.
    
    def get_allocated_capital(self, total_capital: float) -> float:
        """Calculate allocated capital"""
        return total_capital * (self.allocation_percent / 100.0)


@dataclass
class TradingRules:
    """Trading rules for a style"""
    style: TradingStyle
    timeframe: str
    max_trades_per_day: Optional[int]
    max_open_positions: int
    risk_per_trade_percent: float
    stop_loss_method: str
    profit_target_r_multiple: float
    holding_period_days: Optional[int]
    
    # Entry filters
    requires_trend: bool
    requires_volume_confirmation: bool
    requires_breakout: bool
    
    # Exit rules
    time_based_exit: bool
    trailing_stop: bool
    target_based_exit: bool


class TradingStylesConfig:
    """Configuration for all trading styles"""
    
    # Capital allocation (must sum to 100%)
    ALLOCATIONS = {
        TradingStyle.INTRADAY: StyleAllocation(
            style=TradingStyle.INTRADAY,
            allocation_percent=20.0,
            expected_annual_return=15.0,
            max_drawdown_percent=12.0,
            volatility="High",
            holding_period="Minutes to Hours"
        ),
        TradingStyle.SWING: StyleAllocation(
            style=TradingStyle.SWING,
            allocation_percent=30.0,
            expected_annual_return=25.0,
            max_drawdown_percent=10.0,
            volatility="Medium",
            holding_period="3-10 Days"
        ),
        TradingStyle.MIDTERM: StyleAllocation(
            style=TradingStyle.MIDTERM,
            allocation_percent=30.0,
            expected_annual_return=30.0,
            max_drawdown_percent=12.0,
            volatility="Medium",
            holding_period="1-6 Months"
        ),
        TradingStyle.LONGTERM: StyleAllocation(
            style=TradingStyle.LONGTERM,
            allocation_percent=20.0,
            expected_annual_return=18.0,
            max_drawdown_percent=15.0,
            volatility="Low",
            holding_period="1+ Years"
        )
    }
    
    # Trading rules for each style
    RULES = {
        TradingStyle.INTRADAY: TradingRules(
            style=TradingStyle.INTRADAY,
            timeframe="5min/15min",
            max_trades_per_day=2,
            max_open_positions=1,
            risk_per_trade_percent=0.7,
            stop_loss_method="swing_low_or_atr",
            profit_target_r_multiple=1.5,
            holding_period_days=None,  # Intraday only
            requires_trend=True,
            requires_volume_confirmation=True,
            requires_breakout=True,
            time_based_exit=True,
            trailing_stop=True,
            target_based_exit=True
        ),
        TradingStyle.SWING: TradingRules(
            style=TradingStyle.SWING,
            timeframe="daily",
            max_trades_per_day=None,  # No daily limit
            max_open_positions=3,
            risk_per_trade_percent=1.5,
            stop_loss_method="5day_low_or_atr",
            profit_target_r_multiple=2.0,
            holding_period_days=10,
            requires_trend=True,
            requires_volume_confirmation=True,
            requires_breakout=True,
            time_based_exit=True,
            trailing_stop=True,
            target_based_exit=True
        ),
        TradingStyle.MIDTERM: TradingRules(
            style=TradingStyle.MIDTERM,
            timeframe="daily/weekly",
            max_trades_per_day=None,
            max_open_positions=3,
            risk_per_trade_percent=2.0,
            stop_loss_method="20dma_or_weekly_low",
            profit_target_r_multiple=2.5,
            holding_period_days=180,  # 6 months
            requires_trend=True,
            requires_volume_confirmation=False,
            requires_breakout=True,
            time_based_exit=True,
            trailing_stop=True,
            target_based_exit=False  # Let winners run
        ),
        TradingStyle.LONGTERM: TradingRules(
            style=TradingStyle.LONGTERM,
            timeframe="weekly/monthly",
            max_trades_per_day=None,
            max_open_positions=3,
            risk_per_trade_percent=3.0,
            stop_loss_method="200dma",
            profit_target_r_multiple=3.0,
            holding_period_days=365,  # 1+ year
            requires_trend=False,  # Fundamental-based
            requires_volume_confirmation=False,
            requires_breakout=False,
            time_based_exit=False,
            trailing_stop=False,
            target_based_exit=False  # Long-term hold
        )
    }
    
    @classmethod
    def validate_allocations(cls) -> bool:
        """Ensure allocations sum to 100%"""
        total = sum(alloc.allocation_percent for alloc in cls.ALLOCATIONS.values())
        if abs(total - 100.0) > 0.01:
            logger.error(f"Allocations must sum to 100%, got {total}%")
            return False
        return True
    
    @classmethod
    def get_style_capital(cls, style: TradingStyle, total_capital: float) -> float:
        """Get allocated capital for a style"""
        allocation = cls.ALLOCATIONS[style]
        return allocation.get_allocated_capital(total_capital)
    
    @classmethod
    def get_style_rules(cls, style: TradingStyle) -> TradingRules:
        """Get trading rules for a style"""
        return cls.RULES[style]
    
    @classmethod
    def calculate_position_size(
        cls, 
        style: TradingStyle, 
        allocated_capital: float, 
        entry_price: float, 
        stop_loss_price: float
    ) -> int:
        """Calculate position size based on risk rules
        
        Args:
            style: Trading style
            allocated_capital: Capital allocated to this style
            entry_price: Entry price per share
            stop_loss_price: Stop loss price per share
            
        Returns:
            Number of shares to buy
        """
        rules = cls.get_style_rules(style)
        
        # Risk amount = allocated capital * risk %
        risk_amount = allocated_capital * (rules.risk_per_trade_percent / 100.0)
        
        # Risk per share = entry - stop loss
        risk_per_share = abs(entry_price - stop_loss_price)
        
        if risk_per_share == 0:
            logger.error("Stop loss equals entry price")
            return 0
        
        # Position size = risk amount / risk per share
        shares = int(risk_amount / risk_per_share)
        
        # Validate capital requirement
        required_capital = shares * entry_price
        if required_capital > allocated_capital:
            # Reduce to fit capital
            shares = int(allocated_capital / entry_price)
        
        return shares
    
    @classmethod
    def is_style_allowed_in_regime(
        cls, 
        style: TradingStyle, 
        regime: MarketRegime,
        position_direction: str  # "long" or "short"
    ) -> bool:
        """Check if trading style is allowed in current market regime
        
        Different styles behave differently in different regimes:
        - Intraday: Can trade in any regime (momentum-based)
        - Swing: Requires trend
        - Mid-term: Requires strong trend
        - Long-term: Less affected by short-term regime
        """
        if style == TradingStyle.INTRADAY:
            # Intraday can trade in any regime
            # But reduce size in RANGE
            return True
        
        elif style == TradingStyle.SWING:
            # Swing requires trend
            if regime == MarketRegime.RANGE:
                return False
            if regime == MarketRegime.TREND_UP and position_direction == "short":
                return False
            if regime == MarketRegime.TREND_DOWN and position_direction == "long":
                return False
            return True
        
        elif style == TradingStyle.MIDTERM:
            # Mid-term requires strong trend
            if regime in [MarketRegime.RANGE, MarketRegime.HIGH_VOLATILITY]:
                return False
            if regime == MarketRegime.TREND_UP and position_direction == "short":
                return False
            if regime == MarketRegime.TREND_DOWN and position_direction == "long":
                return False
            return True
        
        elif style == TradingStyle.LONGTERM:
            # Long-term less affected by regime
            # But avoid entries during high volatility
            if regime == MarketRegime.HIGH_VOLATILITY:
                return False
            return True
        
        return False
    
    @classmethod
    def get_regime_position_scaling(cls, style: TradingStyle, regime: MarketRegime) -> float:
        """Get position size scaling factor based on regime
        
        Returns:
            Multiplier for position size (0.0 to 1.0)
        """
        if regime == MarketRegime.HIGH_VOLATILITY:
            # Reduce all positions in high volatility
            return 0.5
        
        if style == TradingStyle.INTRADAY:
            if regime == MarketRegime.RANGE:
                return 0.5  # Half size in range
            return 1.0
        
        elif style == TradingStyle.SWING:
            if regime == MarketRegime.RANGE:
                return 0.0  # No swing trades in range
            return 1.0
        
        elif style == TradingStyle.MIDTERM:
            if regime == MarketRegime.RANGE:
                return 0.0  # No mid-term in range
            return 1.0
        
        elif style == TradingStyle.LONGTERM:
            return 1.0  # Long-term unaffected
        
        return 1.0


class StylePerformanceTracker:
    """Track performance metrics for each trading style"""
    
    def __init__(self):
        self.metrics: Dict[TradingStyle, Dict] = {
            style: {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "current_drawdown": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "average_r": 0.0,
                "last_updated": datetime.now()
            }
            for style in TradingStyle
        }
    
    def update_trade_result(
        self, 
        style: TradingStyle, 
        pnl: float, 
        r_multiple: float
    ):
        """Update metrics after a trade closes"""
        metrics = self.metrics[style]
        
        metrics["total_trades"] += 1
        metrics["total_pnl"] += pnl
        
        if pnl > 0:
            metrics["winning_trades"] += 1
        elif pnl < 0:
            metrics["losing_trades"] += 1
        
        # Update win rate
        if metrics["total_trades"] > 0:
            metrics["win_rate"] = metrics["winning_trades"] / metrics["total_trades"]
        
        # Update average R
        total_r = metrics.get("total_r", 0.0) + r_multiple
        metrics["total_r"] = total_r
        metrics["average_r"] = total_r / metrics["total_trades"]
        
        # Update drawdown
        if pnl < 0:
            metrics["current_drawdown"] += abs(pnl)
            if metrics["current_drawdown"] > metrics["max_drawdown"]:
                metrics["max_drawdown"] = metrics["current_drawdown"]
        else:
            metrics["current_drawdown"] = max(0, metrics["current_drawdown"] - pnl)
        
        metrics["last_updated"] = datetime.now()
        
        logger.info(f"[{style.value.upper()}] Updated: {metrics['total_trades']} trades, "
                   f"Win rate: {metrics['win_rate']*100:.1f}%, PnL: Rs{metrics['total_pnl']:.2f}")
    
    def should_disable_style(self, style: TradingStyle) -> tuple[bool, str]:
        """Check if style should be disabled based on performance
        
        Returns:
            (should_disable, reason)
        """
        metrics = self.metrics[style]
        
        # Need minimum trades before disabling
        if metrics["total_trades"] < 50:
            return False, ""
        
        # Disable if profit factor < 1.2
        if metrics["profit_factor"] < 1.2:
            return True, f"Profit factor {metrics['profit_factor']:.2f} < 1.2 minimum"
        
        # Disable if win rate < 30%
        if metrics["win_rate"] < 0.30:
            return True, f"Win rate {metrics['win_rate']*100:.1f}% < 30% minimum"
        
        # Disable if average R < 0.5
        if metrics["average_r"] < 0.5:
            return True, f"Average R {metrics['average_r']:.2f} < 0.5 minimum"
        
        return False, ""
    
    def get_style_metrics(self, style: TradingStyle) -> Dict:
        """Get current metrics for a style"""
        return self.metrics[style].copy()
    
    def _get_style_summary(self) -> str:
        """Get summary of all styles"""
        lines = ["\n" + "="*80]
        lines.append("MULTI-TIMEFRAME PERFORMANCE SUMMARY")
        lines.append("="*80)
        
        total_pnl = 0.0
        for style in TradingStyle:
            metrics = self.metrics[style]
            total_pnl += metrics["total_pnl"]
            
            lines.append(f"\n[{style.value.upper()}]")
            lines.append(f"  Trades: {metrics['total_trades']} | Win Rate: {metrics['win_rate']*100:.1f}%")
            lines.append(f"  P&L: Rs{metrics['total_pnl']:.2f} | Avg R: {metrics['average_r']:.2f}")
            lines.append(f"  Max DD: Rs{metrics['max_drawdown']:.2f}")
        
        lines.append(f"\n{'='*80}")
        lines.append(f"TOTAL P&L: Rs{total_pnl:.2f}")
        lines.append("="*80)
        
        return "\n".join(lines)


# Initialize and validate
if not TradingStylesConfig.validate_allocations():
    raise ValueError("Trading style allocations are invalid")

logger.info("Trading styles framework initialized")
logger.info(f"Total allocation: {sum(a.allocation_percent for a in TradingStylesConfig.ALLOCATIONS.values())}%")
