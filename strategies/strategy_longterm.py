"""Long-Term Position Trading Strategy (20% Allocation)
=======================================================

Objective: Compounding engine - hold quality stocks for 1+ years
Expected Return: 18% annually
Max Drawdown: 15%
Holding Period: 1+ Years

ENTRY CONDITIONS:
- Revenue growth 3-year avg > 12%
- Profit growth 3-year avg > 15%
- Debt-to-equity < 1
- ROE >= 18%
- Price > 200DMA
- Strong fundamentals + technical confirmation

RISK RULES:
- Risk per trade: 3% of longterm capital
- Max positions: 3
- Stop loss: 200DMA (4-week close below)

EXIT RULES:
- 2 consecutive quarters negative growth
- Price closes below 200DMA for 4 weeks
- Fundamental deterioration
- Debt/equity ratio exceeds 1.5
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


class LongTermStrategy(BaseStrategy):
    """Long-term position trading strategy"""
    
    def __init__(self, broker: BaseBroker, regime_detector: RegimeDetector):
        super().__init__("longterm")
        self.broker = broker
        self.regime_detector = regime_detector
        self.style = TradingStyle.LONGTERM
        
        # Long-term specific settings
        self.min_roe = 18.0  # Minimum ROE %
        self.min_3yr_revenue_growth = 12.0  # 3-year avg
        self.min_3yr_profit_growth = 15.0  # 3-year avg
        self.max_debt_to_equity = 1.0
        self.profit_target_r = 3.0  # Let winners run
        self.max_holding_days = 730  # 2 years max (then review)
        
        # Exit rules
        self.dma_200_exit_weeks = 4  # Exit if below 200DMA for 4 weeks
        self.consecutive_negative_quarters = 2
        
        # Position tracking
        self.open_positions: Dict[str, Dict] = {}
    
    async def generate_signal(self, symbol: str, market_data: Dict) -> Optional[Signal]:
        """Generate long-term signal for a symbol
        
        Args:
            symbol: Stock symbol
            market_data: Dict with 'daily_candles', 'monthly_candles', 'quote', 'fundamentals'
            
        Returns:
            Signal or None
        """
        try:
            # Get candles
            daily_candles = market_data.get('daily_candles', [])
            monthly_candles = market_data.get('monthly_candles', [])
            
            if len(daily_candles) < 200:  # Need 200 days for 200DMA
                return None
            
            quote = market_data.get('quote')
            if not quote:
                return None
            
            current_price = quote.get('ltp', 0)
            if current_price == 0:
                return None
            
            # Long-term less affected by short-term regime, but avoid high volatility entries
            regime = await self.regime_detector.get_regime("NIFTY50", "weekly")
            if regime and regime.is_high_volatility():
                logger.debug(f"[LONGTERM] High volatility, delaying entry")
                return None
            
            # Check fundamentals (most important for long-term)
            fundamentals = market_data.get('fundamentals', {})
            if not self._check_fundamentals(symbol, fundamentals):
                return None
            
            # Calculate technical indicators
            daily_closes = np.array([c['close'] for c in daily_candles])
            dma_200 = self._calculate_sma(daily_closes, 200)
            
            # Entry condition: Price > 200DMA (long-term uptrend)
            if current_price > dma_200:
                # Calculate stop loss (200DMA or fundamental-based)
                stop_loss = dma_200 * 0.90  # 10% below 200DMA (wide stop)
                
                risk = current_price - stop_loss
                target = current_price + (risk * self.profit_target_r)
                
                signal = Signal(
                    symbol=symbol,
                    direction=SignalDirection.LONG,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    target=target,
                    strategy=self.name,
                    timeframe="monthly",
                    metadata={
                        "dma_200": dma_200,
                        "roe": fundamentals.get('roe', 0),
                        "revenue_growth_3yr": fundamentals.get('revenue_growth_3yr', 0),
                        "profit_growth_3yr": fundamentals.get('profit_growth_3yr', 0),
                        "debt_to_equity": fundamentals.get('debt_to_equity', 0),
                        "market_cap": fundamentals.get('market_cap', 0),
                        "expected_r": self.profit_target_r,
                        "entry_date": datetime.now().date().isoformat(),
                        "quarters_negative": 0  # Track negative quarters
                    }
                )
                
                logger.info(f"[LONGTERM LONG] {symbol} @ Rs{current_price:.2f}, "
                           f"SL: Rs{stop_loss:.2f} (200DMA: Rs{dma_200:.2f}), "
                           f"ROE: {fundamentals.get('roe', 0):.1f}%, "
                           f"3Y Rev Growth: {fundamentals.get('revenue_growth_3yr', 0):+.1f}%")
                
                return signal
            
            else:
                logger.debug(f"[LONGTERM] {symbol} below 200DMA (Rs{current_price:.2f} < Rs{dma_200:.2f})")
                return None
            
        except Exception as e:
            logger.error(f"[LONGTERM] Error generating signal for {symbol}: {e}")
            return None
    
    async def should_exit(
        self, 
        position: Dict, 
        current_price: float, 
        current_time: datetime,
        market_data: Dict
    ) -> tuple[bool, str]:
        """Check if long-term position should be exited
        
        Returns:
            (should_exit, reason)
        """
        symbol = position['symbol']
        entry_date = datetime.fromisoformat(position['metadata']['entry_date'])
        holding_days = (datetime.now().date() - entry_date.date()).days
        
        # Check if fundamentals have deteriorated
        fundamentals = market_data.get('fundamentals', {})
        if fundamentals:
            # Check for fundamental red flags
            if self._check_fundamental_deterioration(symbol, fundamentals, position):
                return True, "FUNDAMENTAL_DETERIORATION"
            
            # Track negative quarters
            current_quarter_growth = fundamentals.get('quarterly_growth', 100)
            quarters_negative = position['metadata'].get('quarters_negative', 0)
            
            if current_quarter_growth < 0:
                quarters_negative += 1
                position['metadata']['quarters_negative'] = quarters_negative
                
                if quarters_negative >= self.consecutive_negative_quarters:
                    return True, "CONSECUTIVE_NEGATIVE_QUARTERS"
            else:
                # Reset counter if positive
                position['metadata']['quarters_negative'] = 0
        
        # Check 200DMA exit rule
        daily_candles = market_data.get('daily_candles', [])
        weekly_candles = market_data.get('weekly_candles', [])
        
        if len(daily_candles) >= 200 and len(weekly_candles) >= 4:
            closes = np.array([c['close'] for c in daily_candles])
            dma_200 = self._calculate_sma(closes, 200)
            
            # Check if closed below 200DMA for last 4 weeks
            last_4_weekly_closes = [c['close'] for c in weekly_candles[-4:]]
            weeks_below_200 = sum(1 for close in last_4_weekly_closes if close < dma_200)
            
            if weeks_below_200 >= self.dma_200_exit_weeks:
                logger.info(f"[LONGTERM] {symbol} closed below 200DMA for {weeks_below_200} weeks")
                return True, "BELOW_200DMA_4_WEEKS"
        
        # Hard stop loss (should rarely hit with 200DMA exit)
        if current_price <= position['stop_loss']:
            return True, "STOP_LOSS"
        
        # Target reached (but long-term holds, so just log)
        if position.get('target') and current_price >= position['target']:
            # Don't exit on target for long-term, let it run
            # Just log the milestone
            logger.info(f"[LONGTERM] {symbol} reached target Rs{position['target']:.2f}, holding for more")
            # Update target to higher level
            position['target'] = current_price * 1.2  # New target 20% higher
        
        # Review at 2 years
        if holding_days >= self.max_holding_days:
            logger.info(f"[LONGTERM] {symbol} held for {holding_days} days, review required")
            # Could implement automatic review logic
            # For now, just log
        
        return False, ""
    
    def _check_fundamentals(self, symbol: str, fundamentals: Dict) -> bool:
        """Check if fundamentals meet long-term investment criteria
        
        Returns:
            True if fundamentals pass
        """
        if not fundamentals:
            logger.debug(f"[LONGTERM] {symbol} - No fundamental data available")
            return False
        
        roe = fundamentals.get('roe', 0)
        revenue_growth_3yr = fundamentals.get('revenue_growth_3yr', -100)
        profit_growth_3yr = fundamentals.get('profit_growth_3yr', -100)
        debt_to_equity = fundamentals.get('debt_to_equity', 999)
        
        # Check all criteria
        checks = []
        
        if roe < self.min_roe:
            logger.debug(f"[LONGTERM] {symbol} - ROE {roe:.1f}% < {self.min_roe}%")
            checks.append(False)
        else:
            checks.append(True)
        
        if revenue_growth_3yr < self.min_3yr_revenue_growth:
            logger.debug(f"[LONGTERM] {symbol} - 3Y Revenue growth {revenue_growth_3yr:.1f}% < {self.min_3yr_revenue_growth}%")
            checks.append(False)
        else:
            checks.append(True)
        
        if profit_growth_3yr < self.min_3yr_profit_growth:
            logger.debug(f"[LONGTERM] {symbol} - 3Y Profit growth {profit_growth_3yr:.1f}% < {self.min_3yr_profit_growth}%")
            checks.append(False)
        else:
            checks.append(True)
        
        if debt_to_equity > self.max_debt_to_equity:
            logger.debug(f"[LONGTERM] {symbol} - Debt/Equity {debt_to_equity:.2f} > {self.max_debt_to_equity}")
            checks.append(False)
        else:
            checks.append(True)
        
        if all(checks):
            logger.info(f"[LONGTERM] {symbol} - Fundamentals pass: "
                       f"ROE {roe:.1f}%, Rev3Y {revenue_growth_3yr:+.1f}%, "
                       f"Profit3Y {profit_growth_3yr:+.1f}%, D/E {debt_to_equity:.2f}")
            return True
        
        return False
    
    def _check_fundamental_deterioration(
        self, 
        symbol: str, 
        fundamentals: Dict, 
        position: Dict
    ) -> bool:
        """Check if fundamentals have deteriorated
        
        Returns:
            True if deterioration detected
        """
        # Get entry fundamentals
        entry_roe = position['metadata'].get('roe', 0)
        entry_debt_equity = position['metadata'].get('debt_to_equity', 0)
        
        # Current fundamentals
        current_roe = fundamentals.get('roe', 0)
        current_debt_equity = fundamentals.get('debt_to_equity', 999)
        
        # Check for significant deterioration
        if current_roe < entry_roe * 0.7:  # ROE dropped > 30%
            logger.warning(f"[LONGTERM] {symbol} - ROE deteriorated: {entry_roe:.1f}% -> {current_roe:.1f}%")
            return True
        
        if current_debt_equity > 1.5:  # Debt levels too high
            logger.warning(f"[LONGTERM] {symbol} - Debt/Equity too high: {current_debt_equity:.2f}")
            return True
        
        return False
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return float(np.mean(prices))
        return float(np.mean(prices[-period:]))


logger.info("Long-term strategy initialized")
