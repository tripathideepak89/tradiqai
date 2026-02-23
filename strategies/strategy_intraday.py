"""Intraday Trading Strategy (20% Allocation)
===========================================

Objective: Tactical momentum capture within a single day
Expected Return: 15% annually
Max Drawdown: 12%
Holding Period: Minutes to Hours

ENTRY CONDITIONS (LONG):
- Market regime == TREND_UP  
- Price > VWAP
- 20EMA > 50EMA
- Breakout above intraday high
- Volume >= 1.8x average
- NOT in first 15 minutes
- NOT a range day

RISK RULES:
- Risk per trade: 0.7% of intraday capital
- Max trades per day: 2
- Max open positions: 1
- Stop loss: Recent swing low OR 1x ATR

EXIT RULES:
- Price hits stop loss
- Price hits 1.5R target (move stop to breakeven)
- Time >= 15:20 (EOD exit)
- No progress after 3 candles (exit 50%)
"""
import logging
from typing import Optional, Dict, List
from datetime import datetime, time
import numpy as np

from strategies.base import BaseStrategy, Signal, SignalDirection
from trading_styles import TradingStyle
from regime_detector import RegimeDetector
from brokers.base import BaseBroker

logger = logging.getLogger(__name__)


class IntradayStrategy(BaseStrategy):
    """Intraday momentum strategy"""
    
    def __init__(self, broker: BaseBroker, regime_detector: RegimeDetector):
        super().__init__("intraday")
        self.broker = broker
        self.regime_detector = regime_detector
        self.style = TradingStyle.INTRADAY
        
        # Intraday-specific settings
        self.min_volume_multiplier = 1.8
        self.no_trade_start = time(9, 15)  # No trade before 9:15
        self.no_trade_end = time(9, 30)    # No trade before 9:30 (first 15 min)
        self.eod_exit_time = time(15, 20)  # Exit all by 3:20 PM
        self.profit_target_r = 1.5
        self.stop_loss_atr_multiplier = 1.0
        self.breakeven_trigger_r = 1.0  # Move to BE at 1R
        
        # Tracking
        self.trades_today = 0
        self.max_trades_per_day = 2
        self.last_trade_date = None
    
    async def generate_signal(self, symbol: str, market_data: Dict) -> Optional[Signal]:
        """Generate intraday signal for a symbol
        
        Args:
            symbol: Stock symbol
            market_data: Dict with 'candles', 'quote', 'vwap'
            
        Returns:
            Signal or None
        """
        try:
            # Reset daily counter if new day
            today = datetime.now().date()
            if self.last_trade_date != today:
                self.trades_today = 0
                self.last_trade_date = today
            
            # Check if max trades reached
            if self.trades_today >= self.max_trades_per_day:
                logger.debug(f"[INTRADAY] Max trades ({self.max_trades_per_day}) reached today")
                return None
            
            # Check time filters
            current_time = datetime.now().time()
            if not self._is_trading_time(current_time):
                return None
            
            # Get market regime
            regime = await self.regime_detector.get_regime("NIFTY50", "15min")
            if not regime:
                logger.warning("[INTRADAY] Could not determine market regime")
                return None
            
            # Check if regime allows intraday trading
            if regime.is_high_volatility():
                logger.debug(f"[INTRADAY] High volatility regime, skipping")
                return None
            
            # Get intraday data
            candles = market_data.get('candles', [])
            if len(candles) < 50:
                return None
            
            quote = market_data.get('quote')
            if not quote:
                return None
            
            current_price = quote.get('ltp', 0)
            if current_price == 0:
                return None
            
            # Check if it's a range day
            if self._is_range_day(candles):
                logger.debug(f"[INTRADAY] {symbol} is range-bound, skipping")
                return None
            
            # Calculate indicators
            ema_20 = self._calculate_ema([c['close'] for c in candles], 20)
            ema_50 = self._calculate_ema([c['close'] for c in candles], 50)
            vwap = market_data.get('vwap', ema_20)
            avg_volume = np.mean([c['volume'] for c in candles[-20:]])
            current_volume = candles[-1]['volume']
            atr = self._calculate_atr(candles, 14)
            intraday_high = max([c['high'] for c in candles])
            intraday_low = min([c['low'] for c in candles])
            recent_swing_low = self._find_recent_swing_low(candles, lookback=10)
            
            # LONG entry conditions
            if (regime.is_bullish() and
                current_price > vwap and
                ema_20 > ema_50 and
                current_price > intraday_high * 0.999 and  # Breakout (allow 0.1% tolerance)
                current_volume >= avg_volume * self.min_volume_multiplier):
                
                # Calculate stop loss and target
                stop_loss = max(recent_swing_low, current_price - atr * self.stop_loss_atr_multiplier)
                risk = current_price - stop_loss
                target = current_price + (risk * self.profit_target_r)
                
                signal = Signal(
                    symbol=symbol,
                    direction=SignalDirection.LONG,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target=target,
                    strategy=self.name,
                    timeframe="5min",
                    metadata={
                        "regime": regime.regime_type,
                        "ema_20": ema_20,
                        "ema_50": ema_50,
                        "vwap": vwap,
                        "atr": atr,
                        "volume_ratio": current_volume / avg_volume,
                        "intraday_high": intraday_high,
                        "expected_r": self.profit_target_r
                    }
                )
                
                logger.info(f"[INTRADAY LONG] {symbol} @ Rs{current_price:.2f}, "
                           f"SL: Rs{stop_loss:.2f}, Target: Rs{target:.2f}, "
                           f"Volume: {current_volume/avg_volume:.1f}x avg")
                
                self.trades_today += 1
                return signal
            
            # SHORT entry conditions (if regime allows)
            if (regime.is_bearish() and
                current_price < vwap and
                ema_20 < ema_50 and
                current_price < intraday_low * 1.001 and
                current_volume >= avg_volume * self.min_volume_multiplier):
                
                recent_swing_high = self._find_recent_swing_high(candles, lookback=10)
                stop_loss = min(recent_swing_high, current_price + atr * self.stop_loss_atr_multiplier)
                risk = stop_loss - current_price
                target = current_price - (risk * self.profit_target_r)
                
                signal = Signal(
                    symbol=symbol,
                    direction=SignalDirection.SHORT,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target=target,
                    strategy=self.name,
                    timeframe="5min",
                    metadata={
                        "regime": regime.regime_type,
                        "ema_20": ema_20,
                        "ema_50": ema_50,
                        "vwap": vwap,
                        "atr": atr,
                        "volume_ratio": current_volume / avg_volume,
                        "intraday_low": intraday_low,
                        "expected_r": self.profit_target_r
                    }
                )
                
                logger.info(f"[INTRADAY SHORT] {symbol} @ Rs{current_price:.2f}, "
                           f"SL: Rs{stop_loss:.2f}, Target: Rs{target:.2f}")
                
                self.trades_today += 1
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"[INTRADAY] Error generating signal for {symbol}: {e}")
            return None
    
    def should_exit(self, position: Dict, current_price: float, current_time: datetime) -> tuple[bool, str]:
        """Check if position should be exited
        
        Returns:
            (should_exit, reason)
        """
        # EOD exit
        if current_time.time() >= self.eod_exit_time:
            return True, "EOD_EXIT"
        
        # Stop loss hit
        if position['direction'] == 'long':
            if current_price <= position['stop_loss']:
                return True, "STOP_LOSS"
            
            # Target hit
            if position.get('target') and current_price >= position['target']:
                return True, "TARGET"
        
        else:  # short
            if current_price >= position['stop_loss']:
                return True, "STOP_LOSS"
            
            if position.get('target') and current_price <= position['target']:
                return True, "TARGET"
        
        # No progress check (for partial exit)
        candles_since_entry = position.get('candles_since_entry', 0)
        if candles_since_entry >= 3:
            entry_price = position['entry_price']
            current_profit = abs(current_price - entry_price) / entry_price
            
            if current_profit < 0.001:  # Less than 0.1% move
                return True, "NO_PROGRESS"
        
        return False, ""
    
    def _is_trading_time(self, current_time: time) -> bool:
        """Check if current time is valid for intraday trading"""
        # Not in first 15 minutes
        if self.no_trade_start <= current_time <= self.no_trade_end:
            return False
        
        # Not after 3:00 PM
        if current_time >= time(15, 0):
            return False
        
        return True
    
    def _is_range_day(self, candles: List[Dict], threshold: float = 0.015) -> bool:
        """Detect if it's a range-bound day
        
        Args:
            candles: Historical candles
            threshold: Range threshold (default 1.5%)
            
        Returns:
            True if range-bound
        """
        if len(candles) < 10:
            return False
        
        high = max([c['high'] for c in candles[-10:]])
        low = min([c['low'] for c in candles[-10:]])
        range_percent = ((high - low) / low) if low > 0 else 0
        
        return range_percent < threshold
    
    def _find_recent_swing_low(self, candles: List[Dict], lookback: int = 10) -> float:
        """Find recent swing low"""
        if len(candles) < lookback:
            return candles[-1]['low']
        
        lows = [c['low'] for c in candles[-lookback:]]
        return min(lows)
    
    def _find_recent_swing_high(self, candles: List[Dict], lookback: int = 10) -> float:
        """Find recent swing high"""
        if len(candles) < lookback:
            return candles[-1]['high']
        
        highs = [c['high'] for c in candles[-lookback:]]
        return max(highs)
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return np.mean(prices)
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """Calculate ATR"""
        if len(candles) < period + 1:
            highs = [c['high'] for c in candles]
            lows = [c['low'] for c in candles]
            return np.mean(np.array(highs) - np.array(lows))
        
        tr = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']
            
            tr_val = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr.append(tr_val)
        
        return np.mean(tr[-period:])


logger.info("Intraday strategy initialized")
