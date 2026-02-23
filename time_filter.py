"""Time Filter Rules - Trade Only During Optimal Windows"""
import logging
from datetime import datetime, time
from typing import Tuple

from utils.timezone import now_ist

logger = logging.getLogger(__name__)


class TimeFilter:
    """Filter trades based on time of day
    
    CORE PRINCIPLE: Avoid noise windows and low liquidity periods
    
    Rules:
    - No trades 09:15 - 09:30 (opening volatility trap)
    - Best window 1: 09:45 - 11:30 (primary session)
    - Best window 2: 13:45 - 14:45 (secondary session)
    - Avoid: 12:00 - 13:15 (lunch, low liquidity)
    - Avoid: After 15:00 (unless closing positions)
    - Flatten all by 15:20 (no overnight intraday)
    """
    
    # Define trading windows
    MARKET_OPEN = time(9, 15)
    AVOID_PERIOD_END = time(9, 30)  # First 15 mins - noise
    
    PRIMARY_WINDOW_START = time(9, 45)
    PRIMARY_WINDOW_END = time(11, 30)
    
    LUNCH_AVOID_START = time(12, 0)
    LUNCH_AVOID_END = time(13, 15)
    
    SECONDARY_WINDOW_START = time(13, 45)
    SECONDARY_WINDOW_END = time(14, 45)
    
    NO_NEW_TRADES_AFTER = time(15, 0)
    FLATTEN_ALL_BY = time(15, 20)
    MARKET_CLOSE = time(15, 30)
    
    @staticmethod
    def is_market_open() -> bool:
        """Check if market is currently open"""
        now = now_ist().time()
        return TimeFilter.MARKET_OPEN <= now <= TimeFilter.MARKET_CLOSE
    
    @staticmethod
    def can_enter_new_trade() -> Tuple[bool, str]:
        """Check if new trades are allowed at current time
        
        Returns:
            (allowed: bool, reason: str)
        """
        now = now_ist().time()
        
        # Market closed
        if not TimeFilter.is_market_open():
            return False, "Market closed"
        
        # Avoid first 15 minutes (09:15 - 09:30)
        if TimeFilter.MARKET_OPEN <= now < TimeFilter.AVOID_PERIOD_END:
            return False, "First 15 mins - opening volatility trap"
        
        # Primary window (09:45 - 11:30) - BEST
        if TimeFilter.PRIMARY_WINDOW_START <= now <= TimeFilter.PRIMARY_WINDOW_END:
            return True, "Primary trading window"
        
        # Lunch period (12:00 - 13:15) - AVOID
        if TimeFilter.LUNCH_AVOID_START <= now < TimeFilter.LUNCH_AVOID_END:
            return False, "Lunch hour - low liquidity"
        
        # Secondary window (13:45 - 14:45) - GOOD
        if TimeFilter.SECONDARY_WINDOW_START <= now <= TimeFilter.SECONDARY_WINDOW_END:
            return True, "Secondary trading window"
        
        # After 15:00 - NO NEW TRADES
        if now >= TimeFilter.NO_NEW_TRADES_AFTER:
            return False, "After 15:00 - only manage existing positions"
        
        # Gap between windows (11:30 - 12:00, 13:15 - 13:45)
        return False, "Outside optimal trading windows"
    
    @staticmethod
    def should_flatten_all() -> bool:
        """Check if all positions should be flattened (end of day)"""
        now = now_ist().time()
        return now >= TimeFilter.FLATTEN_ALL_BY
    
    @staticmethod
    def get_current_window() -> str:
        """Get description of current time window"""
        now = now_ist().time()
        
        if not TimeFilter.is_market_open():
            return "MARKET_CLOSED"
        
        if TimeFilter.MARKET_OPEN <= now < TimeFilter.AVOID_PERIOD_END:
            return "OPENING_VOLATILITY"
        
        if TimeFilter.PRIMARY_WINDOW_START <= now <= TimeFilter.PRIMARY_WINDOW_END:
            return "PRIMARY_WINDOW"
        
        if TimeFilter.LUNCH_AVOID_START <= now < TimeFilter.LUNCH_AVOID_END:
            return "LUNCH_PERIOD"
        
        if TimeFilter.SECONDARY_WINDOW_START <= now <= TimeFilter.SECONDARY_WINDOW_END:
            return "SECONDARY_WINDOW"
        
        if now >= TimeFilter.NO_NEW_TRADES_AFTER:
            return "END_OF_DAY"
        
        return "GAP_PERIOD"
    
    @staticmethod
    def get_next_window_info() -> dict:
        """Get information about next trading window"""
        now = now_ist().time()
        
        if now < TimeFilter.AVOID_PERIOD_END:
            return {
                "next_window": "PRIMARY_WINDOW",
                "starts_at": TimeFilter.PRIMARY_WINDOW_START.strftime("%H:%M"),
                "minutes_until": TimeFilter._minutes_between(now, TimeFilter.PRIMARY_WINDOW_START)
            }
        
        if now < TimeFilter.PRIMARY_WINDOW_START:
            return {
                "next_window": "PRIMARY_WINDOW",
                "starts_at": TimeFilter.PRIMARY_WINDOW_START.strftime("%H:%M"),
                "minutes_until": TimeFilter._minutes_between(now, TimeFilter.PRIMARY_WINDOW_START)
            }
        
        if TimeFilter.PRIMARY_WINDOW_END < now < TimeFilter.SECONDARY_WINDOW_START:
            return {
                "next_window": "SECONDARY_WINDOW",
                "starts_at": TimeFilter.SECONDARY_WINDOW_START.strftime("%H:%M"),
                "minutes_until": TimeFilter._minutes_between(now, TimeFilter.SECONDARY_WINDOW_START)
            }
        
        return {
            "next_window": "NONE_TODAY",
            "starts_at": "NEXT_DAY",
            "minutes_until": -1
        }
    
    @staticmethod
    def _minutes_between(time1: time, time2: time) -> int:
        """Calculate minutes between two times"""
        t1_minutes = time1.hour * 60 + time1.minute
        t2_minutes = time2.hour * 60 + time2.minute
        return t2_minutes - t1_minutes
    
    @staticmethod
    def log_time_status():
        """Log current time window status"""
        can_trade, reason = TimeFilter.can_enter_new_trade()
        window = TimeFilter.get_current_window()
        
        if can_trade:
            logger.info(f"✓ Time Check: {window} - {reason}")
        else:
            logger.debug(f"✗ Time Check: {window} - {reason}")
            next_info = TimeFilter.get_next_window_info()
            if next_info["minutes_until"] > 0:
                logger.debug(
                    f"  Next window: {next_info['next_window']} "
                    f"starts at {next_info['starts_at']} "
                    f"({next_info['minutes_until']} mins)"
                )
