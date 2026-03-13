"""
Strong Dip Opportunity Engine (SDOE)
=====================================

Strategy: Find quality stocks that are temporarily down but have strong
underlying fundamentals/technicals and attractive rebound potential.

CORE IDEA:
- NOT blind "buy any falling stock"
- IS "strong stocks on temporary decline"

Target Holding Period:
- Short term: 5-20 trading days
- Medium term: 20-90 trading days

Scoring Model (0-100):
- Decline Attractiveness: 20 pts
- Quality/Strength: 25 pts
- Stabilization: 20 pts
- Recovery Confirmation: 15 pts
- Market+Sector Alignment: 10 pts
- Upside/Target Bonus: 10 pts

Classification:
- 80+: Strong Buy Opportunity
- 65-79: Buy Watchlist / Early Entry Zone
- 50-64: Monitor Only
- <50: Reject
"""
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import numpy as np

from strategies.base import BaseStrategy, Signal
from config import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION (Overridable via config.py / environment)
# ══════════════════════════════════════════════════════════════════════════════

SDOE_CONFIG = {
    # ── Decline Filter Thresholds ──────────────────────────────────────────────
    "decline_20d_min_pct": 3.0,      # Min decline from 20-day high (lowered for more opportunities)
    "decline_60d_min_pct": 5.0,      # Min decline from 60-day high
    "decline_max_pct": 40.0,         # Max decline (avoid falling knives)
    "decline_daily_max_pct": 12.0,   # Reject if single-day crash > 12%
    
    # ── Quality Thresholds ─────────────────────────────────────────────────────
    "min_market_cap_cr": 500,        # Min market cap in crores (₹5B) - allows mid-caps
    "min_avg_volume_cr": 1,          # Min 20-day avg traded value in crores
    "min_roe_pct": 8.0,              # Prefer ROE > 8%
    "max_de_ratio": 2.5,             # Debt/Equity < 2.5
    "min_6m_rs": -25.0,              # 6-month relative strength vs NIFTY (allow underperformance)
    
    # ── Stabilization Thresholds ───────────────────────────────────────────────
    "rsi_oversold": 30,              # RSI below this = oversold
    "rsi_recovery_min": 35,          # RSI must recover above this
    "stabilization_days": 3,         # No new lower low in X days
    "price_above_low_pct": 3.0,      # Price must be X% above recent low
    
    # ── Recovery Confirmation ──────────────────────────────────────────────────
    "recovery_volume_ratio": 1.2,    # Volume > 1.2x average on up days
    "recovery_close_vs_range": 0.6,  # Close in upper 60% of day's range
    "recovery_above_sma": 20,        # Prefer if price > 20 SMA
    
    # ── Market/Sector Context ──────────────────────────────────────────────────
    "allow_bearish_market_entry": True,   # Allow reduced-size entries in bear market
    "bearish_position_reduction": 0.5,    # Reduce position size by 50% in bearish regime
    "sector_weakness_max_days": 20,       # Sector can't be weak for > 20 days
    
    # ── Scoring Weights ────────────────────────────────────────────────────────
    "weight_decline": 20,
    "weight_quality": 25,
    "weight_stabilization": 20,
    "weight_recovery": 15,
    "weight_market_sector": 10,
    "weight_upside_bonus": 10,
    
    # ── Classification Thresholds ──────────────────────────────────────────────
    "score_strong_buy": 80,
    "score_watchlist": 65,
    "score_monitor": 50,
    
    # ── Risk/Reward ────────────────────────────────────────────────────────────
    "default_stop_loss_pct": 5.0,    # Stop loss % below entry
    "min_risk_reward": 2.0,          # Minimum R:R ratio
    "target_recovery_pct": 15.0,     # Default target: recover 15% of decline
    
    # ── Event Risk ─────────────────────────────────────────────────────────────
    "earnings_blackout_days": 2,     # Avoid entry if earnings within 2 days
}


class SDOECategory(str, Enum):
    """SDOE signal classification"""
    STRONG_BUY = "Strong Buy"
    WATCHLIST = "Watchlist"
    MONITOR = "Monitor"
    REJECT = "Reject"


class HoldingHorizon(str, Enum):
    """Expected holding period"""
    SHORT = "5-20 days"
    MEDIUM = "20-45 days"
    LONG = "45-90 days"


