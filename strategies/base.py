"""Base strategy class - all strategies inherit from this"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import pandas as pd
import numpy as np


class SignalDirection(Enum):
    """Signal direction enum"""
    LONG = "BUY"
    SHORT = "SELL"
    EXIT = "EXIT"


@dataclass
class Signal:
    """Trading signal"""
    symbol: str
    action: str  # BUY, SELL, EXIT
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    confidence: float  # 0-1
    reason: str
    timestamp: datetime
    direction: Optional['SignalDirection'] = None  # Optional for compatibility
    
    def to_dict(self) -> Dict:
        """Convert signal to dictionary"""
        return {
            "symbol": self.symbol,
            "action": self.action,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat()
        }


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(self, name: str, parameters: Dict):
        """Initialize strategy
        
        Args:
            name: Strategy name
            parameters: Strategy parameters dictionary
        """
        self.name = name
        self.parameters = parameters
        self.is_active = True
    
    @abstractmethod
    async def analyze(self, data: pd.DataFrame, symbol: str) -> Optional[Signal]:
        """Analyze market data and generate signal
        
        Args:
            data: OHLCV data as pandas DataFrame
            symbol: Trading symbol
            
        Returns:
            Signal if conditions met, None otherwise
        """
        pass
    
    @abstractmethod
    async def should_exit(self, position: Dict, current_price: float) -> bool:
        """Check if position should be exited
        
        Args:
            position: Current position data
            current_price: Current market price
            
        Returns:
            True if should exit, False otherwise
        """
        pass
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        risk_amount: float
    ) -> int:
        """Calculate position size based on risk
        
        Args:
            entry_price: Entry price per share
            stop_loss: Stop loss price
            risk_amount: Maximum risk amount in rupees
            
        Returns:
            Number of shares to buy
        """
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return 0
        
        quantity = int(risk_amount / risk_per_share)
        return max(quantity, 1)  # At least 1 share
    
    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = data['high']
        low = data['low']
        close = data['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()
    
    def calculate_sma(self, data: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average"""
        return data.rolling(window=period).mean()
    
    def is_bullish_candle(self, row: pd.Series) -> bool:
        """Check if candle is bullish"""
        return row['close'] > row['open']
    
    def is_bearish_candle(self, row: pd.Series) -> bool:
        """Check if candle is bearish"""
        return row['close'] < row['open']
    
    def get_swing_low(self, data: pd.DataFrame, lookback: int = 5) -> float:
        """Get recent swing low"""
        return data['low'].tail(lookback).min()
    
    def get_swing_high(self, data: pd.DataFrame, lookback: int = 5) -> float:
        """Get recent swing high"""
        return data['high'].tail(lookback).max()
