"""Base broker interface - all broker adapters must implement this"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OrderType(str, Enum):
    """Order type enumeration"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SLM = "SL-M"


class OrderStatus(str, Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TransactionType(str, Enum):
    """Transaction type enumeration"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Quote:
    """Market quote data"""
    symbol: str
    last_price: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    # Additional fields for better decision making
    upper_circuit_limit: Optional[float] = None
    lower_circuit_limit: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None


@dataclass
class Position:
    """Position data"""
    symbol: str
    quantity: int
    average_price: float
    last_price: float
    pnl: float
    product: str  # MIS, CNC, NRML


@dataclass
class Order:
    """Order information"""
    order_id: str
    symbol: str
    transaction_type: TransactionType
    quantity: int
    price: float
    order_type: OrderType
    status: OrderStatus
    filled_quantity: int
    average_price: float
    timestamp: datetime
    message: Optional[str] = None


class BaseBroker(ABC):
    """Abstract base class for all broker adapters"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize broker with configuration"""
        self.config = config
        self.is_connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect and authenticate with broker"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from broker"""
        pass
    
    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        transaction_type: TransactionType,
        quantity: int,
        order_type: OrderType,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: str = "MIS"
    ) -> Order:
        """Place an order"""
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> Order:
        """Modify an existing order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """Get status of a specific order"""
        pass
    
    @abstractmethod
    async def get_orders(self) -> List[Order]:
        """Get all orders for the day"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        pass
    
    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """Get real-time quote for a symbol"""
        pass
    
    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "15minute"
    ) -> List[Dict]:
        """Get historical OHLCV data"""
        pass
    
    @abstractmethod
    async def get_holdings(self) -> List[Dict]:
        """Get holdings (for delivery/CNC positions)"""
        pass
    
    @abstractmethod
    async def get_margins(self) -> Dict[str, float]:
        """Get available margins"""
        pass
    
    @abstractmethod
    def subscribe_quotes(self, symbols: List[str], callback) -> bool:
        """Subscribe to real-time quotes via websocket"""
        pass
    
    @abstractmethod
    def unsubscribe_quotes(self, symbols: List[str]) -> bool:
        """Unsubscribe from real-time quotes"""
        pass
