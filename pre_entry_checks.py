"""
Pre-Entry Checklist - Professional Trading Discipline
Before any entry, AI must answer these questions and log them.
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, time
from dataclasses import dataclass
from utils.timezone import now_ist
logger = logging.getLogger(__name__)


@dataclass
class PreEntryAnalysis:
    """Pre-entry analysis results"""
    # Questions
    nifty_regime: str  # "trending_up", "trending_down", "flat", "volatile"
    entry_timing: str  # "first_breakout", "second_breakout", "late_entry", "chase"
    volume_status: str  # "above_average", "average", "below_average"
    extension_status: str  # "not_extended", "moderately_extended", "highly_extended"
    risk_reward: float  # Actual R:R ratio
    nearest_resistance: float  # Price level
    resistance_distance_pct: float  # Distance to resistance in %
    
    # Day type
    day_type: str  # "trending", "range", "volatile"
    
    # Decision
    should_enter: bool
    rejection_reason: str = ""
    
    def log_analysis(self, symbol: str, entry_price: float):
        """Log complete pre-entry analysis"""
        logger.info("=" * 80)
        logger.info(f"📋 PRE-ENTRY CHECKLIST FOR {symbol} @ Rs{entry_price:.2f}")
        logger.info("=" * 80)
        logger.info(f"❓ Was NIFTY trending or flat? → {self.nifty_regime.upper()}")
        logger.info(f"❓ Was this first breakout or late entry? → {self.entry_timing.upper()}")
        logger.info(f"❓ Was volume above average? → {self.volume_status.upper()}")
        logger.info(f"❓ Was stock extended already? → {self.extension_status.upper()}")
        logger.info(f"❓ Was reward at least 1.5R? → {self.risk_reward:.2f}:1 {'✅' if self.risk_reward >= 1.5 else '❌'}")
        logger.info(f"❓ Where was nearest resistance? → Rs{self.nearest_resistance:.2f} ({self.resistance_distance_pct:+.2f}%)")
        logger.info(f"📊 Day Type: {self.day_type.upper()}")
        logger.info(f"🎯 Decision: {'✅ ENTER' if self.should_enter else '❌ REJECT - ' + self.rejection_reason}")
        logger.info("=" * 80)


class PreEntryChecker:
    """Performs comprehensive pre-entry checks"""
    
    def __init__(self, broker):
        self.broker = broker
        self._market_open = time(9, 15)
        self._first_hour_end = time(10, 15)
        self._lunch_start = time(12, 0)
        self._power_hour = time(14, 0)
    
    async def check_entry_conditions(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        target: float,
        quote: Dict
    ) -> PreEntryAnalysis:
        """Run complete pre-entry checklist"""
        
        # 1. Check NIFTY regime
        nifty_regime = await self._check_nifty_regime()
        
        # 2. Check entry timing
        entry_timing = self._check_entry_timing(quote, entry_price)
        
        # 3. Check volume
        volume_status = self._check_volume(quote)
        
        # 4. Check if stock is extended
        extension_status = self._check_extension(quote, entry_price)
        
        # 5. Calculate R:R
        risk = entry_price - stop_loss
        reward = target - entry_price
        risk_reward = reward / risk if risk > 0 else 0
        
        # 6. Find nearest resistance
        nearest_resistance, resistance_distance_pct = self._find_nearest_resistance(quote, entry_price)
        
        # 7. Determine day type
        day_type = await self._detect_day_type()
        
        # 8. Make decision
        should_enter, rejection_reason = self._make_entry_decision(
            nifty_regime=nifty_regime,
            entry_timing=entry_timing,
            volume_status=volume_status,
            extension_status=extension_status,
            risk_reward=risk_reward,
            resistance_distance_pct=resistance_distance_pct,
            day_type=day_type
        )
        
        analysis = PreEntryAnalysis(
            nifty_regime=nifty_regime,
            entry_timing=entry_timing,
            volume_status=volume_status,
            extension_status=extension_status,
            risk_reward=risk_reward,
            nearest_resistance=nearest_resistance,
            resistance_distance_pct=resistance_distance_pct,
            day_type=day_type,
            should_enter=should_enter,
            rejection_reason=rejection_reason
        )
        
        # Log it
        analysis.log_analysis(symbol, entry_price)
        
        return analysis
    
    async def _check_nifty_regime(self) -> str:
        """Check if NIFTY is trending or flat"""
        try:
            # Get NIFTY 50 candles (15-min, last 2 hours = 8 candles)
            nifty_candles = await self.broker.get_historical_candles(
                "NIFTY 50",
                interval="15minute",
                from_date=datetime.now().replace(hour=9, minute=15),
                to_date=datetime.now()
            )
            
            if not nifty_candles or len(nifty_candles) < 4:
                return "unknown"
            
            # Calculate ATR and range
            highs = [c['high'] for c in nifty_candles]
            lows = [c['low'] for c in nifty_candles]
            closes = [c['close'] for c in nifty_candles]
            
            current_price = closes[-1]
            open_price = nifty_candles[0]['open']
            
            # Range since market open
            day_range = (max(highs) - min(lows)) / open_price * 100
            
            # Direction
            move_pct = (current_price - open_price) / open_price * 100
            
            # Classification
            if day_range < 0.6:  # NIFTY moved less than 0.6%
                return "flat"
            elif abs(move_pct) > 0.8 and day_range > 1.0:  # Strong directional move
                return "trending_up" if move_pct > 0 else "trending_down"
            elif day_range > 1.5:  # High range but no direction
                return "volatile"
            else:
                return "flat"
                
        except Exception as e:
            logger.error(f"Error checking NIFTY regime: {e}")
            return "unknown"
    
    def _check_entry_timing(self, quote: Dict, entry_price: float) -> str:
        """Check if this is first breakout or late entry"""
        try:
            high = quote.get('high', entry_price)
            open_price = quote.get('open', entry_price)
            
            # How much has stock already moved?
            move_from_open = (high - open_price) / open_price * 100
            current_from_high = (entry_price - high) / high * 100
            
            now = now_ist().time()
            
            # First breakout: Within first 45 min, near high
            if now < self._first_hour_end and current_from_high > -0.5:
                return "first_breakout"
            
            # Second breakout: After pullback, new high
            elif current_from_high > -0.3 and move_from_open > 1.5:
                return "second_breakout"
            
            # Late entry: Stock already moved 3%+
            elif move_from_open > 3.0:
                return "late_entry"
            
            # Chasing: Stock pulled back significantly
            elif current_from_high < -1.0:
                return "chase"
            
            return "normal"
            
        except Exception as e:
            logger.error(f"Error checking entry timing: {e}")
            return "unknown"
    
    def _check_volume(self, quote: Dict) -> str:
        """Check if volume is above average"""
        # Note: This is simplified - ideally compare with 20-day avg volume
        volume = quote.get('volume', 0)
        
        # Heuristic: High volume if > usual for this time
        # This would need historical data for proper implementation
        return "above_average" if volume > 0 else "unknown"
    
    def _check_extension(self, quote: Dict, entry_price: float) -> str:
        """Check if stock is already extended"""
        try:
            open_price = quote.get('open', entry_price)
            low = quote.get('low', entry_price)
            high = quote.get('high', entry_price)
            
            # Calculate extension from open
            move_pct = (entry_price - open_price) / open_price * 100
            
            # Calculate position in day's range
            day_range = high - low
            if day_range > 0:
                position_in_range = (entry_price - low) / day_range
            else:
                position_in_range = 0.5
            
            # Classification
            if move_pct < 1.5 and position_in_range < 0.7:
                return "not_extended"
            elif move_pct < 3.0 and position_in_range < 0.85:
                return "moderately_extended"
            else:
                return "highly_extended"
                
        except Exception as e:
            logger.error(f"Error checking extension: {e}")
            return "unknown"
    
    def _find_nearest_resistance(self, quote: Dict, entry_price: float) -> Tuple[float, float]:
        """Find nearest resistance level"""
        try:
            high = quote.get('high', entry_price)
            
            # Simplified: Use day's high as resistance
            # In production, use pivot points, prior day's levels, etc.
            resistance = high
            
            # If already at high, project next level (+1%)
            if abs(entry_price - high) / entry_price < 0.002:  # Within 0.2%
                resistance = high * 1.01
            
            distance_pct = (resistance - entry_price) / entry_price * 100
            
            return resistance, distance_pct
            
        except Exception as e:
            logger.error(f"Error finding resistance: {e}")
            return entry_price * 1.02, 2.0
    
    async def _detect_day_type(self) -> str:
        """Detect if today is trending or range day"""
        try:
            # Get NIFTY data
            nifty_candles = await self.broker.get_historical_candles(
                "NIFTY 50",
                interval="15minute",
                from_date=datetime.now().replace(hour=9, minute=15),
                to_date=datetime.now()
            )
            
            if not nifty_candles or len(nifty_candles) < 3:
                return "unknown"
            
            opens = [c['open'] for c in nifty_candles]
            highs = [c['high'] for c in nifty_candles]
            lows = [c['low'] for c in nifty_candles]
            closes = [c['close'] for c in nifty_candles]
            
            # First 45 min range
            first_45_min = nifty_candles[:3]  # 3 x 15min = 45 min
            first_range = (max([c['high'] for c in first_45_min]) - 
                          min([c['low'] for c in first_45_min]))
            first_range_pct = first_range / first_45_min[0]['open'] * 100
            
            # Current position vs range
            current_high = max(highs)
            current_low = min(lows)
            total_range_pct = (current_high - current_low) / opens[0] * 100
            
            # Classification
            if first_range_pct < 0.6 and total_range_pct < 1.0:
                # Low volatility, small range = RANGE DAY
                return "range"
            elif total_range_pct > 1.5 and abs(closes[-1] - opens[0]) / opens[0] * 100 > 0.8:
                # High range with direction = TRENDING DAY
                return "trending"
            elif total_range_pct > 1.5:
                # High range but no direction = VOLATILE
                return "volatile"
            else:
                return "range"
                
        except Exception as e:
            logger.error(f"Error detecting day type: {e}")
            return "unknown"
    
    def _make_entry_decision(
        self,
        nifty_regime: str,
        entry_timing: str,
        volume_status: str,
        extension_status: str,
        risk_reward: float,
        resistance_distance_pct: float,
        day_type: str
    ) -> Tuple[bool, str]:
        """Make final entry decision based on all checks"""
        
        # Critical filters - must pass
        if risk_reward < 1.5:
            return False, f"R:R too low ({risk_reward:.2f}:1, need >= 1.5:1)"
        
        if nifty_regime == "flat" and day_type == "range":
            return False, "NIFTY flat + Range day = low probability"
        
        if extension_status == "highly_extended":
            return False, "Stock already extended, risk of pullback"
        
        if entry_timing == "chase":
            return False, "Chasing pullback from high - bad entry"
        
        if entry_timing == "late_entry" and resistance_distance_pct < 1.0:
            return False, "Late entry with resistance nearby"
        
        # Warning filters - can proceed but with caution
        warnings = []
        
        if volume_status == "below_average":
            warnings.append("Low volume")
        
        if nifty_regime == "volatile":
            warnings.append("NIFTY volatile")
        
        if entry_timing == "late_entry":
            warnings.append("Late entry")
        
        if warnings:
            logger.warning(f"⚠️ Proceeding with warnings: {', '.join(warnings)}")
        
        return True, ""
