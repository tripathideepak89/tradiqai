"""Zerodha Kite Connect broker adapter"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from kiteconnect import KiteConnect, KiteTicker
import pyotp

from brokers.base import (
    BaseBroker, Order, Position, Quote, OrderType, 
    OrderStatus, TransactionType
)

logger = logging.getLogger(__name__)


class ZerodhaBroker(BaseBroker):
    """Zerodha Kite Connect broker adapter"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.user_id = config.get("user_id")
        self.password = config.get("password")
        self.totp_secret = config.get("totp_secret")
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.ticker: Optional[KiteTicker] = None
        self.access_token: Optional[str] = None
    
    async def connect(self) -> bool:
        """Connect and authenticate with Zerodha"""
        try:
            # Generate TOTP if available
            if self.totp_secret:
                totp = pyotp.TOTP(self.totp_secret)
                totp_token = totp.now()
                logger.info(f"Generated TOTP: {totp_token}")
            
            # For automated login, you'll need to implement headless browser automation
            # or manually provide the access token
            # This is a placeholder - you need to implement your login flow
            
            # For now, check if we have a saved access token
            # In production, implement proper token management
            if self.access_token:
                self.kite.set_access_token(self.access_token)
                self.is_connected = True
                logger.info("Connected to Zerodha successfully")
                return True
            else:
                logger.warning("Access token not available. Manual login required.")
                # You need to implement automated login or provide access token
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Zerodha: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Zerodha"""
        try:
            if self.ticker:
                self.ticker.close()
            self.is_connected = False
            logger.info("Disconnected from Zerodha")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from Zerodha: {e}")
            return False
    
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
        """Place an order on Zerodha"""
        try:
            # Map our enums to Kite enums
            kite_transaction_type = self.kite.TRANSACTION_TYPE_BUY if transaction_type == TransactionType.BUY else self.kite.TRANSACTION_TYPE_SELL
            
            order_type_map = {
                OrderType.MARKET: self.kite.ORDER_TYPE_MARKET,
                OrderType.LIMIT: self.kite.ORDER_TYPE_LIMIT,
                OrderType.SL: self.kite.ORDER_TYPE_SL,
                OrderType.SLM: self.kite.ORDER_TYPE_SLM
            }
            kite_order_type = order_type_map.get(order_type, self.kite.ORDER_TYPE_MARKET)
            
            order_params = {
                "tradingsymbol": symbol,
                "exchange": self.kite.EXCHANGE_NSE,
                "transaction_type": kite_transaction_type,
                "quantity": quantity,
                "order_type": kite_order_type,
                "product": product,
                "validity": self.kite.VALIDITY_DAY
            }
            
            if price and order_type in [OrderType.LIMIT, OrderType.SL]:
                order_params["price"] = price
            
            if trigger_price and order_type in [OrderType.SL, OrderType.SLM]:
                order_params["trigger_price"] = trigger_price
            
            order_id = self.kite.place_order(**order_params)
            
            logger.info(f"Order placed successfully: {order_id}")
            
            # Get order details
            return await self.get_order_status(order_id)
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> Order:
        """Modify an existing order"""
        try:
            modify_params = {"order_id": order_id}
            
            if quantity:
                modify_params["quantity"] = quantity
            if price:
                modify_params["price"] = price
            if trigger_price:
                modify_params["trigger_price"] = trigger_price
            
            self.kite.modify_order(**modify_params)
            logger.info(f"Order modified successfully: {order_id}")
            
            return await self.get_order_status(order_id)
            
        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.kite.cancel_order(order_id=order_id, variety=self.kite.VARIETY_REGULAR)
            logger.info(f"Order cancelled successfully: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Order:
        """Get status of a specific order"""
        try:
            orders = self.kite.orders()
            order_data = next((o for o in orders if o["order_id"] == order_id), None)
            
            if not order_data:
                raise ValueError(f"Order not found: {order_id}")
            
            return self._parse_order(order_data)
            
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            raise
    
    async def get_orders(self) -> List[Order]:
        """Get all orders for the day"""
        try:
            orders_data = self.kite.orders()
            return [self._parse_order(o) for o in orders_data]
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        try:
            positions_data = self.kite.positions()
            positions = []
            
            # Combine net and day positions
            for pos in positions_data.get("net", []) + positions_data.get("day", []):
                if pos["quantity"] != 0:
                    positions.append(Position(
                        symbol=pos["tradingsymbol"],
                        quantity=pos["quantity"],
                        average_price=pos["average_price"],
                        last_price=pos["last_price"],
                        pnl=pos["pnl"],
                        product=pos["product"]
                    ))
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def get_quote(self, symbol: str) -> Quote:
        """Get real-time quote for a symbol"""
        try:
            instrument_key = f"NSE:{symbol}"
            quote_data = self.kite.quote(instrument_key)[instrument_key]
            
            return Quote(
                symbol=symbol,
                last_price=quote_data["last_price"],
                bid=quote_data["depth"]["buy"][0]["price"] if quote_data["depth"]["buy"] else 0,
                ask=quote_data["depth"]["sell"][0]["price"] if quote_data["depth"]["sell"] else 0,
                volume=quote_data["volume"],
                timestamp=quote_data["last_trade_time"],
                open=quote_data["ohlc"]["open"],
                high=quote_data["ohlc"]["high"],
                low=quote_data["ohlc"]["low"],
                close=quote_data["ohlc"]["close"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            raise
    
    async def get_historical_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "15minute"
    ) -> List[Dict]:
        """Get historical OHLCV data"""
        try:
            instrument_token = self._get_instrument_token(symbol)
            historical_data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            return historical_data
        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return []
    
    async def get_holdings(self) -> List[Dict]:
        """Get holdings"""
        try:
            return self.kite.holdings()
        except Exception as e:
            logger.error(f"Failed to get holdings: {e}")
            return []
    
    async def get_margins(self) -> Dict[str, float]:
        """Get available margins"""
        try:
            margins = self.kite.margins()
            return {
                "available": margins["equity"]["available"]["live_balance"],
                "used": margins["equity"]["utilised"]["debits"]
            }
        except Exception as e:
            logger.error(f"Failed to get margins: {e}")
            return {"available": 0.0, "used": 0.0}
    
    def subscribe_quotes(self, symbols: List[str], callback) -> bool:
        """Subscribe to real-time quotes via websocket"""
        try:
            if not self.access_token:
                logger.error("Access token not available for websocket")
                return False
            
            self.ticker = KiteTicker(self.api_key, self.access_token)
            
            def on_ticks(ws, ticks):
                callback(ticks)
            
            def on_connect(ws, response):
                logger.info("Websocket connected")
                tokens = [self._get_instrument_token(s) for s in symbols]
                ws.subscribe(tokens)
                ws.set_mode(ws.MODE_FULL, tokens)
            
            def on_close(ws, code, reason):
                logger.warning(f"Websocket closed: {code} - {reason}")
            
            self.ticker.on_ticks = on_ticks
            self.ticker.on_connect = on_connect
            self.ticker.on_close = on_close
            
            # Start ticker in a separate thread
            self.ticker.connect(threaded=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe quotes: {e}")
            return False
    
    def unsubscribe_quotes(self, symbols: List[str]) -> bool:
        """Unsubscribe from real-time quotes"""
        try:
            if self.ticker:
                tokens = [self._get_instrument_token(s) for s in symbols]
                self.ticker.unsubscribe(tokens)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to unsubscribe quotes: {e}")
            return False
    
    def _parse_order(self, order_data: Dict) -> Order:
        """Parse Kite order data to Order object"""
        status_map = {
            "COMPLETE": OrderStatus.COMPLETE,
            "OPEN": OrderStatus.OPEN,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED
        }
        
        return Order(
            order_id=order_data["order_id"],
            symbol=order_data["tradingsymbol"],
            transaction_type=TransactionType.BUY if order_data["transaction_type"] == "BUY" else TransactionType.SELL,
            quantity=order_data["quantity"],
            price=order_data.get("price", 0.0),
            order_type=OrderType(order_data["order_type"]),
            status=status_map.get(order_data["status"], OrderStatus.PENDING),
            filled_quantity=order_data["filled_quantity"],
            average_price=order_data.get("average_price", 0.0),
            timestamp=order_data["order_timestamp"],
            message=order_data.get("status_message")
        )
    
    def _get_instrument_token(self, symbol: str) -> int:
        """Get instrument token for a symbol - implement caching in production"""
        # This is a placeholder - you should cache instruments data
        # and look up the token efficiently
        try:
            instruments = self.kite.instruments("NSE")
            instrument = next((i for i in instruments if i["tradingsymbol"] == symbol), None)
            if instrument:
                return instrument["instrument_token"]
            raise ValueError(f"Instrument not found: {symbol}")
        except Exception as e:
            logger.error(f"Failed to get instrument token: {e}")
            raise
