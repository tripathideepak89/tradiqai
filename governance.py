"""AI Investor Governance Policy Implementation

Based on AI Investor Governance Policy v1.0
Ensures capital preservation first, statistical edge second, growth third.
"""
import logging
from typing import Dict, Optional
from datetime import datetime, date
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TradingLayer(Enum):
    """Trading strategy layers"""
    INTRADAY = "L1_INTRADAY"
    WEEKLY = "L2_WEEKLY"
    MONTHLY = "L3_MONTHLY"
    QUARTERLY = "L4_QUARTERLY"


class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    EVENT_RISK = "EVENT_RISK"


class SystemMode(Enum):
    """System operational modes"""
    ACTIVE = "ACTIVE"
    SAFE_MODE = "SAFE_MODE"
    FROZEN = "FROZEN"
    HALTED = "HALTED"


@dataclass
class LayerAllocation:
    """Capital allocation for each layer"""
    layer: TradingLayer
    allocation_percent: float
    allocation_amount: float
    risk_per_trade_percent: float
    max_layer_drawdown_percent: float
    current_drawdown_percent: float = 0.0
    is_active: bool = True


@dataclass
class GovernanceState:
    """Current governance state"""
    system_mode: SystemMode
    total_capital: float
    peak_equity: float
    current_drawdown_percent: float
    daily_loss: float
    market_regime: MarketRegime
    last_updated: datetime


