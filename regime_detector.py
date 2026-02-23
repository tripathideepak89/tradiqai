"""Enhanced Market Regime Detection for Multi-Timeframe Trading
================================================================

Detects market regime across multiple timeframes:
- Intraday regime (5-min/15-min)
- Daily regime (for swing)
- Weekly regime (for mid-term)
- Monthly regime (for long-term)

Regime types:
- TREND_UP: Strong uptrend (allow longs)
- TREND_DOWN: Strong downtrend (allow shorts if enabled)
- RANGE: Sideways movement (reduce/disable entries)
- HIGH_VOLATILITY: Chaotic movement (reduce size)
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RegimeData:
    """Market regime data"""
    regime_type: str  # TREND_UP, TREND_DOWN, RANGE, HIGH_VOLATILITY
    ema_20: float
    ema_50: float
    ema_200: Optional[float]
    atr: float
    atr_percent: float
    timeframe: str
    confidence: float  # 0.0 to 1.0
    last_updated: datetime
    
    def is_bullish(self) -> bool:
        return self.regime_type == "TREND_UP"
    
    def is_bearish(self) -> bool:
        return self.regime_type == "TREND_DOWN"
    
    def is_ranging(self) -> bool:
        return self.regime_type == "RANGE"
    
    def is_high_volatility(self) -> bool:
        return self.regime_type == "HIGH_VOLATILITY"


class RegimeDetector:
    """Detect market regime across multiple timeframes"""
    
    def __init__(self, broker):
        self.broker = broker
        self.cache: Dict[str, RegimeData] = {}
        self.cache_duration_minutes = {
            "5min": 5,
            "15min": 15,
            "daily": 60,
            "weekly": 240,  # 4 hours
        }
    
    async def get_regime(
        self, 
        symbol: str = "NIFTY50", 
        timeframe: str = "15min"
    ) -> Optional[RegimeData]:
        """Get market regime for given timeframe
        
        Args:
            symbol: Index symbol (default NIFTY50)
            timeframe: 5min, 15min, daily, weekly
            
        Returns:
            RegimeData or None if detection fails
        """
        cache_key = f"{symbol}:{timeframe}"
        
        # Check cache
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            age_minutes = (datetime.now() - cached.last_updated).seconds / 60
            if age_minutes < self.cache_duration_minutes[timeframe]:
                return cached
        
        # Fetch and calculate regime
        try:
            regime_data = await self._calculate_regime(symbol, timeframe)
            if regime_data:
                self.cache[cache_key] = regime_data
            return regime_data
        except Exception as e:
            logger.error(f"Failed to detect regime for {symbol} {timeframe}: {e}")
            return None
    
    async def _calculate_regime(
        self, 
        symbol: str, 
        timeframe: str
    ) -> Optional[RegimeData]:
        """Calculate regime from historical data"""
        
        # Determine how much data we need
        lookback_days = {
            "5min": 5,
            "15min": 5,
            "daily": 60,  # For 50 EMA
            "weekly": 250,  # For 200 EMA
        }
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=lookback_days[timeframe])
        
        try:
            # Get historical data
            candles = await self.broker.get_historical_data(
                symbol=symbol,
                from_date=start_time,
                to_date=end_time,
                interval=timeframe
            )
            
            if not candles or len(candles) < 50:
                logger.warning(f"Insufficient data for {symbol} {timeframe}")
                return None
            
            # Extract close prices
            closes = np.array([c['close'] for c in candles])
            highs = np.array([c['high'] for c in candles])
            lows = np.array([c['low'] for c in candles])
            
            # Calculate EMAs
            ema_20 = self._calculate_ema(closes, 20)
            ema_50 = self._calculate_ema(closes, 50)
            ema_200 = self._calculate_ema(closes, 200) if len(closes) >= 200 else None
            
            # Calculate ATR
            atr = self._calculate_atr(highs, lows, closes, 14)
            atr_percent = (atr / closes[-1]) * 100 if closes[-1] > 0 else 0
            
            # Determine regime
            regime_type, confidence = self._determine_regime_type(
                closes[-1], ema_20, ema_50, ema_200, atr_percent
            )
            
            regime_data = RegimeData(
                regime_type=regime_type,
                ema_20=ema_20,
                ema_50=ema_50,
                ema_200=ema_200,
                atr=atr,
                atr_percent=atr_percent,
                timeframe=timeframe,
                confidence=confidence,
                last_updated=datetime.now()
            )
            
            logger.info(f"[REGIME] {symbol} {timeframe}: {regime_type} "
                       f"(confidence: {confidence:.0%}, ATR: {atr_percent:.2f}%)")
            
            return regime_data
            
        except Exception as e:
            logger.error(f"Error calculating regime: {e}")
            return None
    
    def _determine_regime_type(
        self, 
        current_price: float, 
        ema_20: float, 
        ema_50: float, 
        ema_200: Optional[float],
        atr_percent: float
    ) -> tuple[str, float]:
        """Determine regime type and confidence
        
        Returns:
            (regime_type, confidence)
        """
        confidence = 0.5  # Base confidence
        
        # High volatility check (overrides everything)
        if atr_percent > 3.0:  # 3% ATR is high for indices
            return "HIGH_VOLATILITY", 0.8
        
        # Trend determination
        if ema_20 > ema_50:
            # Potential uptrend
            separation_percent = ((ema_20 - ema_50) / ema_50) * 100
            
            if separation_percent > 1.0:
                # Strong uptrend
                confidence = min(0.9, 0.5 + separation_percent * 0.1)
                
                # Additional confirmation from 200 EMA
                if ema_200 and ema_50 > ema_200:
                    confidence = min(0.95, confidence + 0.1)
                
                return "TREND_UP", confidence
            
            elif separation_percent > 0.2:
                # Weak uptrend
                return "TREND_UP", 0.6
            
            else:
                # Too flat, likely ranging
                return "RANGE", 0.7
        
        elif ema_20 < ema_50:
            # Potential downtrend
            separation_percent = ((ema_50 - ema_20) / ema_50) * 100
            
            if separation_percent > 1.0:
                # Strong downtrend
                confidence = min(0.9, 0.5 + separation_percent * 0.1)
                
                if ema_200 and ema_50 < ema_200:
                    confidence = min(0.95, confidence + 0.1)
                
                return "TREND_DOWN", confidence
            
            elif separation_percent > 0.2:
                # Weak downtrend
                return "TREND_DOWN", 0.6
            
            else:
                return "RANGE", 0.7
        
        else:
            # EMAs equal = ranging
            return "RANGE", 0.8
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return float(np.mean(prices))
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return float(ema)
    
    def _calculate_atr(
        self, 
        highs: np.ndarray, 
        lows: np.ndarray, 
        closes: np.ndarray, 
        period: int
    ) -> float:
        """Calculate Average True Range"""
        if len(closes) < period + 1:
            return float(np.mean(highs - lows))
        
        # True Range = max of:
        # 1. High - Low
        # 2. |High - Previous Close|
        # 3. |Low - Previous Close|
        
        tr = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr.append(max(high_low, high_close, low_close))
        
        tr = np.array(tr)
        atr = float(np.mean(tr[-period:]))
        
        return atr
    
    async def get_multi_timeframe_regime(
        self, 
        symbol: str = "NIFTY50"
    ) -> Dict[str, RegimeData]:
        """Get regime for all timeframes
        
        Returns:
            Dict of timeframe -> RegimeData
        """
        regimes = {}
        
        for timeframe in ["15min", "daily", "weekly"]:
            regime = await self.get_regime(symbol, timeframe)
            if regime:
                regimes[timeframe] = regime
        
        return regimes
    
    def print_regime_summary(self, regimes: Dict[str, RegimeData]):
        """Print regime summary"""
        logger.info("\n" + "="*80)
        logger.info("MARKET REGIME ANALYSIS")
        logger.info("="*80)
        
        for timeframe, regime in regimes.items():
            logger.info(f"\n[{timeframe.upper()}]")
            logger.info(f"  Regime: {regime.regime_type}")
            logger.info(f"  Confidence: {regime.confidence:.0%}")
            logger.info(f"  EMA 20: {regime.ema_20:.2f}")
            logger.info(f"  EMA 50: {regime.ema_50:.2f}")
            if regime.ema_200:
                logger.info(f"  EMA 200: {regime.ema_200:.2f}")
            logger.info(f"  ATR: {regime.atr_percent:.2f}%")
        
        logger.info("\n" + "="*80)
    
    def get_trading_bias(self, regimes: Dict[str, RegimeData]) -> str:
        """Get overall trading bias from multi-timeframe analysis
        
        Returns:
            "BULLISH", "BEARISH", "NEUTRAL"
        """
        if not regimes:
            return "NEUTRAL"
        
        # Weight by timeframe importance
        weights = {
            "15min": 0.2,
            "daily": 0.5,
            "weekly": 0.3
        }
        
        bullish_score = 0.0
        bearish_score = 0.0
        
        for timeframe, regime in regimes.items():
            weight = weights.get(timeframe, 0.3)
            
            if regime.is_bullish():
                bullish_score += weight * regime.confidence
            elif regime.is_bearish():
                bearish_score += weight * regime.confidence
        
        if bullish_score > bearish_score * 1.5:
            return "BULLISH"
        elif bearish_score > bullish_score * 1.5:
            return "BEARISH"
        else:
            return "NEUTRAL"


class RegimeBasedRiskAdjuster:
    """Adjust risk based on regime"""
    
    @staticmethod
    def get_position_size_multiplier(regime: RegimeData) -> float:
        """Get position size adjustment based on regime
        
        Returns:
            Multiplier (0.0 to 1.0)
        """
        if regime.is_high_volatility():
            # Cut size in half during high volatility
            return 0.5
        
        if regime.is_ranging():
            # Reduce size in range
            return 0.6
        
        # Strong trend = full size
        if regime.confidence > 0.8:
            return 1.0
        
        # Weak trend = 80% size
        return 0.8
    
    @staticmethod
    def should_enter_new_trades(regime: RegimeData, trading_style: str) -> bool:
        """Determine if new trades should be entered
        
        Args:
            regime: Current regime
            trading_style: intraday, swing, midterm, longterm
            
        Returns:
            True if new trades allowed
        """
        if regime.is_high_volatility() and trading_style in ["swing", "midterm"]:
            # No swing/midterm in high volatility
            return False
        
        if regime.is_ranging():
            if trading_style in ["swing", "midterm"]:
                # No trend-following in range
                return False
            elif trading_style == "intraday":
                # Intraday can trade range with reduced size
                return True
        
        # All other cases allow trading
        return True


logger.info("Enhanced regime detector initialized")
