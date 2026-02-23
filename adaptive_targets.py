"""
Adaptive Target System - Dynamic exit targets based on market structure
Replaces fixed targets with intelligent, structure-based exits
"""
import logging
from typing import Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class AdaptiveTargetSystem:
    """Calculate dynamic targets based on market conditions"""
    
    def __init__(self, broker):
        self.broker = broker
    
    def calculate_adaptive_target(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        quote: Dict,
        day_type: str,
        resistance: float
    ) -> Tuple[float, str]:
        """
        Calculate adaptive target based on:
        - Day type (trending vs range)
        - Structure (resistance levels)
        - ATR
        - Percentage cap (realistic intraday moves)
        
        Returns:
            (target_price, target_type)
        """
        
        risk = entry_price - stop_loss
        
        # Option A: Structure-based target
        structure_target = self._structure_based_target(
            entry_price, resistance, risk
        )
        
        # Option B: Day-type based target
        day_type_target = self._day_type_based_target(
            entry_price, risk, day_type
        )
        
        # Option C: ATR-based target
        atr = quote.get('high', entry_price) - quote.get('low', entry_price)
        atr_target = entry_price + (atr * 1.5)
        
        # Apply percentage caps based on realistic intraday moves
        # Normal intraday: 1.5% to 3.5% (unless rally)
        max_pct = self._get_max_target_percentage(day_type)
        percentage_cap = entry_price * (1 + max_pct / 100)
        
        # Choose the most conservative (closest) target
        candidates = [
            (structure_target, "structure"),
            (day_type_target, f"day_type_{day_type}"),
            (atr_target, "atr_1.5x"),
            (percentage_cap, f"pct_cap_{max_pct}%")
        ]
        
        # Filter valid targets (must be at least 1.5R)
        min_target = entry_price + (risk * 1.5)
        valid_targets = [(t, name) for t, name in candidates if t >= min_target]
        
        if not valid_targets:
            # If none meet 1.5R, check if percentage cap meets 1.5R
            if percentage_cap >= min_target:
                logger.info(f"{symbol}: Using percentage cap as minimum target")
                return percentage_cap, f"pct_cap_{max_pct}%"
            else:
                # Use minimum 1.5R but warn
                logger.warning(f"{symbol}: All targets below 1.5R, using minimum")
                return min_target, "minimum_1.5R"
        
        # Choose most conservative valid target
        target, target_name = min(valid_targets, key=lambda x: x[0])
        
        r_multiple = (target - entry_price) / risk
        target_pct = (target - entry_price) / entry_price * 100
        
        logger.info(
            f"📊 {symbol} Adaptive Target: Rs{target:.2f} "
            f"({r_multiple:.2f}R, +{target_pct:.1f}%, {target_name})"
        )
        
        return target, target_name
    
    def _get_max_target_percentage(self, day_type: str) -> float:
        """
        Get maximum realistic target percentage based on day type
        
        Normal intraday moves: 1.5% to 3.5%
        Only aim for 4%+ on trending/rally days
        """
        if day_type == "trending":
            return 3.5  # Allow higher targets on trending days
        elif day_type == "range":
            return 2.5  # Conservative on range days
        elif day_type == "volatile":
            return 3.0  # Medium on volatile days
        else:
            return 2.5  # Default conservative
    
    def _structure_based_target(
        self,
        entry_price: float,
        resistance: float,
        risk: float
    ) -> float:
        """Target = nearest resistance level (or before it)"""
        
        # If resistance is close (< 1R), don't aim for it
        # Target slightly before resistance to avoid rejection
        distance_to_resistance = resistance - entry_price
        
        if distance_to_resistance < risk * 1.5:
            # Resistance too close, target before it
            return entry_price + (distance_to_resistance * 0.8)
        else:
            # Resistance far enough, aim for it
            return resistance * 0.99  # Slightly before resistance
    
    def _day_type_based_target(
        self,
        entry_price: float,
        risk: float,
        day_type: str
    ) -> float:
        """
        Target based on day regime
        
        Adjusted for realistic intraday moves (1.5% to 3.5%)
        """
        
        if day_type == "trending":
            # Trending day: Aim for 2R (but capped by percentage)
            return entry_price + (risk * 2.0)
        
        elif day_type == "range":
            # Range day: Conservative 1.5R target
            return entry_price + (risk * 1.5)
        
        elif day_type == "volatile":
            # Volatile day: Medium 1.75R
            return entry_price + (risk * 1.75)
        
        else:
            # Unknown: Default 1.5R
            return entry_price + (risk * 1.5)
    
    def should_trail_stop(
        self,
        entry_price: float,
        stop_loss: float,
        current_price: float,
        target: float
    ) -> Tuple[bool, float]:
        """
        Determine if stop should be trailed
        
        Rules:
        - Once price moves 0.5R, move stop to breakeven
        - Once price moves 1R, trail at 0.5R
        
        Returns:
            (should_trail, new_stop_price)
        """
        
        risk = entry_price - stop_loss
        gain = current_price - entry_price
        r_multiple = gain / risk if risk > 0 else 0
        
        if r_multiple >= 1.0:
            # Move to 0.5R profit
            new_stop = entry_price + (risk * 0.5)
            logger.info(
                f"🔄 Trail stop to +0.5R (Rs{new_stop:.2f}) "
                f"as price reached 1R"
            )
            return True, new_stop
        
        elif r_multiple >= 0.5:
            # Move to breakeven
            logger.info(
                f"🔄 Trail stop to breakeven (Rs{entry_price:.2f}) "
                f"as price reached 0.5R"
            )
            return True, entry_price
        
        return False, stop_loss


