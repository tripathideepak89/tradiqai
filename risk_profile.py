"""
Risk Profile Engine for TradiqAI

Calculates trading parameters based on user's risk tolerance (0-100%).
- 0% = Ultra Conservative (Capital Preservation)
- 50% = Balanced (Moderate Growth)
- 100% = Aggressive (Maximum Growth)
"""

from dataclasses import dataclass
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskProfile:
    """Trading parameters derived from risk tolerance level"""
    
    # Core metrics
    risk_tolerance: int  # 0-100
    risk_label: str  # "Ultra Safe", "Conservative", etc.
    
    # Position sizing
    max_open_positions: int
    max_capital_per_trade_percent: float
    max_exposure_percent: float
    
    # Risk limits
    risk_per_trade_percent: float
    max_daily_loss_percent: float
    max_drawdown_percent: float
    
    # Stop loss / Take profit
    stop_loss_multiplier: float  # ATR multiplier
    take_profit_multiplier: float  # Risk:Reward ratio
    trailing_stop_enabled: bool
    
    # Trading behavior
    consecutive_loss_limit: int
    consecutive_loss_pause_minutes: int
    allow_volatile_stocks: bool
    min_volume_multiplier: float  # Minimum volume relative to average
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "risk_tolerance": self.risk_tolerance,
            "risk_label": self.risk_label,
            "max_open_positions": self.max_open_positions,
            "max_capital_per_trade_percent": self.max_capital_per_trade_percent,
            "max_exposure_percent": self.max_exposure_percent,
            "risk_per_trade_percent": self.risk_per_trade_percent,
            "max_daily_loss_percent": self.max_daily_loss_percent,
            "max_drawdown_percent": self.max_drawdown_percent,
            "stop_loss_multiplier": self.stop_loss_multiplier,
            "take_profit_multiplier": self.take_profit_multiplier,
            "trailing_stop_enabled": self.trailing_stop_enabled,
            "consecutive_loss_limit": self.consecutive_loss_limit,
            "consecutive_loss_pause_minutes": self.consecutive_loss_pause_minutes,
            "allow_volatile_stocks": self.allow_volatile_stocks,
            "min_volume_multiplier": self.min_volume_multiplier
        }


def get_risk_label(risk_tolerance: int) -> str:
    """Get human-readable risk label"""
    if risk_tolerance <= 10:
        return "Ultra Safe"
    elif risk_tolerance <= 25:
        return "Very Conservative"
    elif risk_tolerance <= 40:
        return "Conservative"
    elif risk_tolerance <= 60:
        return "Balanced"
    elif risk_tolerance <= 75:
        return "Growth"
    elif risk_tolerance <= 90:
        return "Aggressive"
    else:
        return "Very Aggressive"


def interpolate(risk: int, min_val: float, max_val: float) -> float:
    """Linear interpolation based on risk tolerance 0-100"""
    return min_val + (max_val - min_val) * (risk / 100.0)


