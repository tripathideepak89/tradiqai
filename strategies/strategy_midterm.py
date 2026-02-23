"""Mid-Term Trend Trading Strategy (30% Allocation)
===================================================

Objective: Capture structural trend moves over 1-6 months
Expected Return: 30% annually
Max Drawdown: 12%
Holding Period: 1-6 Months

ENTRY CONDITIONS (LONG):
- Price > 50DMA AND > 200DMA
- 50DMA > 200DMA (golden cross context)
- Earnings growth last 2 quarters > 0
- Revenue growth positive
- ROE >= 15%
- Breakout above recent range

RISK RULES:
- Risk per trade: 2% of midterm capital
- Max positions: 3
- Stop loss: Weekly low OR 20DMA

EXIT RULES:
- Weekly close below 20DMA
- Earnings disappointment (reduce 50%)
- 3 months passed AND momentum weak
- Fundamental deterioration
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


class MidTermStrategy(BaseStrategy):
    """Mid-term trend trading strategy"""
    
    def __init__(self, broker: BaseBroker, regime_detector: RegimeDetector):
        super().__init__("midterm")
        self.broker = broker
        self.regime_detector = regime_detector
        self.style = TradingStyle.MIDTERM
        
        # Mid-term specific settings
        self.min_roe = 15.0  # Minimum ROE %
        self.profit_target_r = 2.5
        self.stop_loss_type = "20dma_or_weekly_low"
        self.max_holding_days = 180  # 6 months
        self.momentum_check_days = 90  # Check momentum after 3 months
        
        # Fundamental thresholds
        self.min_revenue_growth = 0.0  # Positive
        self.min_earnings_growth = 0.0  # Positive
        
        # Position tracking
        self.open_positions: Dict[str, Dict] = {}
    
    async def generate_signal(self, symbol: str, market_data: Dict) -> Optional[Signal]:
        """Generate mid-term signal for a symbol
        
        Args:
            symbol: Stock symbol
            market_data: Dict with 'daily_candles', 'weekly_candles', 'quote', 'fundamentals'
            
        Returns:
            Signal or None
        """
        try:
            # Get candles
            daily_candles = market_data.get('daily_candles', [])
            weekly_candles = market_data.get('weekly_candles', [])
            
            if len(daily_candles) < 200 or len(weekly_candles) < 20:
                return None
            
            quote = market_data.get('quote')
            if not quote:
                return None
            
            current_price = quote.get('ltp', 0)
            if current_price == 0:
                return None
            
            # Get weekly regime for mid-term view
            regime = await self.regime_detector.get_regime("NIFTY50", "weekly")
            if not regime:
                logger.warning("[MIDTERM] Could not determine market regime")
                return None
            
            # Mid-term requires strong trend
            if regime.is_ranging() or regime.is_high_volatility():
                logger.debug(f"[MIDTERM] Regime not suitable: {regime.regime_type}")
                return None
            
            # Check fundamentals
            fundamentals = market_data.get('fundamentals', {})
            if not self._check_fundamentals(symbol, fundamentals):
                return None
            
            # Calculate technical indicators
            daily_closes = np.array([c['close'] for c in daily_candles])
            daily_highs = np.array([c['high'] for c in daily_candles])
            daily_lows = np.array([c['low'] for c in daily_candles])
            
            weekly_lows = np.array([c['low'] for c in weekly_candles])
            
            dma_50 = self._calculate_sma(daily_closes, 50)
            dma_200 = self._calculate_sma(daily_closes, 200)
            dma_20 = self._calculate_sma(daily_closes, 20)
            
            # Check for breakout above recent range (60-day high)
            sixty_day_high = np.max(daily_highs[-60:])
            four_week_low = np.min(weekly_lows[-4:])
            
            # LONG entry conditions
            if (regime.is_bullish() and
                current_price > dma_50 and
                current_price > dma_200 and
                dma_50 > dma_200 and
                current_price >= sixty_day_high * 0.995):  # Near breakout
                
                # Calculate stop loss (weekly low)
                stop_loss = max(four_week_low, dma_20 * 0.95)  # Don't set too tight
                
                risk = current_price - stop_loss
                target = current_price + (risk * self.profit_target_r)
                
                signal = Signal(
                    symbol=symbol,
                    direction=SignalDirection.LONG,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target=target,
                    strategy=self.name,
                    timeframe="weekly",
                    metadata={
                        "regime": regime.regime_type,
                        "dma_50": dma_50,
                        "dma_200": dma_200,
                        "dma_20": dma_20,
                        "roe": fundamentals.get('roe', 0),
                        "revenue_growth": fundamentals.get('revenue_growth', 0),
                        "earnings_growth": fundamentals.get('earnings_growth', 0),
                        "sixty_day_high": sixty_day_high,
                        "expected_r": self.profit_target_r,
                        "entry_date": datetime.now().date().isoformat()
                    }
                )
                
                logger.info(f"[MIDTERM LONG] {symbol} @ Rs{current_price:.2f}, "
                           f"SL: Rs{stop_loss:.2f}, Target: Rs{target:.2f}, "
                           f"ROE: {fundamentals.get('roe', 0):.1f}%")
                
                return signal
            
            # SHORT entry (less common for mid-term)
            if (regime.is_bearish() and
                current_price < dma_50 and
                current_price < dma_200 and
                dma_50 < dma_200):
                
                four_week_high = np.max(daily_highs[-20:])
                stop_loss = min(four_week_high, dma_20 * 1.05)
                
                risk = stop_loss - current_price
                target = current_price - (risk * self.profit_target_r)
                
                signal = Signal(
                    symbol=symbol,
                    direction=SignalDirection.SHORT,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target=target,
                    strategy=self.name,
                    timeframe="weekly",
                    metadata={
                        "regime": regime.regime_type,
                        "dma_50": dma_50,
                        "dma_200": dma_200,
                        "expected_r": self.profit_target_r,
                        "entry_date": datetime.now().date().isoformat()
                    }
                )
                
                logger.info(f"[MIDTERM SHORT] {symbol} @ Rs{current_price:.2f}, "
                           f"SL: Rs{stop_loss:.2f}, Target: Rs{target:.2f}")
                
                return signal
            
            return None
            
        except Exception as e:
            logger.error(f"[MIDTERM] Error generating signal for {symbol}: {e}")
            return None
    
    async def should_exit(
        self, 
        position: Dict, 
        current_price: float, 
        current_time: datetime,
        market_data: Dict
    ) -> tuple[bool, str]:
        """Check if mid-term position should be exited
        
        Returns:
            (should_exit, reason)
        """
        symbol = position['symbol']
        direction = position['direction']
        entry_date = datetime.fromisoformat(position['metadata']['entry_date'])
        holding_days = (datetime.now().date() - entry_date.date()).days
        
        # Max holding period
        if holding_days > self.max_holding_days:
            return True, "MAX_HOLDING_PERIOD"
        
        # Get weekly candles
        weekly_candles = market_data.get('weekly_candles', [])
        daily_candles = market_data.get('daily_candles', [])
        
        # Calculate 20DMA
        if len(daily_candles) >= 20:
            closes = np.array([c['close'] for c in daily_candles])
            dma_20 = self._calculate_sma(closes, 20)
            
            # Exit if weekly close below 20DMA (for long)
            if direction == 'long' and len(weekly_candles) > 0:
                last_weekly_close = weekly_candles[-1]['close']
                if last_weekly_close < dma_20:
                    return True, "WEEKLY_CLOSE_BELOW_20DMA"
            
            # Exit if weekly close above 20DMA (for short)
            if direction == 'short' and len(weekly_candles) > 0:
                last_weekly_close = weekly_candles[-1]['close']
                if last_weekly_close > dma_20:
                    return True, "WEEKLY_CLOSE_ABOVE_20DMA"
        
        # Stop loss
        if direction == 'long':
            if current_price <= position['stop_loss']:
                return True, "STOP_LOSS"
            
            if position.get('target') and current_price >= position['target']:
                return True, "TARGET"
        else:
            if current_price >= position['stop_loss']:
                return True, "STOP_LOSS"
            
            if position.get('target') and current_price <= position['target']:
                return True, "TARGET"
        
        # Momentum check after 3 months
        if holding_days >= self.momentum_check_days:
            entry_price = position['entry_price']
            momentum = ((current_price - entry_price) / entry_price) * 100
            
            if direction == 'long' and momentum < 5.0:  # Less than 5% gain in 3 months
                return True, "WEAK_MOMENTUM"
            elif direction == 'short' and momentum > -5.0:
                return True, "WEAK_MOMENTUM"
        
        # Check for earnings disappointment (would need fundamental data)
        fundamentals = market_data.get('fundamentals', {})
        if fundamentals:
            earnings_growth = fundamentals.get('earnings_growth', 100)  # Default high
            if earnings_growth < -10:  # Earnings dropped > 10%
                return True, "EARNINGS_DISAPPOINTMENT"
        
        return False, ""
    
    def _check_fundamentals(self, symbol: str, fundamentals: Dict) -> bool:
        """Check if fundamentals meet criteria
        
        Returns:
            True if fundamentals pass
        """
        if not fundamentals:
            # If no fundamental data, skip this stock
            logger.debug(f"[MIDTERM] {symbol} - No fundamental data available")
            return False
        
        roe = fundamentals.get('roe', 0)
        revenue_growth = fundamentals.get('revenue_growth', -100)
        earnings_growth = fundamentals.get('earnings_growth', -100)
        
        if roe < self.min_roe:
            logger.debug(f"[MIDTERM] {symbol} - ROE {roe:.1f}% < {self.min_roe}%")
            return False
        
        if revenue_growth < self.min_revenue_growth:
            logger.debug(f"[MIDTERM] {symbol} - Revenue growth {revenue_growth:.1f}% negative")
            return False
        
        if earnings_growth < self.min_earnings_growth:
            logger.debug(f"[MIDTERM] {symbol} - Earnings growth {earnings_growth:.1f}% negative")
            return False
        
        logger.debug(f"[MIDTERM] {symbol} - Fundamentals pass: "
                    f"ROE {roe:.1f}%, Rev {revenue_growth:+.1f}%, EPS {earnings_growth:+.1f}%")
        return True
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return float(np.mean(prices))
        return float(np.mean(prices[-period:]))


logger.info("Mid-term strategy initialized")
