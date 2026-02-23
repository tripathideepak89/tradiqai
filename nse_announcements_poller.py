"""
NSE Announcements Poller
Handles NSE session/cookie management and corporate announcements fetching
"""
import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import time

logger = logging.getLogger(__name__)


class NSEAnnouncementsPoller:
    """
    Production-ready NSE corporate announcements fetcher
    
    Handles:
    - Session/cookie management
    - NSE API endpoint calls
    - Error handling with exponential backoff
    - Rate limiting protection
    """
    
    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.session: Optional[aiohttp.ClientSession] = None
        self.cookies: Dict = {}
        self.last_cookie_refresh = None
        self.cookie_refresh_interval = timedelta(minutes=30)  # Refresh every 30 min
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Min 1 second between requests
        
        # Error handling
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.backoff_seconds = [5, 15, 30, 60, 120]  # Exponential backoff
        
        # Browser-like headers (required by NSE)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Referer': 'https://www.nseindia.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
    
    async def initialize(self):
        """Initialize HTTP session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )
            logger.info("✅ NSE HTTP session initialized")
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🔌 NSE HTTP session closed")
    
    async def _establish_session_cookies(self) -> bool:
        """
        Step A: Establish session by visiting NSE homepage
        This gets us the required cookies
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            await self.initialize()
            
            # Visit homepage to get cookies
            logger.info("🔐 Establishing NSE session cookies...")
            
            async with self.session.get(
                self.base_url,
                headers=self.headers,
                allow_redirects=True
            ) as response:
                
                if response.status == 200:
                    # Store cookies
                    self.cookies = {cookie.key: cookie.value for cookie in response.cookies.values()}
                    self.last_cookie_refresh = datetime.now()
                    
                    logger.info(f"✅ NSE session established - Got {len(self.cookies)} cookies")
                    logger.debug(f"   Cookies: {list(self.cookies.keys())}")
                    
                    self.consecutive_errors = 0
                    return True
                else:
                    logger.error(f"❌ Failed to establish NSE session: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error establishing NSE session: {e}")
            self.consecutive_errors += 1
            return False
    
    async def _should_refresh_cookies(self) -> bool:
        """Check if cookies need refresh"""
        if not self.cookies:
            return True
        
        if not self.last_cookie_refresh:
            return True
        
        elapsed = datetime.now() - self.last_cookie_refresh
        if elapsed > self.cookie_refresh_interval:
            logger.info("⏰ Cookie refresh interval reached")
            return True
        
        return False
    
    async def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def fetch_announcements(self, from_date: Optional[str] = None, 
                                 to_date: Optional[str] = None,
                                 symbol: Optional[str] = None) -> List[Dict]:
        """
        Step B: Fetch corporate announcements from NSE
        
        Args:
            from_date: Date in format 'DD-MMM-YYYY' (e.g., '18-FEB-2026')
            to_date: Date in format 'DD-MMM-YYYY'
            symbol: Stock symbol (optional, fetches all if None)
        
        Returns:
            List of announcement dictionaries
        """
        try:
            # Refresh cookies if needed
            if await self._should_refresh_cookies():
                success = await self._establish_session_cookies()
                if not success:
                    return []
            
            # Rate limit
            await self._rate_limit()
            
            # Build announcement URL
            # NSE announcements API endpoint
            announcements_url = f"{self.base_url}/api/corporates-corporateActions"
            
            # Build params
            params = {
                'index': 'equities'
            }
            
            if from_date:
                params['from_date'] = from_date
            if to_date:
                params['to_date'] = to_date
            if symbol:
                params['symbol'] = symbol
            
            logger.info(f"📡 Fetching NSE announcements: {params}")
            
            # Make request with cookies
            async with self.session.get(
                announcements_url,
                params=params,
                headers=self.headers,
                cookies=self.cookies,
                allow_redirects=True
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # NSE returns data in different formats depending on endpoint
                    # Try to extract announcements list
                    announcements = []
                    
                    if isinstance(data, list):
                        announcements = data
                    elif isinstance(data, dict):
                        # Try common keys
                        for key in ['data', 'announcements', 'corporateActions']:
                            if key in data and isinstance(data[key], list):
                                announcements = data[key]
                                break
                    
                    logger.info(f"✅ Fetched {len(announcements)} announcements from NSE")
                    self.consecutive_errors = 0
                    
                    return announcements
                
                elif response.status == 401:
                    # Unauthorized - need to refresh cookies
                    logger.warning("⚠️ NSE returned 401 - refreshing cookies...")
                    self.cookies.clear()
                    self.last_cookie_refresh = None
                    
                    # Retry once with fresh cookies
                    if await self._establish_session_cookies():
                        return await self.fetch_announcements(from_date, to_date, symbol)
                    
                    return []
                
                else:
                    logger.error(f"❌ NSE API returned HTTP {response.status}")
                    text = await response.text()
                    logger.debug(f"   Response: {text[:200]}")
                    
                    self.consecutive_errors += 1
                    return []
        
        except asyncio.TimeoutError:
            logger.error("❌ NSE API request timed out")
            self.consecutive_errors += 1
            return []
        
        except Exception as e:
            logger.error(f"❌ Error fetching NSE announcements: {e}")
            self.consecutive_errors += 1
            return []
    
    async def fetch_latest_announcements(self, hours_back: int = 1) -> List[Dict]:
        """
        Fetch announcements from last N hours
        
        Args:
            hours_back: How many hours back to fetch (default: 1)
        
        Returns:
            List of recent announcements
        """
        now = datetime.now()
        from_date = (now - timedelta(hours=hours_back)).strftime('%d-%b-%Y').upper()
        to_date = now.strftime('%d-%b-%Y').upper()
        
        return await self.fetch_announcements(from_date=from_date, to_date=to_date)
    
    async def fetch_symbol_announcements(self, symbol: str, hours_back: int = 24) -> List[Dict]:
        """
        Fetch announcements for specific symbol
        
        Args:
            symbol: Stock symbol (e.g., 'TATASTEEL')
            hours_back: How many hours back to fetch
        
        Returns:
            List of announcements for that symbol
        """
        now = datetime.now()
        from_date = (now - timedelta(hours=hours_back)).strftime('%d-%b-%Y').upper()
        to_date = now.strftime('%d-%b-%Y').upper()
        
        return await self.fetch_announcements(
            from_date=from_date,
            to_date=to_date,
            symbol=symbol
        )
    
    def get_health_status(self) -> Dict:
        """
        Get poller health status
        
        Returns:
            Health status dict
        """
        status = "HEALTHY"
        
        if self.consecutive_errors >= self.max_consecutive_errors:
            status = "CRITICAL"
        elif self.consecutive_errors >= 3:
            status = "DEGRADED"
        elif not self.cookies:
            status = "NO_SESSION"
        
        next_backoff = None
        if self.consecutive_errors > 0:
            backoff_index = min(self.consecutive_errors - 1, len(self.backoff_seconds) - 1)
            next_backoff = self.backoff_seconds[backoff_index]
        
        return {
            'status': status,
            'session_established': bool(self.cookies),
            'cookies_count': len(self.cookies),
            'last_cookie_refresh': self.last_cookie_refresh.isoformat() if self.last_cookie_refresh else None,
            'consecutive_errors': self.consecutive_errors,
            'next_backoff_seconds': next_backoff
        }
    
    def should_backoff(self) -> Optional[int]:
        """
        Check if we should backoff due to errors
        
        Returns:
            Backoff seconds if should backoff, None otherwise
        """
        if self.consecutive_errors == 0:
            return None
        
        backoff_index = min(self.consecutive_errors - 1, len(self.backoff_seconds) - 1)
        return self.backoff_seconds[backoff_index]


# Singleton instance
_poller_instance = None


def get_nse_poller() -> NSEAnnouncementsPoller:
    """Get singleton NSE poller instance"""
    global _poller_instance
    if _poller_instance is None:
        _poller_instance = NSEAnnouncementsPoller()
    return _poller_instance


async def test_nse_poller():
    """Test NSE announcements poller"""
    poller = get_nse_poller()
    
    try:
        await poller.initialize()
        
        # Test session establishment
        print("\n🔐 Testing NSE session establishment...")
        success = await poller._establish_session_cookies()
        print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
        
        # Test fetching latest announcements
        print("\n📡 Testing announcements fetch...")
        announcements = await poller.fetch_latest_announcements(hours_back=2)
        print(f"   Found {len(announcements)} announcements")
        
        if announcements:
            print("\n📋 Sample announcement:")
            sample = announcements[0]
            for key, value in sample.items():
                print(f"   {key}: {value}")
        
        # Test health status
        print("\n🏥 Health Status:")
        health = poller.get_health_status()
        for key, value in health.items():
            print(f"   {key}: {value}")
    
    finally:
        await poller.close()


if __name__ == "__main__":
    # Run test
    asyncio.run(test_nse_poller())