def calculate_risk_profile(risk_tolerance: int, capital: float = 50000.0) -> RiskProfile:
    """
    Calculate trading parameters based on risk tolerance.
    
    Risk tolerance scale:
    - 0%: Ultra conservative, capital preservation priority
    - 50%: Balanced approach, moderate risk/reward
    - 100%: Aggressive, maximum growth potential
    
    Args:
        risk_tolerance: User's risk preference (0-100)
        capital: User's trading capital for calculations
        
    Returns:
        RiskProfile with calculated trading parameters
    """
    # Clamp to valid range
    risk = max(0, min(100, risk_tolerance))
    
    # === Position Sizing ===
    # Max open positions: 1 (safe) to 5 (aggressive)
    max_positions_raw = interpolate(risk, 1.0, 5.0)
    max_open_positions = max(1, min(5, round(max_positions_raw)))
    
    # Capital per trade: 15% (safe) to 40% (aggressive)
    max_capital_per_trade = round(interpolate(risk, 15.0, 40.0), 1)
    
    # Total exposure: 30% (safe) to 90% (aggressive)
    max_exposure = round(interpolate(risk, 30.0, 90.0), 1)
    
    # === Risk Limits ===
    # Risk per trade: 0.3% (safe) to 2.5% (aggressive)
    risk_per_trade = round(interpolate(risk, 0.3, 2.5), 2)
    
    # Daily loss limit: 1% (safe) to 8% (aggressive)
    max_daily_loss = round(interpolate(risk, 1.0, 8.0), 1)
    
    # Max drawdown: 8% (safe) to 25% (aggressive)
    max_drawdown = round(interpolate(risk, 8.0, 25.0), 1)
    
    # === Stop Loss / Take Profit ===
    # SL ATR multiplier: 3.0 (safe - wider stops) to 1.5 (aggressive - tighter stops)
    # Note: Safer = wider stops to avoid noise, Aggressive = tighter for more trades
    stop_loss_mult = round(interpolate(risk, 3.0, 1.5), 1)
    
    # TP ratio: 1.5 (safe - quick profits) to 3.0 (aggressive - let winners run)
    take_profit_mult = round(interpolate(risk, 1.5, 3.0), 1)
    
    # Trailing stop: enabled for balanced and above (>40%)
    trailing_enabled = risk >= 40
    
    # === Trading Behavior ===
    # Consecutive loss limit: 2 (safe) to 5 (aggressive)
    consec_loss_raw = interpolate(risk, 2.0, 5.0)
    consecutive_loss_limit = max(2, min(5, round(consec_loss_raw)))
    
    # Pause duration: 90 min (safe - longer cooldown) to 30 min (aggressive)
    pause_raw = interpolate(risk, 90.0, 30.0)
    pause_minutes = max(30, min(120, round(pause_raw / 15) * 15))  # Round to 15 min intervals
    
    # Allow volatile stocks: only for aggressive (>60%)
    allow_volatile = risk > 60
    
    # Minimum volume: 2.0x (safe - only liquid stocks) to 1.0x (aggressive)
    min_volume = round(interpolate(risk, 2.0, 1.0), 1)
    
    logger.info(f"Calculated risk profile: {risk}% → {get_risk_label(risk)}")
    
    return RiskProfile(
        risk_tolerance=risk,
        risk_label=get_risk_label(risk),
        max_open_positions=max_open_positions,
        max_capital_per_trade_percent=max_capital_per_trade,
        max_exposure_percent=max_exposure,
        risk_per_trade_percent=risk_per_trade,
        max_daily_loss_percent=max_daily_loss,
        max_drawdown_percent=max_drawdown,
        stop_loss_multiplier=stop_loss_mult,
        take_profit_multiplier=take_profit_mult,
        trailing_stop_enabled=trailing_enabled,
        consecutive_loss_limit=consecutive_loss_limit,
        consecutive_loss_pause_minutes=pause_minutes,
        allow_volatile_stocks=allow_volatile,
        min_volume_multiplier=min_volume
    )


def get_risk_amount(risk_tolerance: int, capital: float) -> Dict[str, float]:
    """
    Calculate actual rupee amounts based on risk tolerance and capital.
    
    Returns dict with:
    - max_per_trade_risk: ₹ amount to risk per trade
    - max_daily_loss: ₹ amount max daily loss
    - max_position_size: ₹ amount per position
    """
    profile = calculate_risk_profile(risk_tolerance, capital)
    
    return {
        "max_per_trade_risk": round(capital * profile.risk_per_trade_percent / 100, 2),
        "max_daily_loss": round(capital * profile.max_daily_loss_percent / 100, 2),
        "max_position_size": round(capital * profile.max_capital_per_trade_percent / 100, 2),
        "max_exposure": round(capital * profile.max_exposure_percent / 100, 2)
    }


# Predefined profiles for quick reference
PRESET_PROFILES = {
    "ultra_safe": calculate_risk_profile(0),
    "conservative": calculate_risk_profile(25),
    "balanced": calculate_risk_profile(50),
    "growth": calculate_risk_profile(75),
    "aggressive": calculate_risk_profile(100)
}


if __name__ == "__main__":
    # Demo: Show profiles at different risk levels
    print("=" * 60)
    print("TradiqAI Risk Profile Calculator")
    print("=" * 60)
    
    for level in [0, 25, 50, 75, 100]:
        profile = calculate_risk_profile(level)
        amounts = get_risk_amount(level, 50000)
        
        print(f"\n📊 Risk Level: {level}% ({profile.risk_label})")
        print(f"   Max Positions: {profile.max_open_positions}")
        print(f"   Risk/Trade: {profile.risk_per_trade_percent}% (₹{amounts['max_per_trade_risk']:,.0f})")
        print(f"   Daily Loss Limit: {profile.max_daily_loss_percent}% (₹{amounts['max_daily_loss']:,.0f})")
        print(f"   Max Exposure: {profile.max_exposure_percent}%")
        print(f"   Volatile Stocks: {'✅' if profile.allow_volatile_stocks else '❌'}")
