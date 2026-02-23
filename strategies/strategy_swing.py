"""Short-Term Swing Trading Strategy (30% Allocation)
====================================================

Objective: Capture momentum moves over 3-10 days
Expected Return: 25% annually
Max Drawdown: 10%
Holding Period: 3-10 Days

ENTRY CONDITIONS (LONG):
- Price > 50DMA
- 20DMA > 50DMA
- Breakout above 10-day high
- Volume >= 1.5x average
- Relative strength vs NIFTY > 0
- Market regime == TREND_UP

RISK RULES:
- Risk per trade: 1.5% of swing capital
- Max positions: 3
- Stop loss: Lowest low of last 5 days OR 1.5xATR

EXIT RULES:
- Close below 20DMA
- Price reaches 2R (start trailing to 20DMA)
- Holding days > 10
- Regime changes to RANGE or high volatility
"""
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import numpy as np

from strategies.base import BaseStrategy, Signal, SignalDirection
from trading_styles import TradingStyle
from regime_detector import RegimeDetector
from brokers.base import BaseBroker

logger = logging.getLogger(__name__)


class SwingStrategy(BaseStrategy):
    """Short-term swing trading strategy"""
    
    def __init__(self, broker: BaseBroker, regime_detector: RegimeDetector):
        super().__init__("swing")
        self.broker = broker
        self.regime_detector = regime_detector
        self.style = TradingStyle.SWING
        
        # Swing-specific settings
        self.min_volume_multiplier = 1.5
        self.profit_target_r = 2.0
        self.stop_loss_atr_multiplier = 1.5
        self.max_holding_days = 10
        self.trailing_start_r = 1.5  # Start trailing at 1.5R
        
        # Position tracking
        self.open_positions: Dict[str, Dict] = {}
    
    async def generate_signal(self, symbol: str, market_data: Dict) -> Optional[Signal]:
        """Generate swing signal for a symbol
        
        Args:
            symbol: Stock symbol
            market_data: Dict with 'daily_candles', 'quote'
            
        Returns:
            Signal or None
        """
        try:
            # Get daily candles
            candles = market_data.get('daily_candles', [])
            if len(candles) < 60:  # Need 60 days for indicators
                return None
            
            quote = market_data.get('quote')
            if not quote:
                return None
            
            current_price = quote.get('ltp', 0)
            if current_price == 0:
                return None
            
            # Get market regime (daily timeframe)
            regime = await self.regime_detector.get_regime("NIFTY50", "daily")
            if not regime:
                logger.warning("[SWING] Could not determine market regime")
                return None
            
            # Swing requires trend
            if regime.is_ranging() or regime.is_high_volatility():
                logger.debug(f"[SWING] Regime not suitable: {regime.regime_type}")
                return None
            
            # Calculate indicators
            closes = np.array([c['close'] for c in candles])
            highs = np.array([c['high'] for c in candles])
            lows = np.array([c['low'] for c in candles])
            volumes = np.array([c['volume'] for c in candles])
            
            dma_20 = self._calculate_sma(closes, 20)
            dma_50 = self._calculate_sma(closes, 50)
            atr = self._calculate_atr(highs, lows, closes, 14)
            
            ten_day_high = np.max(highs[-10:])
            five_day_low = np.min(lows[-5:])
            
            avg_volume = np.mean(volumes[-20:])
            current_volume = volumes[-1]
            
            # Calculate relative strength vs NIFTY
            nifty_regime = regime
            relative_strength = self._calculate_relative_strength(candles, nifty_regime)
            
            # LONG entry conditions
            if (regime.is_bullish() and
                current_price > dma_50 and
                dma_20 > dma_50 and
                current_price >= ten_day_high * 0.998 and  # Breakout
                current_volume >= avg_volume * self.min_volume_multiplier and
                relative_strength > 0):
                
                # Calculate stop loss and target
                stop_loss_1 = five_day_low
                stop_loss_2 = current_price - (atr * self.stop_loss_atr_multiplier)
                stop_loss = max(stop_loss_1, stop_loss_2)  # Use tighter stop
                
                risk = current_price - stop_loss
                target = current_price + (risk * self.profit_target_r)
                
                signal = Signal(
                    symbol=symbol,
                    direction=SignalDirection.LONG,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target=target,
                    strategy=self.name,
                    timeframe="daily",
                    metadata={
                        "regime": regime.regime_type,
                        "dma_20": dma_20,
                        "dma_50": dma_50,
                        "atr": atr,
                        "volume_ratio": current_volume / avg_volume,
                        "relative_strength": relative_strength,
                        "ten_day_high": ten_day_high,
                        "expected_r": self.profit_target_r,
                        "entry_date": datetime.now().date().isoformat()
                    }
                )
                
                logger.info(f"[SWING LONG] {symbol} @ Rs{current_price:.2f}, "
                           f"SL: Rs{stop_loss:.2f}, Target: Rs{target:.2f}, "
                           f"RS: {relative_strength:+.2f}")
                
                return signal
            
            # SHORT entry conditions
            if (regime.is_bearish() and
                current_price < dma_50 and
                dma_20 < dma_50 and
                current_price <= np.min(lows[-10:]) * 1.002 and
                current_volume >= avg_volume * self.min_volume_multiplier and
                relative_strength < 0):
                
                five_day_high = np.max(highs[-5:])
                stop_loss_1 = five_day_high
                stop_loss_2 = current_price + (atr * self.stop_loss_atr_multiplier)
                stop_loss = min(stop_loss_1, stop_loss_2)
                
                risk = stop_loss - current_price
                target = current_price - (risk * self.profit_target_r)
                
                signal = Signal(
                    symbol=symbol,
                    direction=SignalDirection.SHORT,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target=target,
                    strategy=self.name,
                    timeframe="daily",
                    metadata={
                        "regime": regime.regime_type,
                        "dma_20": dma_20,
                        "dma_50": dma_50,
                        "atr": atr,
                        "volume_ratio": current_volume / avg_volume,
                        "relative_strength": relative_strength,
                        "expected_r": self.profit_target_r,
                        "entry_date": datetime.now().date().isoformat()
                    }
                )
                
                logger.info(f"[SWING SHORT] {symbol} @ Rs{current_price:.2f}, "
                           f"SL: Rs{stop_loss:.2f}, Target: Rs{target:.2f}")
                
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"[SWING] Error generating signal for {symbol}: {e}")
            return None
    
    async def should_exit(
        self, 
        position: Dict, 
        current_price: float, 
        current_time: datetime,
        market_data: Dict
    ) -> tuple[bool, str]:
        """Check if swing position should be exited
        
        Returns:
            (should_exit, reason)
        """
        symbol = position['symbol']
        direction = position['direction']
        entry_date = datetime.fromisoformat(position['metadata']['entry_date'])
        holding_days = (datetime.now().date() - entry_date.date()).days
        
        # Max holding period
        if holding_days > self.max_holding_days:
            return True, "MAX_HOLDING_DAYS"
        
        # Get daily candles for DMA calculation
        candles = market_data.get('daily_candles', [])
        if len(candles) >= 20:
            closes = np.array([c['close'] for c in candles])
            dma_20 = self._calculate_sma(closes, 20)
            
            # Exit if close below 20DMA (for long)
            if direction == 'long' and current_price < dma_20:
                return True, "BELOW_20DMA"
            
            # Exit if close above 20DMA (for short)
            if direction == 'short' and current_price > dma_20:
                return True, "ABOVE_20DMA"
        
        # Stop loss check
        if direction == 'long':
            if current_price <= position['stop_loss']:
                return True, "STOP_LOSS"
            
            # Target reached
            if position.get('target') and current_price >= position['target']:
                return True, "TARGET"
            
            # Trailing stop logic
            entry_price = position['entry_price']
            risk = entry_price - position['stop_loss']
            profit = current_price - entry_price
            r_multiple = profit / risk if risk > 0 else 0
            
            if r_multiple >= self.trailing_start_r:
                # Trail to 20DMA if available
                if len(candles) >= 20:
                    trailing_stop = dma_20
                    if current_price < trailing_stop:
                        return True, "TRAILING_STOP"
        
        else:  # short
            if current_price >= position['stop_loss']:
                return True, "STOP_LOSS"
            
            if position.get('target') and current_price <= position['target']:
                return True, "TARGET"
            
            entry_price = position['entry_price']
            risk = position['stop_loss'] - entry_price
            profit = entry_price - current_price
            r_multiple = profit / risk if risk > 0 else 0
            
            if r_multiple >= self.trailing_start_r:
                if len(candles) >= 20:
                    trailing_stop = dma_20
                    if current_price > trailing_stop:
                        return True, "TRAILING_STOP"
        
        # Check regime change
        regime = await self.regime_detector.get_regime("NIFTY50", "daily")
        if regime and (regime.is_ranging() or regime.is_high_volatility()):
            return True, "REGIME_CHANGE"
        
        return False, ""
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return float(np.mean(prices))
        return float(np.mean(prices[-period:]))
    
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
        
        tr = []
        for i in range(1, len(closes)):
            tr_val = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr.append(tr_val)
        
        return float(np.mean(tr[-period:]))
    
    def _calculate_relative_strength(
        self, 
        stock_candles: List[Dict], 
        nifty_regime: object
    ) -> float:
        """Calculate relative strength vs NIFTY
        
        Returns:
            Positive = outperforming, Negative = underperforming
        """
        if len(stock_candles) < 20:
            return 0.0
        
        # Simple RS: stock return vs index return over last 10 days
        stock_start = stock_candles[-10]['close']
        stock_end = stock_candles[-1]['close']
        stock_return = ((stock_end - stock_start) / stock_start) * 100 if stock_start > 0 else 0
        
        # Assume NIFTY return from regime slope
        # Simplified: use EMA separation as proxy
        nifty_strength = ((nifty_regime.ema_20 - nifty_regime.ema_50) / nifty_regime.ema_50) * 100 if nifty_regime.ema_50 > 0 else 0
        
        return stock_return - nifty_strength


logger.info("Swing strategy initialized")