class GovernanceEngine:
    """Enforces AI Investor Governance Policy
    
    Policy Rules:
    - Capital preservation first
    - Risk controls override strategy logic
    - Multi-layer independent allocation
    - Global risk constraints
    """
    
    # Global Risk Limits (Section 4.1)
    MAX_TOTAL_DRAWDOWN = 15.0  # %
    MAX_DAILY_LOSS = 3.0  # %
    MAX_SINGLE_STOCK_EXPOSURE = 25.0  # %
    MAX_SECTOR_EXPOSURE = 40.0  # %
    
    # Layer Allocations (Section 3)
    LAYER_ALLOCATIONS = {
        TradingLayer.INTRADAY: {
            'percent': 25.0,
            'risk_per_trade': 0.8,
            'max_drawdown': 5.0
        },
        TradingLayer.WEEKLY: {
            'percent': 30.0,
            'risk_per_trade': 1.5,
            'max_drawdown': 8.0
        },
        TradingLayer.MONTHLY: {
            'percent': 25.0,
            'risk_per_trade': 2.0,
            'max_drawdown': 10.0
        },
        TradingLayer.QUARTERLY: {
            'percent': 20.0,
            'risk_per_trade': 3.0,
            'max_drawdown': 12.0
        }
    }
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_equity = initial_capital
        
        # Initialize layer allocations
        self.layers: Dict[TradingLayer, LayerAllocation] = {}
        for layer, config in self.LAYER_ALLOCATIONS.items():
            allocation_amount = (config['percent'] / 100) * initial_capital
            self.layers[layer] = LayerAllocation(
                layer=layer,
                allocation_percent=config['percent'],
                allocation_amount=allocation_amount,
                risk_per_trade_percent=config['risk_per_trade'],
                max_layer_drawdown_percent=config['max_drawdown']
            )
        
        # System state
        self.state = GovernanceState(
            system_mode=SystemMode.ACTIVE,
            total_capital=initial_capital,
            peak_equity=initial_capital,
            current_drawdown_percent=0.0,
            daily_loss=0.0,
            market_regime=MarketRegime.TRENDING,
            last_updated=datetime.now()
        )
        
        logger.info("[GOVERNANCE] Policy initialized")
        logger.info(f"  Initial Capital: Rs{initial_capital:,.2f}")
        for layer, alloc in self.layers.items():
            logger.info(
                f"  {layer.value}: Rs{alloc.allocation_amount:,.2f} "
                f"({alloc.allocation_percent}%, risk={alloc.risk_per_trade_percent}%)"
            )
    
    def update_capital(self, current_capital: float):
        """Update current capital and check drawdown (Section 9)"""
        self.current_capital = current_capital
        
        # Update peak equity
        if current_capital > self.peak_equity:
            self.peak_equity = current_capital
        
        # Calculate drawdown
        self.state.current_drawdown_percent = (
            (self.peak_equity - current_capital) / self.peak_equity * 100
        )
        
        # Check drawdown thresholds (Section 9)
        if self.state.current_drawdown_percent >= 20.0:
            self.state.system_mode = SystemMode.HALTED
            logger.error(
                f"[GOVERNANCE] SYSTEM HALTED - Drawdown {self.state.current_drawdown_percent:.1f}% "
                f">= 20% threshold. Manual review required."
            )
        elif self.state.current_drawdown_percent >= 15.0:
            self.state.system_mode = SystemMode.FROZEN
            logger.error(
                f"[GOVERNANCE] SYSTEM FROZEN - Drawdown {self.state.current_drawdown_percent:.1f}% "
                f">= 15% threshold. No new entries allowed."
            )
        elif self.state.current_drawdown_percent >= 10.0:
            if self.state.system_mode == SystemMode.ACTIVE:
                logger.warning(
                    f"[GOVERNANCE] Reducing position sizes 50% - Drawdown "
                    f"{self.state.current_drawdown_percent:.1f}% >= 10%"
                )
            # Don't demote from FROZEN/HALTED automatically
        
        self.state.last_updated = datetime.now()
    
    def get_layer_max_position_size(
        self,
        layer: TradingLayer,
        entry_price: float
    ) -> int:
        """Calculate maximum position size for a layer
        
        Considers:
        - Layer capital allocation
        - Single stock exposure limit (25%)
        - Layer risk per trade
        
        Returns:
            Maximum quantity allowed
        """
        layer_alloc = self.layers[layer]
        
        if not layer_alloc.is_active:
            logger.warning(f"[GOVERNANCE] Layer {layer.value} is paused")
            return 0
        
        # Maximum based on layer allocation (entire layer capital)
        max_from_layer = int(layer_alloc.allocation_amount / entry_price)
        
        # Maximum based on single stock exposure (25% of total capital)
        max_single_stock = int(
            (self.MAX_SINGLE_STOCK_EXPOSURE / 100) * self.current_capital / entry_price
        )
        
        # Maximum based on risk per trade
        # Risk per trade = layer_capital * risk_per_trade_percent / 100
        max_risk_amount = (
            layer_alloc.allocation_amount * 
            layer_alloc.risk_per_trade_percent / 100
        )
        # Assuming 2% stop loss for position sizing
        max_from_risk = int(max_risk_amount / (entry_price * 0.02))
        
        # Return the most conservative limit
        max_qty = min(max_from_layer, max_single_stock, max_from_risk)
        
        logger.debug(
            f"[GOVERNANCE] {layer.value} max position size for Rs{entry_price:.2f}: "
            f"{max_qty} shares (layer={max_from_layer}, stock_limit={max_single_stock}, "
            f"risk={max_from_risk})"
        )
        
        return max_qty
    
    def check_trade_approval(
        self,
        layer: TradingLayer,
        symbol: str,
        quantity: int,
        entry_price: float,
        current_exposure: float = 0.0
    ) -> tuple[bool, Optional[str]]:
        """Check if trade complies with governance policy (Section 6)
        
        Returns:
            (approved, reason)
        """
        # Check system mode
        if self.state.system_mode == SystemMode.HALTED:
            return False, "System HALTED - Manual review required"
        
        if self.state.system_mode == SystemMode.FROZEN:
            return False, "System FROZEN - No new entries allowed (drawdown >= 15%)"
        
        # Check if layer is active
        layer_alloc = self.layers[layer]
        if not layer_alloc.is_active:
            return False, f"Layer {layer.value} is paused"
        
        # Check if layer drawdown exceeded
        if layer_alloc.current_drawdown_percent >= layer_alloc.max_layer_drawdown_percent:
            return False, (
                f"Layer {layer.value} drawdown {layer_alloc.current_drawdown_percent:.1f}% "
                f">= limit {layer_alloc.max_layer_drawdown_percent}%"
            )
        
        # Check single stock exposure
        position_value = quantity * entry_price
        single_stock_percent = (position_value / self.current_capital) * 100
        
        if single_stock_percent > self.MAX_SINGLE_STOCK_EXPOSURE:
            return False, (
                f"Single stock exposure {single_stock_percent:.1f}% exceeds "
                f"limit {self.MAX_SINGLE_STOCK_EXPOSURE}%"
            )
        
        # Check layer capital allocation
        if position_value > layer_alloc.allocation_amount:
            return False, (
                f"Trade capital Rs{position_value:,.2f} exceeds layer allocation "
                f"Rs{layer_alloc.allocation_amount:,.2f}"
            )
        
        # Check total exposure with existing positions
        total_exposure_after = current_exposure + position_value
        max_exposure = (self.MAX_SECTOR_EXPOSURE / 100) * self.current_capital
        
        if total_exposure_after > max_exposure:
            return False, (
                f"Total exposure Rs{total_exposure_after:,.2f} would exceed limit "
                f"Rs{max_exposure:,.2f}"
            )
        
        # All checks passed
        return True, None
    
    def update_market_regime(self, regime: MarketRegime):
        """Update market regime classification (Section 5.2)"""
        old_regime = self.state.market_regime
        self.state.market_regime = regime
        
        if old_regime != regime:
            logger.info(f"[GOVERNANCE] Market regime changed: {old_regime.value} -> {regime.value}")
            
            # Regime-specific adjustments
            if regime == MarketRegime.HIGH_VOLATILITY:
                logger.warning("[GOVERNANCE] High volatility detected - Reduce position sizes 30%")
            elif regime == MarketRegime.EVENT_RISK:
                logger.warning("[GOVERNANCE] Event risk detected - Suspend intraday layer")
                self.layers[TradingLayer.INTRADAY].is_active = False
    
    def get_position_size_multiplier(self) -> float:
        """Get position size multiplier based on drawdown (Section 9)
        
        Returns:
            Multiplier (1.0 = full size, 0.5 = half size, 0.0 = no trades)
        """
        if self.state.system_mode == SystemMode.HALTED:
            return 0.0
        
        if self.state.system_mode == SystemMode.FROZEN:
            return 0.0
        
        if self.state.current_drawdown_percent >= 10.0:
            return 0.5  # Reduce 50%
        
        # Market regime adjustments
        if self.state.market_regime == MarketRegime.HIGH_VOLATILITY:
            return 0.7  # Reduce 30%
        
        return 1.0
    
    def get_governance_summary(self) -> str:
        """Get governance state summary"""
        lines = [
            "=== GOVERNANCE STATUS ===",
            f"System Mode: {self.state.system_mode.value}",
            f"Capital: Rs{self.current_capital:,.2f} (Peak: Rs{self.peak_equity:,.2f})",
            f"Drawdown: {self.state.current_drawdown_percent:.2f}%",
            f"Market Regime: {self.state.market_regime.value}",
            f"Position Multiplier: {self.get_position_size_multiplier():.0%}",
            "",
            "Layer Status:"
        ]
        
        for layer, alloc in self.layers.items():
            status = "ACTIVE" if alloc.is_active else "PAUSED"
            lines.append(
                f"  {layer.value}: Rs{alloc.allocation_amount:,.2f} "
                f"({alloc.allocation_percent}%) - {status}"
            )
        
        return "\n".join(lines)
