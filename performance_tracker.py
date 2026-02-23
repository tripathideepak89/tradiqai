"""Performance Tracker for Trading Strategies
============================================

Tracks and scores performance across multiple dimensions:
- Returns (30-day)
- Profit factor
- Max drawdown
- Win rate
- Equity curve trend

Provides 0-100 performance score for capital allocation decisions.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class TradingLayer(str, Enum):
    """Trading timeframe layers"""
    INTRADAY = "intraday"
    SWING = "swing"
    MID_TERM = "mid_term"
    LONG_TERM = "long_term"


@dataclass
class StrategyMetrics:
    """Comprehensive strategy performance metrics"""
    layer: TradingLayer
    lookback_days: int = 30
    
    # Core metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # P&L metrics
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    
    # Cost efficiency
    total_costs: float = 0.0
    cost_to_profit_ratio: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    max_consecutive_losses: int = 0
    
    # Equity curve
    equity_curve: List[float] = field(default_factory=list)
    equity_curve_slope: float = 0.0
    
    # Timestamps
    last_trade_time: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def profit_factor(self) -> float:
        """Calculate profit factor (gross_profit / gross_loss)"""
        if self.gross_loss == 0:
            return float('inf') if self.gross_profit > 0 else 0.0
        return self.gross_profit / abs(self.gross_loss)
    
    @property
    def average_win(self) -> float:
        """Average winning trade size"""
        if self.winning_trades == 0:
            return 0.0
        return self.gross_profit / self.winning_trades
    
    @property
    def average_loss(self) -> float:
        """Average losing trade size"""
        if self.losing_trades == 0:
            return 0.0
        return abs(self.gross_loss) / self.losing_trades
    
    @property
    def return_percentage(self) -> float:
        """Return as percentage of starting capital"""
        # This will be calculated relative to allocated capital
        return 0.0  # Placeholder, calculated externally


@dataclass
class PerformanceScore:
    """Performance score breakdown (0-100)"""
    total_score: float
    
    # Component scores
    return_score: float  # 30 points
    profit_factor_score: float  # 20 points
    drawdown_score: float  # 20 points
    win_rate_score: float  # 15 points
    trend_score: float  # 15 points
    
    # Metadata
    metrics: StrategyMetrics
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        return (
            f"Performance Score: {self.total_score:.1f}/100\n"
            f"  Return: {self.return_score:.1f}/30\n"
            f"  Profit Factor: {self.profit_factor_score:.1f}/20\n"
            f"  Drawdown: {self.drawdown_score:.1f}/20\n"
            f"  Win Rate: {self.win_rate_score:.1f}/15\n"
            f"  Trend: {self.trend_score:.1f}/15"
        )


class PerformanceTracker:
    """Track and score strategy performance"""
    
    # Scoring weights
    RETURN_WEIGHT = 30.0
    PROFIT_FACTOR_WEIGHT = 20.0
    DRAWDOWN_WEIGHT = 20.0
    WIN_RATE_WEIGHT = 15.0
    TREND_WEIGHT = 15.0
    
    # Performance thresholds
    EXCELLENT_RETURN = 0.10  # 10% monthly
    GOOD_RETURN = 0.05  # 5% monthly
    EXCELLENT_PROFIT_FACTOR = 2.0
    GOOD_PROFIT_FACTOR = 1.5
    MAX_ACCEPTABLE_DRAWDOWN = 0.10  # 10%
    EXCELLENT_WIN_RATE = 0.60  # 60%
    GOOD_WIN_RATE = 0.50  # 50%
    
    def __init__(self):
        self.strategy_metrics: Dict[TradingLayer, StrategyMetrics] = {}
        
        # Initialize metrics for each layer
        for layer in TradingLayer:
            self.strategy_metrics[layer] = StrategyMetrics(layer=layer)
        
        logger.info("Performance tracker initialized for all trading layers")
    
    def update_metrics(
        self,
        layer: TradingLayer,
        trade_pnl: float,
        trade_costs: float,
        current_equity: float
    ) -> None:
        """Update metrics after a trade closes
        
        Args:
            layer: Trading layer (intraday/swing/etc)
            trade_pnl: Net P&L from trade
            trade_costs: Transaction costs
            current_equity: Current equity value for curve
        """
        metrics = self.strategy_metrics[layer]
        
        # Update trade counts
        metrics.total_trades += 1
        if trade_pnl > 0:
            metrics.winning_trades += 1
            metrics.gross_profit += trade_pnl
        else:
            metrics.losing_trades += 1
            metrics.gross_loss += trade_pnl  # Already negative
        
        metrics.net_pnl += trade_pnl
        metrics.total_costs += trade_costs
        
        # Update cost efficiency
        if metrics.gross_profit > 0:
            metrics.cost_to_profit_ratio = metrics.total_costs / metrics.gross_profit
        
        # Update equity curve
        metrics.equity_curve.append(current_equity)
        if len(metrics.equity_curve) > 100:
            metrics.equity_curve = metrics.equity_curve[-100:]  # Keep last 100
        
        # Calculate equity curve slope (trend)
        if len(metrics.equity_curve) >= 5:
            metrics.equity_curve_slope = self._calculate_trend(metrics.equity_curve)
        
        # Update timestamps
        metrics.last_trade_time = datetime.now()
        metrics.last_updated = datetime.now()
        
        logger.info(f"[{layer.value.upper()}] Metrics updated: "
                   f"{metrics.total_trades} trades, {metrics.win_rate:.1f}% win rate, "
                   f"PF: {metrics.profit_factor:.2f}")
    
    def calculate_score(
        self,
        layer: TradingLayer,
        allocated_capital: float
    ) -> PerformanceScore:
        """Calculate comprehensive performance score (0-100)
        
        Args:
            layer: Trading layer to score
            allocated_capital: Capital allocated to this layer
            
        Returns:
            PerformanceScore with detailed breakdown
        """
        metrics = self.strategy_metrics[layer]
        
        # If no trades, return neutral score
        if metrics.total_trades == 0:
            return PerformanceScore(
                total_score=50.0,  # Neutral
                return_score=15.0,
                profit_factor_score=10.0,
                drawdown_score=10.0,
                win_rate_score=7.5,
                trend_score=7.5,
                metrics=metrics
            )
        
        # 1. Return Score (30 points)
        return_pct = (metrics.net_pnl / allocated_capital) if allocated_capital > 0 else 0
        return_score = self._score_returns(return_pct)
        
        # 2. Profit Factor Score (20 points)
        profit_factor_score = self._score_profit_factor(metrics.profit_factor)
        
        # 3. Drawdown Score (20 points) - lower is better
        drawdown_score = self._score_drawdown(metrics.max_drawdown, allocated_capital)
        
        # 4. Win Rate Score (15 points)
        win_rate_score = self._score_win_rate(metrics.win_rate / 100.0)
        
        # 5. Trend Score (15 points)
        trend_score = self._score_trend(metrics.equity_curve_slope)
        
        # Total score
        total_score = (
            return_score +
            profit_factor_score +
            drawdown_score +
            win_rate_score +
            trend_score
        )
        
        return PerformanceScore(
            total_score=round(total_score, 1),
            return_score=round(return_score, 1),
            profit_factor_score=round(profit_factor_score, 1),
            drawdown_score=round(drawdown_score, 1),
            win_rate_score=round(win_rate_score, 1),
            trend_score=round(trend_score, 1),
            metrics=metrics
        )
    
    def _score_returns(self, return_pct: float) -> float:
        """Score returns (0-30 points)"""
        if return_pct >= self.EXCELLENT_RETURN:
            return 30.0
        elif return_pct >= self.GOOD_RETURN:
            # Linear scale between GOOD and EXCELLENT
            ratio = (return_pct - self.GOOD_RETURN) / (self.EXCELLENT_RETURN - self.GOOD_RETURN)
            return 20.0 + (10.0 * ratio)
        elif return_pct > 0:
            # Linear scale between 0 and GOOD
            ratio = return_pct / self.GOOD_RETURN
            return 15.0 + (5.0 * ratio)
        elif return_pct == 0:
            return 15.0  # Neutral
        else:
            # Negative returns
            penalty = min(abs(return_pct) / self.MAX_ACCEPTABLE_DRAWDOWN, 1.0)
            return max(0, 15.0 - (15.0 * penalty))
    
    def _score_profit_factor(self, pf: float) -> float:
        """Score profit factor (0-20 points)"""
        if pf >= self.EXCELLENT_PROFIT_FACTOR:
            return 20.0
        elif pf >= self.GOOD_PROFIT_FACTOR:
            ratio = (pf - self.GOOD_PROFIT_FACTOR) / (self.EXCELLENT_PROFIT_FACTOR - self.GOOD_PROFIT_FACTOR)
            return 15.0 + (5.0 * ratio)
        elif pf >= 1.0:
            ratio = (pf - 1.0) / (self.GOOD_PROFIT_FACTOR - 1.0)
            return 10.0 + (5.0 * ratio)
        else:
            # PF < 1 means losing money
            return max(0, 10.0 * pf)
    
    def _score_drawdown(self, drawdown: float, capital: float) -> float:
        """Score drawdown (0-20 points) - lower drawdown is better"""
        if capital == 0:
            return 10.0  # Neutral
        
        dd_pct = abs(drawdown) / capital
        
        if dd_pct == 0:
            return 20.0
        elif dd_pct <= self.MAX_ACCEPTABLE_DRAWDOWN / 2:  # <= 5%
            return 20.0 - (dd_pct / (self.MAX_ACCEPTABLE_DRAWDOWN / 2)) * 5.0
        elif dd_pct <= self.MAX_ACCEPTABLE_DRAWDOWN:  # 5-10%
            ratio = (dd_pct - self.MAX_ACCEPTABLE_DRAWDOWN / 2) / (self.MAX_ACCEPTABLE_DRAWDOWN / 2)
            return 15.0 - (ratio * 10.0)
        else:
            # Excessive drawdown
            penalty = min((dd_pct - self.MAX_ACCEPTABLE_DRAWDOWN) / self.MAX_ACCEPTABLE_DRAWDOWN, 1.0)
            return max(0, 5.0 - (5.0 * penalty))
    
    def _score_win_rate(self, win_rate: float) -> float:
        """Score win rate (0-15 points)"""
        if win_rate >= self.EXCELLENT_WIN_RATE:
            return 15.0
        elif win_rate >= self.GOOD_WIN_RATE:
            ratio = (win_rate - self.GOOD_WIN_RATE) / (self.EXCELLENT_WIN_RATE - self.GOOD_WIN_RATE)
            return 10.0 + (5.0 * ratio)
        else:
            # Below 50% win rate
            return max(0, 10.0 * (win_rate / self.GOOD_WIN_RATE))
    
    def _score_trend(self, slope: float) -> float:
        """Score equity curve trend (0-15 points)"""
        # Slope > 0 means upward trending equity
        if slope >= 0.05:  # Strong uptrend
            return 15.0
        elif slope >= 0.02:  # Moderate uptrend
            return 12.0
        elif slope >= 0:  # Slight uptrend
            return 10.0
        elif slope >= -0.02:  # Slight downtrend
            return 7.0
        elif slope >= -0.05:  # Moderate downtrend
            return 4.0
        else:  # Strong downtrend
            return 0.0
    
    def _calculate_trend(self, equity_curve: List[float]) -> float:
        """Calculate equity curve trend using linear regression slope
        
        Returns:
            Slope of equity curve (positive = uptrend)
        """
        if len(equity_curve) < 2:
            return 0.0
        
        n = len(equity_curve)
        x = list(range(n))
        y = equity_curve
        
        # Simple linear regression
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        
        # Normalize by mean equity to get percentage slope
        if y_mean != 0:
            slope = slope / y_mean
        
        return slope
    
    def get_metrics(self, layer: TradingLayer) -> StrategyMetrics:
        """Get current metrics for a layer"""
        return self.strategy_metrics[layer]
    
    def should_kill_strategy(self, layer: TradingLayer, min_trades: int = 50) -> bool:
        """Determine if strategy should be killed based on poor performance
        
        Args:
            layer: Trading layer to check
            min_trades: Minimum trades before kill decision
            
        Returns:
            True if strategy should be disabled
        """
        metrics = self.strategy_metrics[layer]
        
        # Need minimum sample size
        if metrics.total_trades < min_trades:
            return False
        
        # Kill conditions
        kill_reasons = []
        
        # 1. Profit factor < 1 (losing money overall)
        if metrics.profit_factor < 1.0:
            kill_reasons.append(f"Profit factor {metrics.profit_factor:.2f} < 1.0")
        
        # 2. Excessive cost ratio (>50%)
        if metrics.cost_to_profit_ratio > 0.5:
            kill_reasons.append(f"Cost ratio {metrics.cost_to_profit_ratio*100:.1f}% > 50%")
        
        # 3. Severe drawdown (>20%)
        # This would need capital context, skipping for now
        
        if kill_reasons:
            logger.critical(f"[{layer.value.upper()}] STRATEGY KILL SWITCH TRIGGERED: {', '.join(kill_reasons)}")
            return True
        
        return False


# Global instance
performance_tracker = PerformanceTracker()


if __name__ == "__main__":
    """Test performance scoring"""
    print("\n" + "="*80)
    print("PERFORMANCE TRACKER TEST")
    print("="*80 + "\n")
    
    tracker = PerformanceTracker()
    allocated_capital = 10000.0
    
    # Simulate some trades
    print("Simulating intraday trades...")
    trades = [
        (150, 15, 10150),  # Win
        (-80, 10, 10070),  # Loss
        (200, 18, 10270),  # Win
        (180, 16, 10450),  # Win
        (-100, 12, 10350), # Loss
    ]
    
    for pnl, costs, equity in trades:
        tracker.update_metrics(TradingLayer.INTRADAY, pnl, costs, equity)
    
    # Calculate score
    score = tracker.calculate_score(TradingLayer.INTRADAY, allocated_capital)
    metrics = tracker.get_metrics(TradingLayer.INTRADAY)
    
    print("\nMetrics:")
    print(f"  Total trades: {metrics.total_trades}")
    print(f"  Win rate: {metrics.win_rate:.1f}%")
    print(f"  Profit factor: {metrics.profit_factor:.2f}")
    print(f"  Net P&L: ₹{metrics.net_pnl:.2f}")
    print(f"  Cost ratio: {metrics.cost_to_profit_ratio*100:.1f}%")
    print(f"\n{score}")
    print("\n" + "="*80 + "\n")
