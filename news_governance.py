"""
News Governance Rules - Event Risk Management
Prevents trading during high-risk events
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, time
from enum import Enum

logger = logging.getLogger(__name__)


class EventRiskLevel(str, Enum):
    """Event risk levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NewsGovernance:
    """
    News-related governance and risk rules
    
    Key Rules:
    1. No trading 2 min after breaking news (let volatility settle)
    2. Trade only if volume ≥ 2× average
    3. If price moved > 2% before detection, don't chase
    4. Use VWAP anchor on news days
    5. Reduce position size 30% on news-driven trades
    """
    
    def __init__(self):
        self.news_cooldown_seconds = 120  # 2 minutes
        self.min_volume_multiplier = 2.0
        self.max_chase_pct = 2.0
        self.news_position_size_factor = 0.7  # Reduce by 30%
        
        # Event risk calendar (would be populated from API/config)
        self.event_calendar = {}
    
    def check_news_cooldown(
        self,
        news_timestamp: datetime,
        current_time: datetime = None
    ) -> Tuple[bool, str]:
        """
        Rule 1: No trading 2 minutes after breaking news
        
        Returns: (can_trade, reason)
        """
        if current_time is None:
            current_time = datetime.now()
        
        seconds_since_news = (current_time - news_timestamp).total_seconds()
        
        if seconds_since_news < self.news_cooldown_seconds:
            remaining = int(self.news_cooldown_seconds - seconds_since_news)
            return False, f"News cooldown: wait {remaining}s for volatility to settle"
        
        return True, ""
    
    def check_volume_requirement(
        self,
        current_volume: float,
        avg_volume: float
    ) -> Tuple[bool, str]:
        """
        Rule 2: Trade only if volume ≥ 2× average
        
        News without volume = trap
        """
        if avg_volume == 0:
            return False, "No average volume data"
        
        volume_ratio = current_volume / avg_volume
        
        if volume_ratio < self.min_volume_multiplier:
            return False, f"Volume {volume_ratio:.1f}× < required {self.min_volume_multiplier}×"
        
        return True, ""
    
    def check_chase_prevention(
        self,
        price_at_detection: float,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Rule 3: If price moved > 2% before detection, don't chase
        
        Most retail bots enter late
        """
        if price_at_detection == 0:
            return True, ""
        
        move_pct = abs((current_price - price_at_detection) / price_at_detection * 100)
        
        if move_pct > self.max_chase_pct:
            return False, f"Already moved {move_pct:.2f}% (> {self.max_chase_pct}%) - don't chase"
        
        return True, ""
    
    def check_vwap_bias(
        self,
        action: str,
        current_price: float,
        vwap: float
    ) -> Tuple[bool, str]:
        """
        Rule 4: Use VWAP anchor on news days
        
        - Go long only above VWAP
        - Short only below VWAP
        
        VWAP shows institutional positioning
        """
        if vwap == 0:
            return True, "No VWAP data"
        
        if action == "BUY" and current_price < vwap:
            return False, f"Long rejected: price (Rs{current_price:.2f}) below VWAP (Rs{vwap:.2f})"
        
        if action == "SELL" and current_price > vwap:
            return False, f"Short rejected: price (Rs{current_price:.2f}) above VWAP (Rs{vwap:.2f})"
        
        return True, ""
    
    def get_position_size_adjustment(
        self,
        base_quantity: int,
        is_news_trade: bool
    ) -> Tuple[int, str]:
        """
        Rule 5: Reduce position size by 30% on news-driven trades
        
        Volatility increases
        """
        if not is_news_trade:
            return base_quantity, ""
        
        adjusted_quantity = int(base_quantity * self.news_position_size_factor)
        reduction_pct = (1 - self.news_position_size_factor) * 100
        
        reason = f"News trade: reduced by {reduction_pct:.0f}% (volatility risk)"
        
        return adjusted_quantity, reason
    
    def check_event_risk(
        self,
        current_date: datetime = None
    ) -> Tuple[EventRiskLevel, str]:
        """
        Check if today is a high-risk event day
        
        Examples:
        - RBI policy day
        - Budget day
        - Fed speech
        - Major earnings cluster
        - Global shock
        """
        if current_date is None:
            current_date = datetime.now()
        
        date_key = current_date.strftime('%Y-%m-%d')
        
        if date_key in self.event_calendar:
            event_data = self.event_calendar[date_key]
            risk_level = event_data.get('risk_level', EventRiskLevel.NONE)
            event_name = event_data.get('event', 'Unknown')
            
            return risk_level, event_name
        
        return EventRiskLevel.NONE, ""
    
    def should_disable_intraday(
        self,
        event_risk_level: EventRiskLevel
    ) -> Tuple[bool, str]:
        """
        Check if intraday trading should be disabled due to event risk
        """
        if event_risk_level in [EventRiskLevel.HIGH, EventRiskLevel.CRITICAL]:
            return True, f"Intraday disabled: {event_risk_level.value.upper()} event risk"
        
        return False, ""
    
    def add_event_to_calendar(
        self,
        date: str,  # Format: YYYY-MM-DD
        event: str,
        risk_level: EventRiskLevel
    ):
        """
        Add event to risk calendar
        
        Example usage:
        ```python
        governance.add_event_to_calendar(
            "2026-02-20",
            "RBI Monetary Policy",
            EventRiskLevel.HIGH
        )
        ```
        """
        self.event_calendar[date] = {
            'event': event,
            'risk_level': risk_level
        }
        
        logger.info(f"📅 Event calendar updated: {date} - {event} ({risk_level.value})")
    
    def check_all_news_governance(
        self,
        news_timestamp: datetime,
        current_price: float,
        price_at_detection: float,
        quote: Dict,
        action: str = "BUY"
    ) -> Tuple[bool, list]:
        """
        Run all news governance checks
        
        Returns: (passed, violations)
        """
        violations = []
        
        # Check 1: Cooldown
        can_trade, reason = self.check_news_cooldown(news_timestamp)
        if not can_trade:
            violations.append(f"Cooldown: {reason}")
        
        # Check 2: Volume
        volume = quote.get('volume', 0)
        avg_volume = quote.get('avg_volume', volume)
        can_trade, reason = self.check_volume_requirement(volume, avg_volume)
        if not can_trade:
            violations.append(f"Volume: {reason}")
        
        # Check 3: Chase prevention
        can_trade, reason = self.check_chase_prevention(price_at_detection, current_price)
        if not can_trade:
            violations.append(f"Chase: {reason}")
        
        # Check 4: VWAP bias
        vwap = quote.get('vwap', 0)
        can_trade, reason = self.check_vwap_bias(action, current_price, vwap)
        if not can_trade:
            violations.append(f"VWAP: {reason}")
        
        # Check 5: Event risk
        event_risk, event_name = self.check_event_risk()
        should_disable, reason = self.should_disable_intraday(event_risk)
        if should_disable:
            violations.append(f"Event: {reason}")
        
        passed = len(violations) == 0
        
        return passed, violations


class NewsStrategyMode:
    """
    News Strategy Mode Rules
    
    If high-impact positive news:
    1. Wait first 5-min candle close
    2. Wait pullback toward VWAP
    3. Enter on continuation break
    4. Tight stop below VWAP
    """
    
    @staticmethod
    def should_wait_for_candle_close(
        news_timestamp: datetime,
        candle_interval_minutes: int = 5
    ) -> Tuple[bool, str]:
        """
        Wait for first candle to close after news
        
        Don't enter on first spike candle
        """
        now = datetime.now()
        minutes_since_news = (now - news_timestamp).total_seconds() / 60
        
        if minutes_since_news < candle_interval_minutes:
            remaining = int(candle_interval_minutes - minutes_since_news)
            return True, f"Wait {remaining} min for first candle close"
        
        return False, ""
    
    @staticmethod
    def check_pullback_to_vwap(
        current_price: float,
        vwap: float,
        direction: str
    ) -> Tuple[bool, str]:
        """
        For long: Wait for pullback toward VWAP before entry
        For short: Wait for rally toward VWAP
        
        Institutional approach: Don't chase the spike
        """
        if vwap == 0:
            return False, "No VWAP data"
        
        distance_from_vwap_pct = abs((current_price - vwap) / vwap * 100)
        
        if direction == "BULLISH":
            # For long, wait for price to be within 1% of VWAP
            if current_price > vwap * 1.01:
                return False, f"Wait for pullback: {distance_from_vwap_pct:.2f}% above VWAP"
            return True, "Near VWAP, entry zone"
        
        elif direction == "BEARISH":
            # For short, wait for price to be within 1% of VWAP
            if current_price < vwap * 0.99:
                return False, f"Wait for rally: {distance_from_vwap_pct:.2f}% below VWAP"
            return True, "Near VWAP, entry zone"
        
        return False, "Direction unclear"
    
    @staticmethod
    def check_continuation_break(
        current_price: float,
        pre_news_high: float,
        pre_news_low: float,
        direction: str
    ) -> Tuple[bool, str]:
        """
        Enter on continuation break (new high/low after pullback)
        
        This confirms the move is real, not just a spike
        """
        if direction == "BULLISH":
            if current_price > pre_news_high:
                return True, "Continuation: New high after pullback"
            return False, f"Wait for break above Rs{pre_news_high:.2f}"
        
        elif direction == "BEARISH":
            if current_price < pre_news_low:
                return True, "Continuation: New low after pullback"
            return False, f"Wait for break below Rs{pre_news_low:.2f}"
        
        return False, "Direction unclear"
    
    @staticmethod
    def calculate_news_stop_loss(
        entry_price: float,
        vwap: float,
        direction: str
    ) -> float:
        """
        Tight stop below/above VWAP for news trades
        
        News trades: use VWAP as anchor, not % distance
        """
        if direction == "BULLISH":
            # Stop below VWAP
            return vwap * 0.998  # 0.2% below VWAP
        
        elif direction == "BEARISH":
            # Stop above VWAP
            return vwap * 1.002  # 0.2% above VWAP
        
        # Fallback: 1% stop
        return entry_price * (0.99 if direction == "BULLISH" else 1.01)