class TimeBasedExit:
    """Time-based exit rules"""
    
    @staticmethod
    def should_exit_on_time(
        entry_time: datetime,
        current_price: float,
        entry_price: float,
        candles_since_entry: int = 0
    ) -> Tuple[bool, str]:
        """
        Exit if trade not moving within 3 candles (15-min basis)
        
        Dead trades kill capital efficiency
        """
        
        # Rule 1: If 3 candles passed (45 min) and price hasn't moved 0.3%
        if candles_since_entry >= 3:
            move_pct = abs(current_price - entry_price) / entry_price * 100
            
            if move_pct < 0.3:
                return True, "Dead trade - no movement in 45 min"
        
        # Rule 2: End of day exit (3:20 PM IST)
        from utils.timezone import now_ist
        now = now_ist()
        if now.hour == 15 and now.minute >= 20:
            return True, "EOD exit"
        
        return False, ""


class VWAPBias:
    """VWAP-based bias rules"""
    
    @staticmethod
    def check_vwap_bias(
        current_price: float,
        vwap: float,
        action: str
    ) -> Tuple[bool, str]:
        """
        Only go long above VWAP
        Only short below VWAP
        
        Simple but powerful filter
        """
        
        if action == "BUY" and current_price < vwap:
            return False, f"Long rejected - price (Rs{current_price:.2f}) below VWAP (Rs{vwap:.2f})"
        
        elif action == "SELL" and current_price > vwap:
            return False, f"Short rejected - price (Rs{current_price:.2f}) above VWAP (Rs{vwap:.2f})"
        
        return True, ""
    
    @staticmethod
    def calculate_vwap(candles: list) -> float:
        """Calculate VWAP from candles"""
        try:
            if not candles:
                return 0
            
            total_volume = 0
            total_pv = 0
            
            for candle in candles:
                typical_price = (
                    candle['high'] + 
                    candle['low'] + 
                    candle['close']
                ) / 3
                volume = candle.get('volume', 0)
                
                total_pv += typical_price * volume
                total_volume += volume
            
            if total_volume == 0:
                return candles[-1]['close']
            
            return total_pv / total_volume
            
        except Exception as e:
            logger.error(f"Error calculating VWAP: {e}")
            return 0
