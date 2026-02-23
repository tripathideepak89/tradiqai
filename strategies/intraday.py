"""Intraday trading strategy - 15 min timeframe with EMA pullback"""
import logging
from typing import Optional, Dict
import pandas as pd
import numpy as np
from datetime import datetime

from strategies.base import BaseStrategy, Signal
from utils.timezone import now_ist

logger = logging.getLogger(__name__)


class IntradayStrategy(BaseStrategy):
    """Intraday EMA pullback strategy
    
    Rules:
    - Timeframe: 15 min
    - Market trend filter: NIFTY above/below 20 EMA
    - Stock selection: Volume > 1.5x average, ATR filter
    - Entry: 20 EMA > 50 EMA, pullback to 20 EMA, bullish candle
    - Stop loss: Below recent swing low, max ₹400 risk
    - Target: Minimum 1:1.5 R:R, trail after 1R
    """
    
    def __init__(self, parameters: Dict = None):
        default_params = {
            "ema_fast": 20,
            "ema_slow": 50,
            "volume_multiplier": 1.5,
            "atr_period": 14,
            "min_atr": 5,  # Minimum ATR to avoid dead stocks
            "swing_lookback": 10,
            "min_risk_reward": 1.5,
            "trail_trigger": 1.0,  # Start trailing after 1R
            "pullback_tolerance": 0.5,  # Percentage tolerance for pullback to EMA
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("IntradayEMAPullback", default_params)
    
    async def analyze(
        self,
        data: pd.DataFrame,
        symbol: str,
        nifty_data: pd.DataFrame = None
    ) -> Optional[Signal]:
        """Analyze and generate intraday signals
        
        Args:
            data: Stock OHLCV data (15 min)
            symbol: Stock symbol
            nifty_data: NIFTY OHLCV data for trend filter
            
        Returns:
            Signal if conditions met, None otherwise
        """
        try:
            if len(data) < 100:  # Need sufficient data
                logger.debug(f"{symbol}: Insufficient data")
                return None
            
            # Calculate indicators
            data = data.copy()
            data['ema_20'] = self.calculate_ema(data['close'], self.parameters['ema_fast'])
            data['ema_50'] = self.calculate_ema(data['close'], self.parameters['ema_slow'])
            data['atr'] = self.calculate_atr(data, self.parameters['atr_period'])
            data['volume_avg'] = data['volume'].rolling(window=20).mean()
            
            # Get latest values
            latest = data.iloc[-1]
            prev = data.iloc[-2]
            
            # 1. Market trend filter (if NIFTY data provided)
            if nifty_data is not None and len(nifty_data) >= 20:
                nifty_data = nifty_data.copy()
                nifty_data['ema_20'] = self.calculate_ema(nifty_data['close'], 20)
                nifty_latest = nifty_data.iloc[-1]
                
                # Only long if NIFTY above 20 EMA (bullish market)
                if nifty_latest['close'] < nifty_latest['ema_20']:
                    logger.debug(f"{symbol}: NIFTY bearish, skipping long")
                    return None
            
            # 2. Volume filter
            if latest['volume'] < latest['volume_avg'] * self.parameters['volume_multiplier']:
                logger.debug(f"{symbol}: Low volume")
                return None
            
            # 3. ATR filter (avoid dead stocks)
            if latest['atr'] < self.parameters['min_atr']:
                logger.debug(f"{symbol}: ATR too low")
                return None
            
            # 4. Trend condition: 20 EMA > 50 EMA
            if latest['ema_20'] <= latest['ema_50']:
                logger.debug(f"{symbol}: Downtrend or flat")
                return None
            
            # 5. Pullback to 20 EMA
            # Price should be near 20 EMA (within tolerance)
            tolerance = self.parameters['pullback_tolerance']
            ema_distance = abs(latest['close'] - latest['ema_20']) / latest['close'] * 100
            
            if ema_distance > tolerance:
                logger.debug(f"{symbol}: Not at EMA pullback")
                return None
            
            # 6. Bullish candle confirmation
            if not self.is_bullish_candle(latest):
                logger.debug(f"{symbol}: Not a bullish candle")
                return None
            
            # 7. Price above 20 EMA
            if latest['close'] < latest['ema_20']:
                logger.debug(f"{symbol}: Price below 20 EMA")
                return None
            
            # Entry and Stop Loss
            entry_price = latest['close']
            swing_low = self.get_swing_low(data, self.parameters['swing_lookback'])
            stop_loss = swing_low * 0.995  # Slightly below swing low
            
            risk_per_share = entry_price - stop_loss
            
            # Ensure reasonable stop loss
            if risk_per_share <= 0 or risk_per_share > entry_price * 0.05:  # Max 5% risk
                logger.debug(f"{symbol}: Invalid stop loss")
                return None
            
            # Target (minimum 1:1.5 R:R)
            target = entry_price + (risk_per_share * self.parameters['min_risk_reward'])
            
            # Calculate position size (will be adjusted by risk engine)
            quantity = 1  # Placeholder - risk engine will calculate properly
            
            # Confidence score
            confidence = self._calculate_confidence(data, latest)
            
            signal = Signal(
                symbol=symbol,
                action="BUY",
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                quantity=quantity,
                confidence=confidence,
                reason=f"EMA pullback: Price near 20EMA, Volume {latest['volume']/latest['volume_avg']:.1f}x, ATR {latest['atr']:.2f}",
                timestamp=datetime.now()
            )
            
            logger.info(
                f"Signal generated for {symbol}: Entry ₹{entry_price:.2f}, "
                f"SL ₹{stop_loss:.2f}, Target ₹{target:.2f}, Confidence {confidence:.2f}"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    async def should_exit(self, position: Dict, current_price: float) -> bool:
        """Check if position should be exited
        
        Exit conditions:
        - Stop loss hit (handled by broker)
        - Target reached
        - Trailing stop triggered
        - End of day (for intraday)
        """
        entry_price = position.get('entry_price', 0)
        stop_loss = position.get('stop_loss', 0)
        target = position.get('target', 0)
        
        # Calculate gain
        risk = entry_price - stop_loss
        gain = current_price - entry_price
        r_multiple = gain / risk if risk > 0 else 0
        
        # Exit at target
        if current_price >= target:
            logger.info(f"{position['symbol']}: Target reached at ₹{current_price:.2f}")
            return True
        
        # Trailing stop after 1R
        if r_multiple >= self.parameters['trail_trigger']:
            # Trail at 0.5R
            trailing_stop = entry_price + (risk * 0.5)
            if current_price < trailing_stop:
                logger.info(f"{position['symbol']}: Trailing stop hit at ₹{current_price:.2f}")
                return True
        
        # Check if it's near market close (exit intraday positions)
        now = now_ist().time()
        market_close = datetime.strptime("15:15", "%H:%M").time()  # Exit 15 min before close
        
        if now >= market_close:
            logger.info(f"{position['symbol']}: End of day exit")
            return True
        
        return False
    
    def _calculate_confidence(self, data: pd.DataFrame, latest: pd.Series) -> float:
        """Calculate signal confidence score (0-1)"""
        score = 0.5  # Base score
        
        # Higher volume = higher confidence
        volume_ratio = latest['volume'] / latest['volume_avg']
        if volume_ratio > 2.0:
            score += 0.2
        elif volume_ratio > 1.5:
            score += 0.1
        
        # Stronger trend = higher confidence
        ema_spread = (latest['ema_20'] - latest['ema_50']) / latest['close'] * 100
        if ema_spread > 2.0:
            score += 0.2
        elif ema_spread > 1.0:
            score += 0.1
        
        # Close near high = higher confidence
        if latest['close'] > latest['high'] * 0.95:
            score += 0.1
        
        return min(score, 1.0)
