"""Groww broker adapter"""
import logging
import uuid
import asyncio
import hashlib
import os
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import aiohttp
import json

from brokers.base import (
    BaseBroker, Order, Position, Quote, OrderType,
    OrderStatus, TransactionType
)
from utils.timezone import IST, now_ist

logger = logging.getLogger(__name__)

# Shared by the bot and dashboard processes so they reuse one daily token
TOKEN_CACHE_PATH = os.getenv("GROWW_TOKEN_CACHE", "/tmp/groww_token.json")


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

        # Daily access token, obtained by exchanging api_key + api_secret.
        # Groww resets it every morning at 6:00 IST.
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.token_fetched_at: Optional[datetime] = None

        if not self.api_key or not self.api_secret:
            logger.error("Groww API credentials not provided")

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-API-VERSION": "1.0",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    @staticmethod
    def _next_reset_ist() -> datetime:
        """Next 6:00 IST, when Groww resets access tokens"""
        now = now_ist()
        reset = now.replace(hour=6, minute=0, second=0, microsecond=0)
        return reset if now < reset else reset + timedelta(days=1)

    @staticmethod
    def _read_token_cache() -> Dict[str, Any]:
        """Token state shared by the bot and dashboard processes (same container)"""
        try:
            with open(TOKEN_CACHE_PATH) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _write_token_cache(state: Dict[str, Any]) -> None:
        try:
            tmp_path = f"{TOKEN_CACHE_PATH}.{os.getpid()}"
            fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
            os.replace(tmp_path, TOKEN_CACHE_PATH)
        except OSError as e:
            logger.warning(f"Could not write Groww token cache: {e}")

    def _adopt_cached_token(self, rejected_token: Optional[str]) -> bool:
        """Use a valid token another process already fetched, instead of calling the token API"""
        state = self._read_token_cache()
        token = state.get("token")
        try:
            expiry = datetime.fromisoformat(state["expiry"])
        except (KeyError, TypeError, ValueError):
            return False
        if not token or token == rejected_token or expiry <= now_ist() + timedelta(minutes=1):
            return False
        self.access_token = token
        self.token_expiry = expiry
        self.token_fetched_at = datetime.fromisoformat(state.get("fetched_at", now_ist().isoformat()))
        logger.info(f"Groww access token reused from cache, valid until {expiry:%Y-%m-%d %H:%M} IST")
        return True

    async def _refresh_access_token(self, rejected_token: Optional[str] = None) -> None:
        """Get a daily access token: reuse the shared one if valid, else exchange api_key + api_secret"""
        if self._adopt_cached_token(rejected_token):
            return

        # Back off after a failed exchange; the token API is tightly rate limited
        state = self._read_token_cache()
        retry_after = state.get("retry_after")
        if retry_after and now_ist() < datetime.fromisoformat(retry_after):
            raise Exception(f"Groww token exchange backing off until {retry_after[11:19]} IST")

        if not self.session:
            self.session = aiohttp.ClientSession()

        timestamp = str(int(time.time()))
        checksum = hashlib.sha256((self.api_secret + timestamp).encode()).hexdigest()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-VERSION": "1.0",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        async with self.session.post(
            f"{self.api_url}/token/api/access",
            headers=headers,
            json={"key_type": "approval", "checksum": checksum, "timestamp": timestamp}
        ) as response:
            response_text = await response.text()
            if response.status >= 400:
                backoff = timedelta(minutes=15 if response.status == 429 else 2)
                state["retry_after"] = (now_ist() + backoff).isoformat()
                self._write_token_cache(state)
                raise Exception(f"Groww token exchange failed [{response.status}]: {response_text[:300]}")
            response_data = json.loads(response_text)

        token = response_data.get("token")
        if not token:
            raise Exception("Groww token exchange returned no token")

        # Expiry comes back as naive IST, e.g. "2026-10-30T06:00:00".
        # A past or near expiry would refresh on every request, so fall back to the next reset.
        try:
            expiry = datetime.fromisoformat(response_data["expiry"]).replace(tzinfo=IST)
        except (KeyError, TypeError, ValueError):
            expiry = None
        if expiry is None or expiry <= now_ist() + timedelta(minutes=5):
            logger.warning(f"Groww token expiry {response_data.get('expiry')!r} unusable, using next 6:00 IST")
            expiry = self._next_reset_ist()

        self.access_token = token
        self.token_expiry = expiry
        self.token_fetched_at = now_ist()
        self._write_token_cache({
            "token": token,
            "expiry": expiry.isoformat(),
            "fetched_at": self.token_fetched_at.isoformat(),
        })
        logger.info(f"Groww access token refreshed, valid until {expiry:%Y-%m-%d %H:%M} IST")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        retry_auth: bool = True
    ) -> Dict:
        """Make HTTP request to Groww API"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()

            if not self.access_token or now_ist() >= self.token_expiry:
                await self._refresh_access_token()

            url = f"{self.api_url}/{endpoint}"
            headers = self._get_headers()
            auth_rejected = False

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

                # Token rejected (e.g. reset at 6:00 IST) - refresh once and retry below.
                # Skip if the token is fresh: the token API allows only 150 calls/day.
                if (response.status in (401, 403) and retry_auth
                        and now_ist() - self.token_fetched_at > timedelta(minutes=1)):
                    auth_rejected = True

                # Handle non-JSON responses
                elif response.status >= 400:
                    try:
                        response_data = json.loads(response_text)
                        error_msg = response_data.get('message', response_text)
                    except:
                        error_msg = response_text
                    
                    logger.error(f"Groww API error: {response.status} - {error_msg}")
                    raise Exception(f"API error [{response.status}]: {error_msg}")
                
                # Parse JSON response
                else:
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

            if auth_rejected:
                logger.warning(f"Groww rejected access token on {endpoint}, refreshing and retrying once")
                await self._refresh_access_token(rejected_token=self.access_token)
                return await self._make_request(method, endpoint, data, params, retry_auth=False)

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
    
    async def get_top_gainers(self, symbols: List[str], limit: int = 20) -> List[Dict]:
        """Get top gainers among the given NSE symbols
        
        Groww has no market-movers endpoint, so day change is computed from the
        bulk LTP and OHLC endpoints (max 50 symbols per call). The OHLC "close"
        is the previous session's close.
        
        Args:
            symbols: NSE trading symbols to rank, e.g. ["RELIANCE", "TCS"]
            limit: Number of stocks to return (default 20)
            
        Returns:
            List of dicts with symbol, ltp, day_change_percent, highest change first
        """
        try:
            result = []
            for i in range(0, len(symbols), 50):
                exchange_symbols = ",".join(f"NSE_{s}" for s in symbols[i:i + 50])
                params = {"segment": "CASH", "exchange_symbols": exchange_symbols}
                ltps = await self._make_request("GET", "live-data/ltp", params=params)
                ohlcs = await self._make_request("GET", "live-data/ohlc", params=params)
                
                for symbol in symbols[i:i + 50]:
                    ltp = ltps.get(f"NSE_{symbol}")
                    prev_close = (ohlcs.get(f"NSE_{symbol}") or {}).get("close")
                    # Unknown/renamed symbols come back missing or with null prices
                    if not ltp or not prev_close:
                        logger.debug(f"No live data for {symbol}, skipping")
                        continue
                    result.append({
                        "symbol": symbol,
                        "ltp": ltp,
                        "day_change_percent": (ltp - prev_close) / prev_close * 100
                    })
            
            result.sort(key=lambda s: s["day_change_percent"], reverse=True)
            logger.info(f"✓ Ranked {len(result)}/{len(symbols)} symbols for top gainers")
            return result[:limit]
            
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
