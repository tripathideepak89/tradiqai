"""Groww broker adapter"""
import logging
import uuid
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiohttp
import json

from brokers.base import (
    BaseBroker, Order, Position, Quote, OrderType, 
    OrderStatus, TransactionType
)

logger = logging.getLogger(__name__)


class GrowwBroker(BaseBroker):
    """Groww broker adapter
    
    Implements Groww's trading API for order placement and market data.
    API documentation: https://groww.in/docs/api (if available)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.api_url = config.get("api_url", "https://api.groww.in/v1")
        self.session: Optional[aiohttp.ClientSession] = None
        
        if not self.api_key or not self.api_secret:
            logger.error("Groww API credentials not provided")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-VERSION": "1.0",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to Groww API"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            url = f"{self.api_url}/{endpoint}"
            headers = self._get_headers()
            
            async with self.session.request(
                method,
                url,
                headers=headers,
                json=data,
                params=params
            ) as response:
                # Get response text first
                response_text = await response.text()
                
                # Log raw response for debugging
                logger.debug(f"Groww API response [{response.status}]: {response_text[:500]}")
                
                # Handle non-JSON responses
                if response.status >= 400:
                    try:
                        response_data = json.loads(response_text)
                        error_msg = response_data.get('message', response_text)
                    except:
                        error_msg = response_text
                    
                    logger.error(f"Groww API error: {response.status} - {error_msg}")
                    raise Exception(f"API error [{response.status}]: {error_msg}")
                
                # Parse JSON response
                try:
                    response_data = json.loads(response_text)
                    # Groww API wraps response in {"status": "SUCCESS", "payload": {...}}
                    if response_data.get("status") == "SUCCESS":
                        return response_data.get("payload", response_data)
                    else:
                        error_msg = response_data.get("message", "Unknown error")
                        raise Exception(f"API returned failure status: {error_msg}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {response_text[:500]}")
                    raise Exception(f"Invalid JSON response from API")
        
        except Exception as e:
            logger.error(f"Groww API request failed: {e}")
            raise
    
    async def connect(self) -> bool:
        """Connect to Groww"""
        try:
            logger.info("Connecting to Groww API...")
            
            # Validate credentials
            if not self.api_key or not self.api_secret:
                logger.error("Groww API credentials missing")
                return False
            
            # Create session
            self.session = aiohttp.ClientSession()
            
            # Test connection with margins endpoint (documented endpoint)
            try:
                response = await self._make_request("GET", "margins/detail/user")
                logger.info(f"Connected to Groww successfully")
                self.is_connected = True
                return True
            except Exception as e:
                logger.error(f"Failed to verify Groww connection: {e}")
                return False
        
        except Exception as e:
            logger.error(f"Groww connection error: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Groww"""
        try:
            if self.session:
                await self.session.close()
                self.session = None
            self.is_connected = False
            logger.info("Disconnected from Groww")
            return True
        except Exception as e:
            logger.error(f"Groww disconnect error: {e}")
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
        """Place an order"""
        try:
            # Generate unique order reference ID (8-20 alphanumeric with max 2 hyphens)
            # Format: AT-12345678-ABCD (16 chars, 2 hyphens)
            timestamp_str = str(int(datetime.now().timestamp()))[-8:]  # Last 8 digits
            random_str = str(uuid.uuid4()).replace('-', '')[:4].upper()  # 4 random chars
            order_ref_id = f"AT-{timestamp_str}-{random_str}"
            
            order_data = {
                "trading_symbol": symbol,
                "exchange": "NSE",
                "segment": "CASH",
                "transaction_type": transaction_type.value,
                "quantity": quantity,
                "order_type": order_type.value,
                "product": product,
                "validity": "DAY",
                "order_reference_id": order_ref_id
            }
            
            if price:
                order_data["price"] = price
            if trigger_price:
                order_data["trigger_price"] = trigger_price
            
            response = await self._make_request("POST", "order/create", data=order_data)
            logger.info(f"Groww order/create response keys: {list(response.keys()) if isinstance(response, dict) else type(response)}")

            # Groww create response may use different key names across API versions
            order_id = (
                response.get("groww_order_id")
                or response.get("order_id")
                or response.get("id")
                or response.get("orderId")
            )
            logger.info(f"Groww order placed: {order_id} (ref: {order_ref_id})")

            if order_id:
                try:
                    return await self.get_order_status(order_id)
                except Exception as status_err:
                    # Status fetch failed but order was placed — return synthetic Order
                    logger.warning(f"Order placed but status fetch failed ({status_err}); using ref ID")

            # Fallback: order is live on Groww, return a confirmed OPEN Order
            return Order(
                order_id=order_id or order_ref_id,
                symbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                price=price or 0.0,
                order_type=order_type,
                status=OrderStatus.OPEN,
                filled_quantity=0,
                average_price=0.0,
                timestamp=datetime.now(),
                message=f"Order placed (ref: {order_ref_id})"
            )
        
        except Exception as e:
            logger.error(f"Failed to place Groww order: {e}")
            raise
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        order_type: Optional[str] = "LIMIT"
    ) -> Order:
        """Modify an order"""
        try:
            modify_data = {
                "groww_order_id": order_id,
                "segment": "CASH",
                "order_type": order_type
            }
            if quantity:
                modify_data["quantity"] = quantity
            if price:
                modify_data["price"] = price
            if trigger_price:
                modify_data["trigger_price"] = trigger_price
            
            await self._make_request("POST", "order/modify", data=modify_data)
            logger.info(f"Groww order modified: {order_id}")
            
            return await self.get_order_status(order_id)
        except Exception as e:
            logger.error(f"Failed to modify Groww order: {e}")
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            cancel_data = {
                "groww_order_id": order_id,
                "segment": "CASH"
            }
            await self._make_request("POST", "order/cancel", data=cancel_data)
            logger.info(f"Groww order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel Groww order: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Order:
        """Get order status"""
        try:
            response = await self._make_request(
                "GET", 
                f"order/status/{order_id}",
                params={"segment": "CASH"}
            )
            return self._parse_order(response)
        except Exception as e:
            logger.error(f"Failed to get Groww order status: {e}")
            raise
    
    def _parse_order(self, order_data: Dict) -> Order:
        """Parse Groww order data to Order object"""
        status_map = {
            "COMPLETE": OrderStatus.COMPLETE,
            "COMPLETED": OrderStatus.COMPLETE,
            "OPEN": OrderStatus.OPEN,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "PENDING": OrderStatus.PENDING
        }
        
        # Map API order types to our enum (handle variations)
        order_type_str = order_data.get("order_type", "MARKET")
        order_type_map = {
            "MARKET": OrderType.MARKET,
            "LIMIT": OrderType.LIMIT,
            "SL": OrderType.SL,
            "SLM": OrderType.SLM,
            "SL-M": OrderType.SLM,  # Broker might use hyphen
            "SL_M": OrderType.SLM,  # Or underscore
        }
        order_type = order_type_map.get(order_type_str, OrderType.MARKET)
        
        return Order(
            order_id=order_data.get("groww_order_id", ""),
            symbol=order_data.get("trading_symbol", ""),
            transaction_type=TransactionType.BUY if order_data.get("transaction_type") == "BUY" else TransactionType.SELL,
            quantity=order_data.get("quantity", 0),
            price=order_data.get("price", 0.0),
            order_type=order_type,
            status=status_map.get(order_data.get("order_status", "PENDING"), OrderStatus.PENDING),
            filled_quantity=order_data.get("filled_quantity", 0),
            average_price=order_data.get("average_fill_price", 0.0),
            timestamp=datetime.fromisoformat(order_data.get("created_at", datetime.now().isoformat())) if order_data.get("created_at") else datetime.now(),
            message=order_data.get("remark")
        )
    
    async def get_orders(self) -> List[Order]:
        """Get all orders"""
        try:
            response = await self._make_request(
                "GET", 
                "order/list",
                params={"segment": "CASH", "page": 0, "page_size": 100}
            )
            orders = []
            for order_data in response.get("order_list", []):
                orders.append(self._parse_order(order_data))
            return orders
        except Exception as e:
            logger.error(f"Failed to get Groww orders: {e}")
            return []
    
    async def get_positions(self) -> List[Position]:
        """Get positions"""
        try:
            response = await self._make_request(
                "GET", 
                "positions/user",
                params={"segment": "CASH"}
            )
            positions = []
            
            for pos_data in response.get("positions", []):
                quantity = pos_data.get("quantity", 0)
                if quantity != 0:
                    positions.append(Position(
                        symbol=pos_data.get("trading_symbol", ""),
                        quantity=quantity,
                        average_price=pos_data.get("net_price", 0.0),
                        last_price=0.0,  # Need to fetch separately via quote API
                        pnl=pos_data.get("realised_pnl", 0.0),
                        product=pos_data.get("product", "CNC")
                    ))
            
            return positions
        except Exception as e:
            logger.error(f"Failed to get Groww positions: {e}")
            return []
    
    async def get_quote(self, symbol: str) -> Quote:
        """Get quote"""
        try:
            # Rate limiting: wait 0.5 seconds between requests
            await asyncio.sleep(0.5)
            
            response = await self._make_request(
                "GET",
                "live-data/quote",
                params={
                    "trading_symbol": symbol,
                    "exchange": "NSE",
                    "segment": "CASH"
                }
            )
            
            ohlc = response.get("ohlc", {})
            return Quote(
                symbol=symbol,
                last_price=response.get("last_price", 0.0),
                bid=response.get("bid_price", 0.0),
                ask=response.get("offer_price", 0.0),
                volume=response.get("volume", 0),
                timestamp=datetime.now(),
                open=ohlc.get("open", 0.0) if isinstance(ohlc, dict) else 0.0,
                high=ohlc.get("high", 0.0) if isinstance(ohlc, dict) else 0.0,
                low=ohlc.get("low", 0.0) if isinstance(ohlc, dict) else 0.0,
                close=ohlc.get("close", 0.0) if isinstance(ohlc, dict) else 0.0,
                upper_circuit_limit=response.get("upper_circuit_limit"),
                lower_circuit_limit=response.get("lower_circuit_limit"),
                week_52_high=response.get("52w_high") or response.get("week_52_high"),
                week_52_low=response.get("52w_low") or response.get("week_52_low")
            )
        except Exception as e:
            logger.error(f"Failed to get Groww quote: {e}")
            raise
    
    async def get_historical_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "15minute"
    ) -> List[Dict]:
        """Get historical data using Groww's backtesting API
        
        Note: candle_interval format is string like "1minute", "5minute", "15minute", "1hour", "1day"
        Data limits: 15min candles can go back 90 days max
        """
        try:
            # Format dates as required by Groww API (yyyy-MM-dd HH:mm:ss)
            start_time = from_date.strftime("%Y-%m-%d %H:%M:%S")
            end_time = to_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Construct Groww symbol format: EXCHANGE-TRADINGSYMBOL
            # For equities: NSE-RELIANCE, BSE-WIPRO
            groww_symbol = f"NSE-{symbol}"
            
            params = {
                "exchange": "NSE",
                "segment": "CASH",
                "groww_symbol": groww_symbol,
                "start_time": start_time,
                "end_time": end_time,
                "candle_interval": interval  # e.g., "15minute", "5minute", "1hour"
            }
            
            logger.debug(f"Fetching historical data: {groww_symbol}, interval={interval}, from={start_time} to={end_time}")
            
            response = await self._make_request(
                "GET",
                "historical/candles",
                params=params
            )
            
            candles = response.get("candles", [])
            logger.info(f"Successfully fetched {len(candles)} candles for {groww_symbol}")
            return candles
            
            return response.get("candles", [])
        except Exception as e:
            logger.error(f"Failed to get Groww historical data: {e}")
            return []
    
    async def get_holdings(self) -> List[Dict]:
        """Get holdings"""
        try:
            response = await self._make_request("GET", "holdings/user")
            return response.get("holdings", [])
        except Exception as e:
            logger.error(f"Failed to get Groww holdings: {e}")
            return []
    
    async def get_margins(self) -> Dict[str, float]:
        """Get margins
        
        Returns available capital and margin usage from Groww API.
        Note: _make_request already extracts the 'payload' from the response
        """
        try:
            # _make_request returns the payload directly (not the full response)
            payload = await self._make_request("GET", "margins/detail/user")
            
            # Debug logging
            logger.debug(f"Margins payload: {json.dumps(payload, indent=2)[:500]}")
            
            # Extract equity margin details
            equity_details = payload.get("equity_margin_details", {})
            
            # Extract values
            available = equity_details.get("cnc_balance_available", 0.0)
            used = equity_details.get("cnc_margin_used", 0.0)
            clear_cash = payload.get("clear_cash", available)  # Total clear cash available
            
            logger.info(f"Parsed margins - available: ₹{clear_cash:,.2f}, used: ₹{used:,.2f}")
            
            return {
                "available": clear_cash,
                "used": used,
                "available_cash": clear_cash,  # Dashboard compatibility
                "margin_used": used,  # Dashboard compatibility
                "available_margin": clear_cash,  # Live monitor compatibility
                "used_margin": used  # Live monitor compatibility
            }
        except Exception as e:
            logger.error(f"Failed to get Groww margins: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "available": 0.0, 
                "used": 0.0,
                "available_cash": 0.0,
                "margin_used": 0.0,
                "available_margin": 0.0,
                "used_margin": 0.0
            }
    
    async def get_top_gainers(self, limit: int = 20, index: str = "NIFTY_500") -> List[Dict]:
        """Get top gainers from Groww
        
        Args:
            limit: Number of stocks to fetch (default 20)
            index: Index to fetch from (NIFTY_500, NIFTY_200, etc.)
            
        Returns:
            List of dicts with symbol, ltp, day_change_percent
        """
        try:
            # Try different possible endpoints
            endpoints_to_try = [
                "discover/top-gainers",
                "screener/top-gainers", 
                "market/top-gainers",
                "live-data/market-movers/gainers",
                "market-data/top-gainers"
            ]
            
            for endpoint in endpoints_to_try:
                try:
                    response = await self._make_request(
                        "GET",
                        endpoint,
                        params={
                            "index": index,
                            "limit": limit,
                            "exchange": "NSE",
                            "segment": "CASH"
                        }
                    )
                    
                    # Check if we got valid data
                    gainers = response.get("stocks", response.get("data", response.get("gainers", [])))
                    
                    if gainers and len(gainers) > 0:
                        # Extract relevant data
                        result = []
                        for stock in gainers[:limit]:
                            result.append({
                                "symbol": stock.get("trading_symbol", stock.get("symbol", "")),
                                "ltp": stock.get("ltp", stock.get("last_price", 0)),
                                "day_change_percent": stock.get("day_change_perc", stock.get("day_change_percent", 0))
                            })
                        
                        logger.info(f"✓ Fetched {len(result)} top gainers from {endpoint}")
                        return result
                        
                except Exception as e:
                    logger.debug(f"Endpoint {endpoint} failed: {e}")
                    continue
            
            # If all endpoints fail
            logger.warning("All top gainers endpoints failed")
            return []
            
        except Exception as e:
            logger.error(f"Failed to get top gainers from Groww: {e}")
            return []
    
    def subscribe_quotes(self, symbols: List[str], callback) -> bool:
        """Subscribe to quotes"""
        logger.warning("Groww WebSocket support not implemented yet")
        logger.info("Consider using REST polling for now")
        return False
    
    def unsubscribe_quotes(self, symbols: List[str]) -> bool:
        """Unsubscribe from quotes"""
        logger.warning("Groww WebSocket support not implemented yet")
        return False