@dataclass
class DeclineMetrics:
    """Metrics describing the stock's decline"""
    price_current: float
    high_20d: float
    high_60d: float
    high_52w: float
    low_20d: float
    decline_from_20d_pct: float
    decline_from_60d_pct: float
    decline_from_52w_pct: float
    worst_single_day_pct: float = 0.0
    decline_started_days_ago: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QualityMetrics:
    """Metrics describing stock quality"""
    market_cap_cr: float = 0.0
    avg_volume_cr: float = 0.0
    roe_pct: Optional[float] = None
    de_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    sector: str = "Other"
    relative_strength_6m: float = 0.0
    is_sector_leader: bool = False
    quality_score: int = 0  # 0-25
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StabilizationMetrics:
    """Metrics describing stabilization after decline"""
    rsi_14: float = 50.0
    rsi_recovering: bool = False
    days_since_new_low: int = 0
    price_above_low_pct: float = 0.0
    forming_base: bool = False
    bullish_reversal_candle: bool = False
    close_vs_range_pct: float = 0.5
    stabilization_score: int = 0  # 0-20
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RecoveryMetrics:
    """Metrics describing early recovery signals"""
    above_prev_day_high: bool = False
    volume_vs_average: float = 1.0
    above_sma_20: bool = False
    above_sma_50: bool = False
    sector_relative_strength: float = 0.0
    recovery_score: int = 0  # 0-15
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MarketContext:
    """Market and sector context"""
    nifty_regime: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    nifty_change_1m_pct: float = 0.0
    sector_trend: str = "NEUTRAL"
    sector_change_1m_pct: float = 0.0
    vix_level: Optional[float] = None
    market_score: int = 0  # 0-10
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SDOERejectionReason:
    """Reason for rejection"""
    code: str
    message: str
    rule_name: str
    rule_value: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SDOESignal:
    """Complete SDOE signal with all context"""
    symbol: str
    exchange: str = "NSE"
    strategy: str = "SDOE"
    
    # Scores
    total_score: int = 0
    category: SDOECategory = SDOECategory.REJECT
    
    # Score breakdown
    decline_score: int = 0
    quality_score: int = 0
    stabilization_score: int = 0
    recovery_score: int = 0
    market_score: int = 0
    upside_bonus: int = 0
    
    # Detailed metrics
    decline_metrics: Optional[DeclineMetrics] = None
    quality_metrics: Optional[QualityMetrics] = None
    stabilization_metrics: Optional[StabilizationMetrics] = None
    recovery_metrics: Optional[RecoveryMetrics] = None
    market_context: Optional[MarketContext] = None
    
    # Trade parameters
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0  # Conservative target
    target_2: float = 0.0  # Aggressive target
    risk_reward_ratio: float = 0.0
    
    # Holding horizon
    holding_horizon: HoldingHorizon = HoldingHorizon.MEDIUM
    
    # Selection/rejection
    is_approved: bool = False
    selection_reasons: List[str] = field(default_factory=list)
    rejection_reasons: List[SDOERejectionReason] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    
    # Timestamps
    analyzed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "strategy": self.strategy,
            "total_score": self.total_score,
            "category": self.category.value,
            "score_breakdown": {
                "decline": self.decline_score,
                "quality": self.quality_score,
                "stabilization": self.stabilization_score,
                "recovery": self.recovery_score,
                "market": self.market_score,
                "upside_bonus": self.upside_bonus,
            },
            "decline_metrics": self.decline_metrics.to_dict() if self.decline_metrics else None,
            "quality_metrics": self.quality_metrics.to_dict() if self.quality_metrics else None,
            "stabilization_metrics": self.stabilization_metrics.to_dict() if self.stabilization_metrics else None,
            "recovery_metrics": self.recovery_metrics.to_dict() if self.recovery_metrics else None,
            "market_context": self.market_context.to_dict() if self.market_context else None,
            "trade_params": {
                "entry_zone": [self.entry_zone_low, self.entry_zone_high],
                "stop_loss": self.stop_loss,
                "target_1": self.target_1,
                "target_2": self.target_2,
                "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            },
            "holding_horizon": self.holding_horizon.value,
            "is_approved": self.is_approved,
            "selection_reasons": self.selection_reasons,
            "rejection_reasons": [r.to_dict() for r in self.rejection_reasons],
            "risk_factors": self.risk_factors,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  SDOE SCORING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class SDOEScoringEngine:
    """
    Strong Dip Opportunity Engine - Scoring and Signal Generation
    
    Identifies quality stocks that are temporarily down with strong
    rebound potential for short-to-medium term investment.
    """
    
    def __init__(self, broker=None, config: Dict = None):
        """
        Initialize SDOE Scoring Engine
        
        Args:
            broker: Broker instance for fetching live/historical data
            config: Optional config overrides
        """
        self.broker = broker
        self.config = {**SDOE_CONFIG, **(config or {})}
        
        # Cache for market regime
        self._market_regime_cache: Optional[Tuple[str, datetime]] = None
        self._market_regime_cache_minutes = 15
        
        logger.info("[SDOE] Strong Dip Opportunity Engine initialized")
    
    # ══════════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════
    
    async def analyze_stock(
        self,
        symbol: str,
        historical_data: List[Dict] = None,
        quote: Dict = None,
        fundamentals: Dict = None,
    ) -> SDOESignal:
        """
        Analyze a single stock for SDOE opportunity.
        
        Args:
            symbol: Stock symbol (e.g., "RELIANCE")
            historical_data: List of OHLCV candles (recent 90+ days)
            quote: Current live quote
            fundamentals: Optional fundamental data (ROE, D/E, etc.)
            
        Returns:
            SDOESignal with complete analysis
        """
        signal = SDOESignal(symbol=symbol, analyzed_at=datetime.now())
        
        try:
            # 1. Fetch data if not provided
            if historical_data is None and self.broker:
                historical_data = await self._fetch_historical_data(symbol)
            
            if quote is None and self.broker:
                quote = await self._fetch_quote(symbol)
            
            if not historical_data or len(historical_data) < 60:
                signal.rejection_reasons.append(SDOERejectionReason(
                    code="INSUFFICIENT_DATA",
                    message="Need at least 60 days of historical data",
                    rule_name="analyze_stock.data_check",
                ))
                return signal
            
            # 2. Calculate decline metrics
            decline_metrics = self._calculate_decline_metrics(historical_data, quote)
            signal.decline_metrics = decline_metrics
            
            # 3. Check decline filter (early rejection)
            decline_ok, decline_reasons = self._check_decline_filter(decline_metrics)
            if not decline_ok:
                signal.rejection_reasons.extend(decline_reasons)
                return signal
            
            # 4. Calculate quality metrics
            quality_metrics = await self._calculate_quality_metrics(
                symbol, historical_data, fundamentals
            )
            signal.quality_metrics = quality_metrics
            
            # 5. Check quality filter
            quality_ok, quality_reasons = self._check_quality_filter(quality_metrics)
            if not quality_ok:
                signal.rejection_reasons.extend(quality_reasons)
                return signal
            
            # 6. Calculate stabilization metrics
            stabilization_metrics = self._calculate_stabilization_metrics(
                historical_data, quote
            )
            signal.stabilization_metrics = stabilization_metrics
            
            # 7. Calculate recovery metrics
            recovery_metrics = self._calculate_recovery_metrics(
                historical_data, quote
            )
            signal.recovery_metrics = recovery_metrics
            
            # 8. Get market context
            market_context = await self._get_market_context(symbol)
            signal.market_context = market_context
            
            # 9. Calculate component scores
            signal.decline_score = self._score_decline(decline_metrics)
            signal.quality_score = quality_metrics.quality_score
            signal.stabilization_score = stabilization_metrics.stabilization_score
            signal.recovery_score = recovery_metrics.recovery_score
            signal.market_score = market_context.market_score
            signal.upside_bonus = self._calculate_upside_bonus(
                decline_metrics, quality_metrics
            )
            
            # 10. Calculate total score
            signal.total_score = (
                signal.decline_score +
                signal.quality_score +
                signal.stabilization_score +
                signal.recovery_score +
                signal.market_score +
                signal.upside_bonus
            )
            
            # 11. Classify signal
            signal.category = self._classify_signal(signal.total_score)
            
            # 12. Calculate trade parameters
            self._calculate_trade_params(signal, historical_data, quote)
            
            # 13. Determine if approved
            signal.is_approved = self._determine_approval(signal)
            
            # 14. Build selection/rejection reasons
            self._build_reasons(signal)
            
            logger.info(
                f"[SDOE] {symbol}: Score={signal.total_score}/100 "
                f"({signal.category.value}) | "
                f"Decline={signal.decline_score}, Quality={signal.quality_score}, "
                f"Stabil={signal.stabilization_score}, Recovery={signal.recovery_score}"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"[SDOE] Error analyzing {symbol}: {e}")
            signal.rejection_reasons.append(SDOERejectionReason(
                code="ANALYSIS_ERROR",
                message=str(e),
                rule_name="analyze_stock",
            ))
            return signal
    
    async def scan_universe(
        self,
        symbols: List[str],
        min_score: int = None,
    ) -> Dict[str, List[SDOESignal]]:
        """
        Scan a list of symbols and categorize results.
        
        Args:
            symbols: List of symbols to scan
            min_score: Optional minimum score filter
            
        Returns:
            Dict with keys: "strong_buy", "watchlist", "monitor", "rejected"
        """
        import asyncio
        
        results = {
            "strong_buy": [],
            "watchlist": [],
            "monitor": [],
            "rejected": [],
        }
        
        min_score = min_score or self.config["score_monitor"]
        
        # Process with rate limiting (avoid yfinance throttle)
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
        
        async def analyze_with_limit(symbol: str):
            async with semaphore:
                try:
                    signal = await self.analyze_stock(symbol)
                    return signal
                except Exception as e:
                    logger.warning(f"[SDOE] Failed to analyze {symbol}: {e}")
                    return None
                finally:
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)
        
        # Run analysis with concurrency
        tasks = [analyze_with_limit(symbol) for symbol in symbols]
        signals = await asyncio.gather(*tasks)
        
        for signal in signals:
            if signal is None:
                continue
                
            if signal.category == SDOECategory.STRONG_BUY:
                results["strong_buy"].append(signal)
            elif signal.category == SDOECategory.WATCHLIST:
                results["watchlist"].append(signal)
            elif signal.category == SDOECategory.MONITOR:
                results["monitor"].append(signal)
            else:
                results["rejected"].append(signal)
        
        # Sort by score descending
        for key in ["strong_buy", "watchlist", "monitor"]:
            results[key].sort(key=lambda x: x.total_score, reverse=True)
        
        logger.info(
            f"[SDOE] Scan complete: {len(results['strong_buy'])} strong buy, "
            f"{len(results['watchlist'])} watchlist, "
            f"{len(results['monitor'])} monitor, "
            f"{len(results['rejected'])} rejected"
        )
        
        return results
    
    # ══════════════════════════════════════════════════════════════════════════
    #  DECLINE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _calculate_decline_metrics(
        self,
        candles: List[Dict],
        quote: Dict = None,
    ) -> DeclineMetrics:
        """Calculate decline metrics from historical data"""
        
        closes = np.array([c['close'] for c in candles])
        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        
        current_price = quote.get('ltp', closes[-1]) if quote else closes[-1]
        
        # Calculate highs and lows
        high_20d = float(highs[-20:].max()) if len(highs) >= 20 else float(highs.max())
        high_60d = float(highs[-60:].max()) if len(highs) >= 60 else float(highs.max())
        high_52w = float(highs.max())  # Assuming we have ~250 days
        low_20d = float(lows[-20:].min()) if len(lows) >= 20 else float(lows.min())
        
        # Calculate declines
        decline_20d = ((high_20d - current_price) / high_20d) * 100
        decline_60d = ((high_60d - current_price) / high_60d) * 100
        decline_52w = ((high_52w - current_price) / high_52w) * 100
        
        # Find worst single-day decline
        daily_returns = np.diff(closes) / closes[:-1] * 100
        worst_day = float(daily_returns.min()) if len(daily_returns) > 0 else 0.0
        
        # Estimate when decline started (days since peak)
        peak_idx = np.argmax(highs[-60:]) if len(highs) >= 60 else np.argmax(highs)
        decline_started = len(candles) - peak_idx - (len(candles) - min(60, len(candles)))
        
        return DeclineMetrics(
            price_current=current_price,
            high_20d=high_20d,
            high_60d=high_60d,
            high_52w=high_52w,
            low_20d=low_20d,
            decline_from_20d_pct=round(decline_20d, 2),
            decline_from_60d_pct=round(decline_60d, 2),
            decline_from_52w_pct=round(decline_52w, 2),
            worst_single_day_pct=round(abs(worst_day), 2),
            decline_started_days_ago=max(0, decline_started),
        )
    
    def _check_decline_filter(
        self,
        metrics: DeclineMetrics,
    ) -> Tuple[bool, List[SDOERejectionReason]]:
        """Check if stock passes decline filter"""
        reasons = []
        
        # Must have meaningful decline
        min_20d = self.config["decline_20d_min_pct"]
        min_60d = self.config["decline_60d_min_pct"]
        
        has_decline = (
            metrics.decline_from_20d_pct >= min_20d or
            metrics.decline_from_60d_pct >= min_60d
        )
        
        if not has_decline:
            reasons.append(SDOERejectionReason(
                code="INSUFFICIENT_DECLINE",
                message=f"Stock not down enough: {metrics.decline_from_20d_pct:.1f}% from 20d high, "
                        f"{metrics.decline_from_60d_pct:.1f}% from 60d high. "
                        f"Need {min_20d}% or {min_60d}%",
                rule_name="decline_filter.minimum",
                rule_value=f"20d_decline={metrics.decline_from_20d_pct}%, 60d_decline={metrics.decline_from_60d_pct}%",
            ))
            return False, reasons
        
        # Not too much decline (falling knife)
        max_decline = self.config["decline_max_pct"]
        if metrics.decline_from_52w_pct > max_decline:
            reasons.append(SDOERejectionReason(
                code="FALLING_KNIFE",
                message=f"Stock down {metrics.decline_from_52w_pct:.1f}% from 52w high - "
                        f"exceeds {max_decline}% limit (potential falling knife)",
                rule_name="decline_filter.max_decline",
                rule_value=f"decline={metrics.decline_from_52w_pct}%, max={max_decline}%",
            ))
            return False, reasons
        
        # No single-day crash
        max_daily = self.config["decline_daily_max_pct"]
        if metrics.worst_single_day_pct > max_daily:
            reasons.append(SDOERejectionReason(
                code="SINGLE_DAY_CRASH",
                message=f"Stock had {metrics.worst_single_day_pct:.1f}% single-day drop - "
                        f"exceeds {max_daily}% limit (potential structural issue)",
                rule_name="decline_filter.daily_crash",
                rule_value=f"worst_day={metrics.worst_single_day_pct}%, max={max_daily}%",
            ))
            return False, reasons
        
        return True, reasons
    
    def _score_decline(self, metrics: DeclineMetrics) -> int:
        """Score the decline attractiveness (0-20)"""
        score = 0
        max_score = self.config["weight_decline"]  # 20
        
        # Sweet spot: 8-20% decline from 60d high
        decline = metrics.decline_from_60d_pct
        
        if 8 <= decline <= 12:
            score = max_score  # Perfect dip
        elif 5 <= decline < 8:
            score = int(max_score * 0.8)  # Good dip
        elif 12 < decline <= 20:
            score = int(max_score * 0.9)  # Deeper dip, still attractive
        elif 20 < decline <= 30:
            score = int(max_score * 0.6)  # Getting risky
        elif decline > 30:
            score = int(max_score * 0.3)  # High risk
        else:
            score = int(max_score * 0.5)  # Mild decline
        
        return score
    
    # ══════════════════════════════════════════════════════════════════════════
    #  QUALITY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    async def _calculate_quality_metrics(
        self,
        symbol: str,
        candles: List[Dict],
        fundamentals: Dict = None,
    ) -> QualityMetrics:
        """Calculate quality metrics for the stock"""
        
        metrics = QualityMetrics()
        score = 0
        max_score = self.config["weight_quality"]  # 25
        
        # Calculate average volume and traded value
        volumes = [c.get('volume', 0) for c in candles[-20:]]
        closes = [c.get('close', 0) for c in candles[-20:]]
        
        if volumes and closes:
            avg_volume = sum(volumes) / len(volumes)
            avg_close = sum(closes) / len(closes)
            avg_value = (avg_volume * avg_close) / 1e7  # Convert to crores
            metrics.avg_volume_cr = round(avg_value, 2)
        
        # Try to fetch fundamentals if not provided
        if fundamentals is None:
            fundamentals = await self._fetch_fundamentals(symbol)
        
        if fundamentals:
            metrics.market_cap_cr = fundamentals.get('market_cap_cr', 0)
            metrics.roe_pct = fundamentals.get('roe_pct')
            metrics.de_ratio = fundamentals.get('de_ratio')
            metrics.dividend_yield = fundamentals.get('dividend_yield')
            metrics.sector = fundamentals.get('sector', 'Other')
            metrics.is_sector_leader = fundamentals.get('is_sector_leader', False)
        
        # Calculate 6-month relative strength
        if len(candles) >= 120:
            stock_return = ((candles[-1]['close'] - candles[-120]['close']) / 
                          candles[-120]['close']) * 100
            # Assume NIFTY return (simplified - should fetch actual)
            nifty_return = 5.0  # Placeholder
            metrics.relative_strength_6m = round(stock_return - nifty_return, 2)
        
        # Score quality components
        # Market cap (0-7 points)
        if metrics.market_cap_cr >= 50000:
            score += 7  # Large cap
        elif metrics.market_cap_cr >= 20000:
            score += 6  # Mid cap
        elif metrics.market_cap_cr >= 5000:
            score += 4  # Small cap
        elif metrics.market_cap_cr >= 2000:
            score += 2  # Micro cap
        
        # Liquidity (0-5 points)
        if metrics.avg_volume_cr >= 50:
            score += 5
        elif metrics.avg_volume_cr >= 20:
            score += 4
        elif metrics.avg_volume_cr >= 10:
            score += 3
        elif metrics.avg_volume_cr >= 5:
            score += 2
        
        # ROE (0-5 points)
        if metrics.roe_pct:
            if metrics.roe_pct >= 20:
                score += 5
            elif metrics.roe_pct >= 15:
                score += 4
            elif metrics.roe_pct >= 12:
                score += 3
        
        # Debt/Equity (0-4 points)
        if metrics.de_ratio is not None:
            if metrics.de_ratio < 0.5:
                score += 4
            elif metrics.de_ratio < 1.0:
                score += 3
            elif metrics.de_ratio < 1.5:
                score += 2
        
        # Sector leader bonus (0-2 points)
        if metrics.is_sector_leader:
            score += 2
        
        # Dividend bonus (0-2 points)
        if metrics.dividend_yield and metrics.dividend_yield > 1.0:
            score += min(2, int(metrics.dividend_yield / 1.5))
        
        metrics.quality_score = min(score, max_score)
        return metrics
    
    def _check_quality_filter(
        self,
        metrics: QualityMetrics,
    ) -> Tuple[bool, List[SDOERejectionReason]]:
        """Check if stock passes quality filter"""
        reasons = []
        
        # Minimum liquidity check
        min_volume = self.config["min_avg_volume_cr"]
        if metrics.avg_volume_cr < min_volume:
            reasons.append(SDOERejectionReason(
                code="LOW_LIQUIDITY",
                message=f"Average traded value ₹{metrics.avg_volume_cr:.1f}Cr < "
                        f"minimum ₹{min_volume}Cr",
                rule_name="quality_filter.liquidity",
                rule_value=f"avg_volume={metrics.avg_volume_cr}Cr, min={min_volume}Cr",
            ))
            return False, reasons
        
        # D/E ratio check (if available)
        max_de = self.config["max_de_ratio"]
        if metrics.de_ratio is not None and metrics.de_ratio > max_de:
            reasons.append(SDOERejectionReason(
                code="HIGH_DEBT",
                message=f"Debt/Equity ratio {metrics.de_ratio:.2f} > maximum {max_de}",
                rule_name="quality_filter.debt",
                rule_value=f"de_ratio={metrics.de_ratio}, max={max_de}",
            ))
            # Don't reject outright, just add to risk factors
        
        return True, reasons
    
    # ══════════════════════════════════════════════════════════════════════════
    #  STABILIZATION ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _calculate_stabilization_metrics(
        self,
        candles: List[Dict],
        quote: Dict = None,
    ) -> StabilizationMetrics:
        """Calculate stabilization metrics after decline"""
        
        metrics = StabilizationMetrics()
        score = 0
        max_score = self.config["weight_stabilization"]  # 20
        
        closes = np.array([c['close'] for c in candles])
        highs = np.array([c['high'] for c in candles])
        lows = np.array([c['low'] for c in candles])
        
        current_price = quote.get('ltp', closes[-1]) if quote else closes[-1]
        
        # RSI calculation
        metrics.rsi_14 = self._calculate_rsi(closes, 14)
        
        # RSI recovering from oversold
        rsi_oversold = self.config["rsi_oversold"]
        rsi_recovery = self.config["rsi_recovery_min"]
        
        if metrics.rsi_14 > rsi_recovery:
            if metrics.rsi_14 < 45:  # Was oversold, now recovering
                metrics.rsi_recovering = True
                score += 5
        
        # Days since new low
        recent_low = float(lows[-20:].min()) if len(lows) >= 20 else float(lows.min())
        low_idx = np.where(lows[-20:] == recent_low)[0]
        if len(low_idx) > 0:
            metrics.days_since_new_low = 20 - int(low_idx[-1]) - 1
        
        stab_days = self.config["stabilization_days"]
        if metrics.days_since_new_low >= stab_days:
            score += 5  # No new low in X days
        
        # Price above recent low
        metrics.price_above_low_pct = ((current_price - recent_low) / recent_low) * 100
        min_above_low = self.config["price_above_low_pct"]
        if metrics.price_above_low_pct >= min_above_low:
            score += 4
        
        # Forming base (low volatility in last 5 days)
        if len(candles) >= 5:
            recent_range = (highs[-5:].max() - lows[-5:].min()) / closes[-5].mean() * 100
            if recent_range < 5.0:  # Less than 5% range
                metrics.forming_base = True
                score += 3
        
        # Bullish reversal candle
        if len(candles) >= 2:
            yesterday = candles[-2]
            today_open = quote.get('open', candles[-1]['open']) if quote else candles[-1]['open']
            today_close = current_price
            today_low = quote.get('low', candles[-1]['low']) if quote else candles[-1]['low']
            today_high = quote.get('high', candles[-1]['high']) if quote else candles[-1]['high']
            
            # Hammer or bullish engulfing
            body = abs(today_close - today_open)
            lower_wick = min(today_open, today_close) - today_low
            
            if lower_wick > body * 2 and today_close > today_open:
                metrics.bullish_reversal_candle = True
                score += 3
        
        # Close vs day range
        if quote:
            day_range = quote.get('high', current_price) - quote.get('low', current_price)
            if day_range > 0:
                metrics.close_vs_range_pct = (
                    (current_price - quote.get('low', current_price)) / day_range
                )
            
            min_range = self.config["recovery_close_vs_range"]
            if metrics.close_vs_range_pct >= min_range:
                score += 2
        
        metrics.stabilization_score = min(score, max_score)
        return metrics
    
    # ══════════════════════════════════════════════════════════════════════════
    #  RECOVERY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _calculate_recovery_metrics(
        self,
        candles: List[Dict],
        quote: Dict = None,
    ) -> RecoveryMetrics:
        """Calculate early recovery signals"""
        
        metrics = RecoveryMetrics()
        score = 0
        max_score = self.config["weight_recovery"]  # 15
        
        closes = np.array([c['close'] for c in candles])
        volumes = np.array([c.get('volume', 0) for c in candles])
        
        current_price = quote.get('ltp', closes[-1]) if quote else closes[-1]
        current_volume = quote.get('volume', 0) if quote else (volumes[-1] if len(volumes) > 0 else 0)
        
        # Above previous day high
        if len(candles) >= 2:
            prev_high = candles[-2]['high']
            if current_price > prev_high:
                metrics.above_prev_day_high = True
                score += 4
        
        # Volume vs average
        if len(volumes) >= 20 and current_volume > 0:
            avg_volume = float(volumes[-20:].mean())
            if avg_volume > 0:
                metrics.volume_vs_average = current_volume / avg_volume
                
                vol_ratio = self.config["recovery_volume_ratio"]
                if metrics.volume_vs_average >= vol_ratio:
                    score += 4
        
        # Above 20 SMA
        if len(closes) >= 20:
            sma_20 = float(closes[-20:].mean())
            if current_price > sma_20:
                metrics.above_sma_20 = True
                score += 4
        
        # Above 50 SMA
        if len(closes) >= 50:
            sma_50 = float(closes[-50:].mean())
            if current_price > sma_50:
                metrics.above_sma_50 = True
                score += 3
        
        metrics.recovery_score = min(score, max_score)
        return metrics
    
    # ══════════════════════════════════════════════════════════════════════════
    #  MARKET CONTEXT
    # ══════════════════════════════════════════════════════════════════════════
    
    async def _get_market_context(self, symbol: str) -> MarketContext:
        """Get market and sector context"""
        
        context = MarketContext()
        score = 0
        max_score = self.config["weight_market_sector"]  # 10
        
        # Get cached or fresh market regime
        regime = await self._get_market_regime()
        context.nifty_regime = regime
        
        # Score based on regime
        if regime == "BULLISH":
            score += 8
        elif regime == "NEUTRAL":
            score += 5
        elif regime == "BEARISH":
            if self.config["allow_bearish_market_entry"]:
                score += 2  # Allow but low score
            else:
                score = 0
        
        # Sector analysis (simplified - would need sector data)
        from capital_manager import get_sector
        sector = get_sector(symbol)
        context.sector_trend = "NEUTRAL"  # Placeholder
        
        context.market_score = min(score, max_score)
        return context
    
    async def _get_market_regime(self) -> str:
        """Get market regime with caching"""
        
        # Check cache
        if self._market_regime_cache:
            regime, cached_at = self._market_regime_cache
            if (datetime.now() - cached_at).seconds < self._market_regime_cache_minutes * 60:
                return regime
        
        # Fetch fresh regime
        regime = "NEUTRAL"
        
        if self.broker:
            try:
                from market_regime import MarketRegime
                mr = MarketRegime(self.broker)
                regime = await mr.get_market_regime()
            except Exception as e:
                logger.warning(f"[SDOE] Failed to get market regime: {e}")
        
        self._market_regime_cache = (regime, datetime.now())
        return regime
    
    # ══════════════════════════════════════════════════════════════════════════
    #  UPSIDE BONUS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _calculate_upside_bonus(
        self,
        decline: DeclineMetrics,
        quality: QualityMetrics,
    ) -> int:
        """Calculate upside/target bonus (0-10)"""
        bonus = 0
        max_bonus = self.config["weight_upside_bonus"]  # 10
        
        # Recovery potential based on decline depth
        # Larger declines in quality stocks = higher recovery potential
        if decline.decline_from_60d_pct >= 15 and quality.quality_score >= 15:
            bonus += 5
        elif decline.decline_from_60d_pct >= 10 and quality.quality_score >= 10:
            bonus += 3
        
        # Dividend bonus
        if quality.dividend_yield and quality.dividend_yield > 2.0:
            bonus += 3
        elif quality.dividend_yield and quality.dividend_yield > 1.0:
            bonus += 2
        
        # Sector leader bonus
        if quality.is_sector_leader:
            bonus += 2
        
        return min(bonus, max_bonus)
    
    # ══════════════════════════════════════════════════════════════════════════
    #  CLASSIFICATION & TRADE PARAMS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _classify_signal(self, total_score: int) -> SDOECategory:
        """Classify signal based on total score"""
        if total_score >= self.config["score_strong_buy"]:
            return SDOECategory.STRONG_BUY
        elif total_score >= self.config["score_watchlist"]:
            return SDOECategory.WATCHLIST
        elif total_score >= self.config["score_monitor"]:
            return SDOECategory.MONITOR
        else:
            return SDOECategory.REJECT
    
    def _calculate_trade_params(
        self,
        signal: SDOESignal,
        candles: List[Dict],
        quote: Dict = None,
    ) -> None:
        """Calculate entry, stop-loss, and target levels"""
        
        if not signal.decline_metrics:
            return
        
        current_price = signal.decline_metrics.price_current
        low_20d = signal.decline_metrics.low_20d
        high_60d = signal.decline_metrics.high_60d
        
        # Entry zone: current price to slightly below
        signal.entry_zone_high = current_price
        signal.entry_zone_low = current_price * 0.98  # 2% below current
        
        # Stop loss: below 20d low or fixed percentage
        stop_pct = self.config["default_stop_loss_pct"]
        signal.stop_loss = max(
            low_20d * 0.98,  # Just below 20d low
            current_price * (1 - stop_pct / 100)  # Fixed %
        )
        
        # Targets: recovery towards previous high
        recovery_pct = self.config["target_recovery_pct"]
        decline_amount = high_60d - current_price
        
        signal.target_1 = current_price + (decline_amount * 0.5)   # 50% recovery
        signal.target_2 = current_price + (decline_amount * 0.75)  # 75% recovery
        
        # Risk/Reward calculation
        risk = current_price - signal.stop_loss
        reward = signal.target_1 - current_price
        signal.risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Determine holding horizon based on decline depth
        decline = signal.decline_metrics.decline_from_60d_pct
        if decline <= 10:
            signal.holding_horizon = HoldingHorizon.SHORT
        elif decline <= 20:
            signal.holding_horizon = HoldingHorizon.MEDIUM
        else:
            signal.holding_horizon = HoldingHorizon.LONG
    
    def _determine_approval(self, signal: SDOESignal) -> bool:
        """Determine if signal is approved for trading"""
        
        # Must be at least watchlist quality
        if signal.category in [SDOECategory.REJECT, SDOECategory.MONITOR]:
            return False
        
        # Must have reasonable R:R
        min_rr = self.config["min_risk_reward"]
        if signal.risk_reward_ratio < min_rr:
            signal.rejection_reasons.append(SDOERejectionReason(
                code="POOR_RISK_REWARD",
                message=f"R:R ratio {signal.risk_reward_ratio:.2f} < minimum {min_rr}",
                rule_name="_determine_approval.risk_reward",
                rule_value=f"rr={signal.risk_reward_ratio}, min={min_rr}",
            ))
            return False
        
        # Must have stabilization evidence
        if signal.stabilization_metrics:
            if signal.stabilization_metrics.stabilization_score < 8:
                signal.rejection_reasons.append(SDOERejectionReason(
                    code="NO_STABILIZATION",
                    message="Insufficient stabilization evidence - stock may still be falling",
                    rule_name="_determine_approval.stabilization",
                    rule_value=f"stab_score={signal.stabilization_metrics.stabilization_score}",
                ))
                return False
        
        return True
    
    def _build_reasons(self, signal: SDOESignal) -> None:
        """Build selection and risk factor lists"""
        
        if signal.is_approved:
            # Selection reasons
            if signal.decline_metrics:
                signal.selection_reasons.append(
                    f"Down {signal.decline_metrics.decline_from_60d_pct:.1f}% from 60-day high"
                )
            
            if signal.quality_metrics:
                if signal.quality_metrics.market_cap_cr >= 20000:
                    signal.selection_reasons.append("Large/Mid cap quality stock")
                if signal.quality_metrics.roe_pct and signal.quality_metrics.roe_pct >= 15:
                    signal.selection_reasons.append(f"Strong ROE: {signal.quality_metrics.roe_pct:.1f}%")
            
            if signal.stabilization_metrics:
                if signal.stabilization_metrics.rsi_recovering:
                    signal.selection_reasons.append("RSI recovering from oversold")
                if signal.stabilization_metrics.forming_base:
                    signal.selection_reasons.append("Forming base/consolidation")
                if signal.stabilization_metrics.bullish_reversal_candle:
                    signal.selection_reasons.append("Bullish reversal candle")
            
            if signal.recovery_metrics:
                if signal.recovery_metrics.above_prev_day_high:
                    signal.selection_reasons.append("Price above previous day high")
                if signal.recovery_metrics.above_sma_20:
                    signal.selection_reasons.append("Reclaimed 20 SMA")
        
        # Risk factors (applicable to all)
        if signal.decline_metrics:
            if signal.decline_metrics.decline_from_52w_pct > 25:
                signal.risk_factors.append(
                    f"Large decline from 52w high ({signal.decline_metrics.decline_from_52w_pct:.1f}%)"
                )
        
        if signal.quality_metrics:
            if signal.quality_metrics.de_ratio and signal.quality_metrics.de_ratio > 1.0:
                signal.risk_factors.append(
                    f"Elevated debt ratio: {signal.quality_metrics.de_ratio:.2f}"
                )
        
        if signal.market_context:
            if signal.market_context.nifty_regime == "BEARISH":
                signal.risk_factors.append("Bearish market regime")
    
    # ══════════════════════════════════════════════════════════════════════════
    #  UTILITY METHODS
    # ══════════════════════════════════════════════════════════════════════════
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    async def _fetch_historical_data(self, symbol: str) -> Optional[List[Dict]]:
        """Fetch historical data from broker or yfinance fallback"""
        # Try broker first
        if self.broker:
            try:
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=90)
                
                candles = await self.broker.get_historical_data(
                    symbol=symbol,
                    from_date=start_date,
                    to_date=end_date,
                    interval="day"
                )
                if candles:
                    return candles
            except Exception as e:
                logger.warning(f"[SDOE] Broker fetch failed for {symbol}: {e}")
        
        # Fallback to yfinance
        try:
            import yfinance as yf
            from datetime import datetime, timedelta
            
            ticker = yf.Ticker(f"{symbol}.NS")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=120)  # Get extra days
            
            df = ticker.history(start=start_date, end=end_date)
            
            if df.empty:
                # Try without .NS suffix
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=start_date, end=end_date)
            
            if df.empty:
                logger.warning(f"[SDOE] No yfinance data for {symbol}")
                return None
            
            # Convert to candle format
            candles = []
            for idx, row in df.iterrows():
                candles.append({
                    'date': idx.strftime('%Y-%m-%d'),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume']),
                })
            
            logger.debug(f"[SDOE] Fetched {len(candles)} candles from yfinance for {symbol}")
            return candles
            
        except ImportError:
            logger.warning("[SDOE] yfinance not available for historical data")
            return None
        except Exception as e:
            logger.warning(f"[SDOE] yfinance fetch failed for {symbol}: {e}")
            return None
    
    async def _fetch_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch current quote from broker or yfinance fallback"""
        # Try broker first
        if self.broker:
            try:
                quote = await self.broker.get_quote(symbol)
                if quote:
                    return quote
            except Exception as e:
                logger.warning(f"[SDOE] Broker quote failed for {symbol}: {e}")
        
        # Fallback to yfinance
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(f"{symbol}.NS")
            info = ticker.info or {}
            
            # Try without .NS if needed
            if not info.get('regularMarketPrice'):
                ticker = yf.Ticker(symbol)
                info = ticker.info or {}
            
            ltp = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
            
            if not ltp:
                return None
            
            return {
                'symbol': symbol,
                'ltp': float(ltp),
                'open': float(info.get('open', ltp)),
                'high': float(info.get('dayHigh', ltp)),
                'low': float(info.get('dayLow', ltp)),
                'close': float(info.get('previousClose', ltp)),
                'volume': int(info.get('volume', 0)),
            }
            
        except ImportError:
            logger.warning("[SDOE] yfinance not available for quote")
            return None
        except Exception as e:
            logger.warning(f"[SDOE] yfinance quote failed for {symbol}: {e}")
            return None
    
    async def _fetch_fundamentals(self, symbol: str) -> Optional[Dict]:
        """Fetch fundamental data (ROE, D/E, etc.)"""
        try:
            # Try yfinance as fallback
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.NS")
            info = ticker.info or {}
            
            roe = info.get('returnOnEquity')
            de = info.get('debtToEquity')
            market_cap = info.get('marketCap', 0)
            div_yield = info.get('dividendYield', 0)
            
            return {
                'market_cap_cr': market_cap / 1e7 if market_cap else 0,  # Convert to crores
                'roe_pct': roe * 100 if roe else None,
                'de_ratio': de / 100 if de and de > 10 else de,
                'dividend_yield': div_yield * 100 if div_yield else 0,
                'sector': info.get('sector', 'Other'),
                'is_sector_leader': False,  # Would need custom logic
            }
        except ImportError:
            logger.debug("[SDOE] yfinance not available for fundamentals")
            return None
        except Exception as e:
            logger.debug(f"[SDOE] Failed to fetch fundamentals for {symbol}: {e}")
            return None


# ══════════════════════════════════════════════════════════════════════════════
#  SDOE STRATEGY (Integrates with TradiqAI signal flow)
# ══════════════════════════════════════════════════════════════════════════════

class SDOEStrategy(BaseStrategy):
    """
    Strong Dip Opportunity Engine Strategy
    
    Inherits from BaseStrategy to integrate with existing signal flow.
    """
    
    def __init__(self, broker=None, config: Dict = None):
        default_params = {
            "min_score": 65,
            "max_signals_per_day": 5,
            "enable_watchlist": True,
        }
        if config:
            default_params.update(config)
        
        super().__init__("SDOE", default_params)
        self.broker = broker
        self.scoring_engine = SDOEScoringEngine(broker=broker, config=config)
    
    async def analyze(self, data: any, symbol: str) -> Optional[Signal]:
        """Analyze symbol and generate trading signal"""
        
        # Get SDOE analysis
        sdoe_signal = await self.scoring_engine.analyze_stock(
            symbol=symbol,
            historical_data=data if isinstance(data, list) else None,
        )
        
        # Only generate Signal for approved opportunities
        if not sdoe_signal.is_approved:
            return None
        
        # Convert to standard Signal format
        signal = Signal(
            symbol=symbol,
            action="BUY",
            entry_price=sdoe_signal.entry_zone_high,
            stop_loss=sdoe_signal.stop_loss,
            target=sdoe_signal.target_1,
            quantity=1,  # Placeholder - risk engine will calculate
            confidence=sdoe_signal.total_score / 100.0,
            reason=f"SDOE Score={sdoe_signal.total_score}, {', '.join(sdoe_signal.selection_reasons[:2])}",
            timestamp=datetime.now(),
            product="CNC",  # Delivery for swing/position trades
        )
        
        logger.info(
            f"[SDOE SIGNAL] {symbol}: Score={sdoe_signal.total_score}, "
            f"Entry={signal.entry_price:.2f}, SL={signal.stop_loss:.2f}, "
            f"Target={signal.target:.2f}"
        )
        
        return signal
    
    async def should_exit(self, position: Dict, current_price: float) -> bool:
        """Check if SDOE position should be exited"""
        entry_price = position.get('entry_price', 0)
        stop_loss = position.get('stop_price', 0)
        target = position.get('target_price', 0)
        
        # Exit on stop loss
        if current_price <= stop_loss:
            logger.info(f"[SDOE EXIT] Stop loss hit at {current_price:.2f}")
            return True
        
        # Exit on target
        if target > 0 and current_price >= target:
            logger.info(f"[SDOE EXIT] Target reached at {current_price:.2f}")
            return True
        
        return False
