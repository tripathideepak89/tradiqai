"""Swing trading strategy - Daily timeframe with breakout"""
import logging
from typing import Optional, Dict
import pandas as pd
from datetime import datetime, timedelta

from strategies.base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


class SwingStrategy(BaseStrategy):
    """Swing breakout strategy
    
    Rules:
    - Timeframe: Daily
    - Entry: Breakout above 20-day high with volume spike
    - Stop loss: ATR-based
    - Holding: 2-5 days
    - Exit: Close below 10 EMA or target hit
    """
    
    def __init__(self, parameters: Dict = None):
        default_params = {
            "breakout_period": 20,
            "volume_spike": 1.5,
            "atr_period": 14,
            "atr_multiplier": 2.0,  # SL = Entry - (ATR * multiplier)
            "ema_exit": 10,
            "min_risk_reward": 2.0,
            "max_holding_days": 5,
        }
        
        if parameters:
            default_params.update(parameters)
        
        super().__init__("SwingBreakout", default_params)
    
    async def analyze(
        self,
        data: pd.DataFrame,
        symbol: str
    ) -> Optional[Signal]:
        """Analyze and generate swing signals
        
        Args:
            data: Stock OHLCV data (Daily)
            symbol: Stock symbol
            
        Returns:
            Signal if conditions met, None otherwise
        """
        try:
            if len(data) < 50:  # Need sufficient data
                logger.debug(f"{symbol}: Insufficient data for swing")
                return None
            
            # Calculate indicators
            data = data.copy()
            data['ema_10'] = self.calculate_ema(data['close'], self.parameters['ema_exit'])
            data['atr'] = self.calculate_atr(data, self.parameters['atr_period'])
            data['volume_avg'] = data['volume'].rolling(window=20).mean()
            data['high_20'] = data['high'].rolling(window=self.parameters['breakout_period']).max()
            
            # Get latest values
            latest = data.iloc[-1]
            prev = data.iloc[-2]
            
            # 1. Breakout condition: Close above 20-day high
            if latest['close'] <= prev['high_20']:
                logger.debug(f"{symbol}: No breakout")
                return None
            
            # 2. Volume spike
            volume_ratio = latest['volume'] / latest['volume_avg']
            if volume_ratio < self.parameters['volume_spike']:
                logger.debug(f"{symbol}: No volume spike (ratio: {volume_ratio:.2f})")
                return None
            
            # 3. Bullish candle
            if not self.is_bullish_candle(latest):
                logger.debug(f"{symbol}: Not a bullish candle")
                return None
            
            # Entry and Stop Loss
            entry_price = latest['close']
            atr = latest['atr']
            stop_loss = entry_price - (atr * self.parameters['atr_multiplier'])
            
            # Ensure reasonable stop loss
            risk_per_share = entry_price - stop_loss
            if risk_per_share <= 0 or risk_per_share > entry_price * 0.08:  # Max 8% risk
                logger.debug(f"{symbol}: Invalid stop loss")
                return None
            
            # Target
            target = entry_price + (risk_per_share * self.parameters['min_risk_reward'])
            
            # Position size (placeholder)
            quantity = 1
            
            # Confidence
            confidence = self._calculate_confidence(latest, volume_ratio, atr)
            
            signal = Signal(
                symbol=symbol,
                action="BUY",
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                quantity=quantity,
                confidence=confidence,
                reason=f"Breakout above 20D high, Volume {volume_ratio:.1f}x, ATR {atr:.2f}",
                timestamp=datetime.now()
            )
            
            logger.info(
                f"Swing signal for {symbol}: Entry ₹{entry_price:.2f}, "
                f"SL ₹{stop_loss:.2f}, Target ₹{target:.2f}"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error in swing analysis for {symbol}: {e}")
            return None
    
    async def should_exit(self, position: Dict, current_data: pd.DataFrame) -> bool:
        """Check if swing position should be exited
        
        Exit conditions:
        - Stop loss hit (handled by broker)
        - Target reached
        - Close below 10 EMA
        - Max holding period exceeded
        """
        try:
            if len(current_data) < 10:
                return False
            
            # Add EMA
            current_data = current_data.copy()
            current_data['ema_10'] = self.calculate_ema(
                current_data['close'],
                self.parameters['ema_exit']
            )
            
            latest = current_data.iloc[-1]
            current_price = latest['close']
            
            entry_price = position.get('entry_price', 0)
            target = position.get('target', 0)
            entry_date = position.get('entry_timestamp')
            
            # Exit at target
            if current_price >= target:
                logger.info(f"{position['symbol']}: Swing target reached")
                return True
            
            # Exit if close below 10 EMA
            if latest['close'] < latest['ema_10']:
                logger.info(f"{position['symbol']}: Closed below 10 EMA")
                return True
            
            # Max holding period
            if entry_date:
                entry_datetime = datetime.fromisoformat(entry_date) if isinstance(entry_date, str) else entry_date
                days_held = (datetime.now() - entry_datetime).days
                
                if days_held >= self.parameters['max_holding_days']:
                    logger.info(f"{position['symbol']}: Max holding period reached")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking swing exit: {e}")
            return False
    
    def _calculate_confidence(
        self,
        latest: pd.Series,
        volume_ratio: float,
        atr: float
    ) -> float:
        """Calculate signal confidence"""
        score = 0.5
        
        # Higher volume = higher confidence
        if volume_ratio > 2.5:
            score += 0.2
        elif volume_ratio > 2.0:
            score += 0.15
        elif volume_ratio > 1.5:
            score += 0.1
        
        # Strong candle
        candle_body = abs(latest['close'] - latest['open'])
        candle_range = latest['high'] - latest['low']
        if candle_range > 0 and (candle_body / candle_range) > 0.7:
            score += 0.15
        
        # Close near high
        if latest['close'] > latest['high'] * 0.98:
            score += 0.15
        
        return min(score, 1.0)
