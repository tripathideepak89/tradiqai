"""Market Regime Detection - Don't Trade Blindly"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from brokers.base import BaseBroker

logger = logging.getLogger(__name__)


class MarketRegime:
    """Detect market regime to determine trading bias
    
    CORE PRINCIPLE: Trade only when market has clear direction
    - Bullish regime: Long positions only
    - Bearish regime: Short positions only
    - Neutral regime: No trades
    """
    
    def __init__(self, broker: BaseBroker):
        self.broker = broker
        self.current_regime = "NEUTRAL"
        self.last_check = None
        self.cache_minutes = 15  # Update every 15 minutes
    
    async def get_market_regime(self) -> str:
        """Get current market regime based on NIFTY 50
        
        Returns:
            "BULLISH" - Long bias only (20 EMA > 50 EMA)
            "BEARISH" - Short bias only (20 EMA < 50 EMA)  
            "NEUTRAL" - No trades (flat EMAs + low ATR)
        """
        try:
            # Use cached regime if recent
            if self.last_check and (datetime.now() - self.last_check).seconds < self.cache_minutes * 60:
                return self.current_regime
            
            # Get NIFTY 50 historical data (15-min candles)
            end_time = datetime.now()
            start_time = end_time - timedelta(days=5)  # Need enough data for 50 EMA
            
            try:
                candles = await self.broker.get_historical_data(
                    symbol="NIFTY50",  # Index symbol
                    from_date=start_time,
                    to_date=end_time,
                    interval="15minute"
                )
                
                if not candles or len(candles) < 50:
                    logger.warning("Insufficient NIFTY data for regime detection")
                    return "NEUTRAL"
                
                # Calculate EMAs
                closes = [c['close'] for c in candles]
                ema_20 = self._calculate_ema(closes, 20)
                ema_50 = self._calculate_ema(closes, 50)
                
                # Calculate ATR for volatility check
                atr = self._calculate_atr(candles, 14)
                avg_price = closes[-1]
                atr_pct = (atr / avg_price) * 100 if avg_price > 0 else 0
                
                # Determine regime
                if ema_20 > ema_50 * 1.001:  # 0.1% buffer to avoid whipsaws
                    if atr_pct > 0.5:  # Sufficient volatility
                        regime = "BULLISH"
                    else:
                        regime = "NEUTRAL"  # Flat market despite uptrend
                elif ema_20 < ema_50 * 0.999:
                    if atr_pct > 0.5:
                        regime = "BEARISH"
                    else:
                        regime = "NEUTRAL"
                else:
                    regime = "NEUTRAL"  # EMAs too close
                
                self.current_regime = regime
                self.last_check = datetime.now()
                
                logger.info(
                    f"Market Regime: {regime} | "
                    f"NIFTY: {closes[-1]:.1f} | "
                    f"20 EMA: {ema_20:.1f} | "
                    f"50 EMA: {ema_50:.1f} | "
                    f"ATR: {atr_pct:.2f}%"
                )
                
                return regime
                
            except Exception as e:
                logger.error(f"Failed to fetch NIFTY data: {e}")
                return "NEUTRAL"  # Default to no trading on error
        
        except Exception as e:
            logger.error(f"Market regime detection error: {e}")
            return "NEUTRAL"
    
    def _calculate_ema(self, prices: list, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return sum(prices) / len(prices)
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period  # Start with SMA
        
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_atr(self, candles: list, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(candles) < period + 1:
            return 0
        
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        return sum(true_ranges[-period:]) / period if true_ranges else 0
    
    async def can_trade(self, position_type: str = "LONG") -> bool:
        """Check if trading is allowed based on market regime
        
        Args:
            position_type: "LONG" or "SHORT"
            
        Returns:
            True if trading allowed, False otherwise
        """
        regime = await self.get_market_regime()
        
        if regime == "NEUTRAL":
            logger.debug("No trading - Market regime is NEUTRAL (no clear direction)")
            return False
        
        if position_type == "LONG" and regime == "BEARISH":
            logger.debug("Long trade rejected - Market regime is BEARISH")
            return False
        
        if position_type == "SHORT" and regime == "BULLISH":
            logger.debug("Short trade rejected - Market regime is BULLISH")
            return False
        
        return True
    
    def get_regime_info(self) -> Dict:
        """Get current regime information for logging/monitoring"""
        return {
            "regime": self.current_regime,
            "last_update": self.last_check.isoformat() if self.last_check else None,
            "can_trade_long": self.current_regime in ["BULLISH"],
            "can_trade_short": self.current_regime in ["BEARISH"]
        }
