"""
News Ingestion Layer
Orchestrates news polling with burst mode, deduplication, and normalization
"""
import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import hashlib
import json

from nse_announcements_poller import get_nse_poller
from news_impact_detector import NewsCategory
from database import SessionLocal
from models import NewsItem

logger = logging.getLogger(__name__)


@dataclass
class NormalizedNews:
    """
    Standard news schema for all sources
    """
    # Identification
    news_id: str                    # Unique ID (hash of key fields)
    source: str                     # NSE / BSE / Broker / NewsAPI
    exchange: str                   # NSE / BSE
    symbol: str                     # Stock symbol
    
    # Content
    headline: str
    description: Optional[str] = None
    category: Optional[NewsCategory] = None
    
    # Metadata
    timestamp: datetime = None      # When news was published
    detected_at: datetime = None    # When we detected it
    attachment_url: Optional[str] = None
    
    # Raw data
    raw_data: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.now()


class NewsDeduplicator:
    """
    Deduplicates news items using stable keys
    """
    
    def __init__(self, ttl_seconds: int = 86400):  # 24 hours
        self.seen_ids: Set[str] = set()
        self.id_timestamps: Dict[str, datetime] = {}
        self.ttl_seconds = ttl_seconds
    
    def generate_news_id(self, symbol: str, timestamp: datetime, 
                        headline: str, source: str) -> str:
        """
        Generate stable unique ID for news item
        
        Uses: symbol + timestamp + headline + source
        """
        key_string = f"{symbol}|{timestamp.isoformat()}|{headline}|{source}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def is_duplicate(self, news_id: str) -> bool:
        """Check if news ID has been seen before"""
        return news_id in self.seen_ids
    
    def mark_seen(self, news_id: str):
        """Mark news ID as seen"""
        self.seen_ids.add(news_id)
        self.id_timestamps[news_id] = datetime.now()
    
    def cleanup_old(self):
        """Remove old IDs beyond TTL"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.ttl_seconds)
        
        old_ids = [
            news_id for news_id, ts in self.id_timestamps.items()
            if ts < cutoff
        ]
        
        for news_id in old_ids:
            self.seen_ids.discard(news_id)
            del self.id_timestamps[news_id]
        
        if old_ids:
            logger.info(f"🧹 Cleaned up {len(old_ids)} old news IDs")


class BurstModeDetector:
    """
    Detects when to switch to burst polling mode
    Based on volume spikes and range expansion
    """
    
    def __init__(self):
        self.burst_symbols: Dict[str, datetime] = {}  # symbol -> burst_start_time
        self.burst_duration = timedelta(minutes=3)    # Burst for 3 minutes
    
    def should_burst_poll(self, symbol: str, quote: Dict) -> bool:
        """
        Check if should use burst polling for this symbol
        
        Triggers:
        - Volume > 3× average
        - Range expansion > 2× ATR
        """
        # Check if already in burst mode
        if symbol in self.burst_symbols:
            burst_start = self.burst_symbols[symbol]
            if datetime.now() - burst_start < self.burst_duration:
                return True
            else:
                # Burst expired
                del self.burst_symbols[symbol]
                logger.info(f"[BURST] Burst mode expired for {symbol}")
                return False
        
        # Check for burst trigger conditions
        volume_ratio = quote.get('volume', 0) / max(quote.get('avg_volume', 1), 1)
        
        intraday_range = 0
        if quote.get('high') and quote.get('low'):
            intraday_range = (quote['high'] - quote['low']) / quote['low'] * 100
        
        # Trigger burst mode
        if volume_ratio >= 3.0:
            logger.warning(f"🚨 BURST MODE TRIGGERED for {symbol} - Volume spike {volume_ratio:.1f}×")
            self.burst_symbols[symbol] = datetime.now()
            return True
        
        if intraday_range >= 3.0:
            logger.warning(f"🚨 BURST MODE TRIGGERED for {symbol} - Range expansion {intraday_range:.1f}%")
            self.burst_symbols[symbol] = datetime.now()
            return True
        
        return False
    
    def get_burst_symbols(self) -> List[str]:
        """Get list of symbols currently in burst mode"""
        return list(self.burst_symbols.keys())


class NewsIngestionLayer:
    """
    Orchestrates news polling with burst mode and deduplication
    
    Architecture:
    - Normal polling: 30-60s
    - Burst polling: 5-10s (when volume/range spikes detected)
    - Deduplication using stable keys
    - Normalization to standard schema
    """
    
    def __init__(self, 
                 normal_poll_interval: int = 45,      # seconds
                 burst_poll_interval: int = 10,       # seconds
                 market_hours_start: str = "09:15",
                 market_hours_end: str = "15:30"):
        
        # Pollers
        self.nse_poller = get_nse_poller()
        
        # Components
        self.deduplicator = NewsDeduplicator()
        self.burst_detector = BurstModeDetector()
        
        # Polling config
        self.normal_poll_interval = normal_poll_interval
        self.burst_poll_interval = burst_poll_interval
        self.market_hours_start = market_hours_start
        self.market_hours_end = market_hours_end
        
        # State
        self.is_polling = False
        self.poll_task = None
        self.last_poll_time = None
        self.news_queue: List[NormalizedNews] = []  # Simple in-memory queue
        
        # Stats
        self.stats = {
            'total_fetched': 0,
            'total_duplicates': 0,
            'total_new': 0,
            'burst_triggers': 0
        }
    
    def is_market_hours(self) -> bool:
        """Check if currently in market hours"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        return self.market_hours_start <= current_time <= self.market_hours_end
    
    def get_current_poll_interval(self) -> int:
        """
        Get current poll interval based on mode
        
        Returns:
            Poll interval in seconds
        """
        # Check if any symbols in burst mode
        burst_symbols = self.burst_detector.get_burst_symbols()
        
        if burst_symbols:
            logger.debug(f"[BURST] Burst mode active for {len(burst_symbols)} symbols")
            return self.burst_poll_interval
        
        # Off-hours: slower polling
        if not self.is_market_hours():
            return self.normal_poll_interval * 10  # 10× slower off-hours
        
        return self.normal_poll_interval
    
    def normalize_nse_announcement(self, raw: Dict) -> Optional[NormalizedNews]:
        """
        Normalize NSE announcement to standard schema
        
        NSE fields vary, but typically:
        - symbol or sm_name
        - subject or desc
        - an_dt or attchmntTime (timestamp)
        - attchmntFile or attachment
        """
        try:
            # Extract symbol
            symbol = raw.get('symbol') or raw.get('sm_name') or raw.get('sm_isin_code', 'UNKNOWN')
            if isinstance(symbol, str):
                symbol = symbol.strip().upper()
            
            # Extract headline
            headline = raw.get('subject') or raw.get('desc') or raw.get('subjectText', '')
            if not headline:
                return None
            
            # Extract timestamp
            timestamp = None
            for time_field in ['an_dt', 'attchmntTime', 'disseminatedTime', 'timestamp']:
                if time_field in raw:
                    try:
                        # Try parsing various formats
                        time_str = raw[time_field]
                        if isinstance(time_str, str):
                            # Try ISO format first
                            try:
                                timestamp = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            except:
                                # Try other common formats
                                for fmt in ['%d-%b-%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S']:
                                    try:
                                        timestamp = datetime.strptime(time_str, fmt)
                                        break
                                    except:
                                        continue
                        break
                    except:
                        continue
            
            if not timestamp:
                timestamp = datetime.now()  # Fallback
            
            # Extract attachment URL
            attachment_url = raw.get('attchmntFile') or raw.get('attachment') or raw.get('file_link')
            
            # Generate news ID
            news_id = self.deduplicator.generate_news_id(
                symbol=symbol,
                timestamp=timestamp,
                headline=headline,
                source='NSE'
            )
            
            return NormalizedNews(
                news_id=news_id,
                source='NSE',
                exchange='NSE',
                symbol=symbol,
                headline=headline,
                description=raw.get('description'),
                category=self._infer_category(headline),
                timestamp=timestamp,
                attachment_url=attachment_url,
                raw_data=raw
            )
        
        except Exception as e:
            logger.error(f"❌ Error normalizing NSE announcement: {e}")
            logger.debug(f"   Raw data: {raw}")
            return None
    
    def _infer_category(self, headline: str) -> Optional[NewsCategory]:
        """
        Infer news category from headline
        Simple keyword matching - can be improved with NLP
        """
        headline_lower = headline.lower()
        
        # Earnings
        if any(word in headline_lower for word in ['result', 'earning', 'profit', 'loss', 'q1', 'q2', 'q3', 'q4', 'fy']):
            return NewsCategory.EARNINGS
        
        # Guidance
        if any(word in headline_lower for word in ['guidance', 'outlook', 'forecast', 'revision', 'upgrade', 'downgrade']):
            return NewsCategory.GUIDANCE
        
        # Regulatory
        if any(word in headline_lower for word in ['sebi', 'regulation', 'compliance', 'penalty', 'fine', 'ban', 'government', 'policy']):
            return NewsCategory.REGULATORY
        
        # Order win
        if any(word in headline_lower for word in ['order', 'contract', 'win', 'awarded', 'deal', 'agreement']):
            return NewsCategory.ORDER_WIN
        
        # Management
        if any(word in headline_lower for word in ['resign', 'appoint', 'ceo', 'cfo', 'director', 'board', 'management']):
            return NewsCategory.MANAGEMENT_CHANGE
        
        # M&A
        if any(word in headline_lower for word in ['merger', 'acquisition', 'takeover', 'buyout', 'consolidation']):
            return NewsCategory.MERGER_ACQUISITION
        
        # Promoter
        if any(word in headline_lower for word in ['promoter', 'pledge', 'stake', 'shareholding']):
            return NewsCategory.PROMOTER_ACTION
        
        return NewsCategory.GENERIC_PR
    
    async def poll_nse_once(self) -> List[NormalizedNews]:
        """
        Poll NSE once and return new normalized news
        
        Returns:
            List of new (non-duplicate) news items
        """
        try:
            # Fetch from NSE
            raw_announcements = await self.nse_poller.fetch_latest_announcements(hours_back=1)
            
            self.stats['total_fetched'] += len(raw_announcements)
            
            if not raw_announcements:
                return []
            
            # Normalize and deduplicate
            new_news = []
            
            for raw in raw_announcements:
                normalized = self.normalize_nse_announcement(raw)
                
                if not normalized:
                    continue
                
                # Check for duplicate
                if self.deduplicator.is_duplicate(normalized.news_id):
                    self.stats['total_duplicates'] += 1
                    continue
                
                # New news!
                self.deduplicator.mark_seen(normalized.news_id)
                new_news.append(normalized)
                self.stats['total_new'] += 1
                
                logger.info(f"📰 NEW NEWS: [{normalized.symbol}] {normalized.headline[:60]}...")
            
            return new_news
        
        except Exception as e:
            logger.error(f"❌ Error polling NSE: {e}")
            return []
    
    async def start_polling(self):
        """
        Start continuous polling loop
        """
        if self.is_polling:
            logger.warning("[WARNING] Polling already running")
            return
        
        self.is_polling = True
        await self.nse_poller.initialize()
        
        logger.info("[STARTED] News ingestion layer started")
        logger.info(f"   Normal interval: {self.normal_poll_interval}s")
        logger.info(f"   Burst interval: {self.burst_poll_interval}s")
        logger.info(f"   Market hours: {self.market_hours_start} - {self.market_hours_end}")
        
        while self.is_polling:
            try:
                # Check NSE health
                health = self.nse_poller.get_health_status()
                
                if health['status'] == 'CRITICAL':
                    logger.error("🚨 NSE poller in CRITICAL state - waiting...")
                    await asyncio.sleep(60)
                    continue
                
                # Check if should backoff
                backoff = self.nse_poller.should_backoff()
                if backoff:
                    logger.warning(f"[BACKOFF] Backing off for {backoff}s due to errors")
                    await asyncio.sleep(backoff)
                    continue
                
                # Poll once
                new_news = await self.poll_nse_once()
                
                # Add to queue and save to database
                if new_news:
                    self.news_queue.extend(new_news)
                    self._save_news_to_db(new_news)
                    logger.info(f"📥 Added {len(new_news)} news items to queue (total: {len(self.news_queue)})")
                
                self.last_poll_time = datetime.now()
                
                # Cleanup old dedup IDs periodically
                if len(self.deduplicator.seen_ids) > 1000:
                    self.deduplicator.cleanup_old()
                
                # Sleep until next poll
                poll_interval = self.get_current_poll_interval()
                logger.debug(f"💤 Sleeping for {poll_interval}s...")
                await asyncio.sleep(poll_interval)
            
            except asyncio.CancelledError:
                logger.info("⏹️ Polling cancelled")
                break
            
            except Exception as e:
                logger.error(f"❌ Error in polling loop: {e}")
                await asyncio.sleep(30)  # Error backoff
    
    async def stop_polling(self):
        """Stop continuous polling"""
        logger.info("⏹️ Stopping news ingestion layer...")
        self.is_polling = False
        
        if self.poll_task:
            self.poll_task.cancel()
            try:
                await self.poll_task
            except asyncio.CancelledError:
                pass
        
        await self.nse_poller.close()
        logger.info("[STOPPED] News ingestion layer stopped")
    
    def get_news_queue(self, max_items: Optional[int] = None) -> List[NormalizedNews]:
        """
        Get items from news queue (non-destructive)
        
        Args:
            max_items: Max items to return (None = all)
        
        Returns:
            List of news items
        """
        if max_items:
            return self.news_queue[:max_items]
        return self.news_queue.copy()
    
    def pop_news_queue(self, max_items: Optional[int] = None) -> List[NormalizedNews]:
        """
        Pop items from news queue (destructive)
        
        Args:
            max_items: Max items to pop (None = all)
        
        Returns:
            List of news items (removed from queue)
        """
        if max_items:
            items = self.news_queue[:max_items]
            self.news_queue = self.news_queue[max_items:]
        else:
            items = self.news_queue.copy()
            self.news_queue.clear()
        
        return items
    
    def trigger_burst_mode(self, symbol: str, quote: Dict):
        """
        Manually trigger burst mode for a symbol
        (Called when broker stream detects unusual activity)
        """
        if self.burst_detector.should_burst_poll(symbol, quote):
            self.stats['burst_triggers'] += 1
            logger.warning(f"[BURST] BURST MODE: Switching to {self.burst_poll_interval}s polling")
    
    def _save_news_to_db(self, news_items: List[NormalizedNews]):
        """
        Save news items to database for cross-process access
        
        Args:
            news_items: List of normalized news items
        """
        if not news_items:
            return
        
        try:
            db = SessionLocal()
            saved_count = 0
            
            for news in news_items:
                try:
                    # Check if already exists
                    existing = db.query(NewsItem).filter(
                        NewsItem.news_id == news.news_id
                    ).first()
                    
                    if existing:
                        continue  # Skip duplicates
                    
                    # Create new news item
                    db_news = NewsItem(
                        news_id=news.news_id,
                        source=news.source,
                        exchange=news.exchange,
                        symbol=news.symbol,
                        headline=news.headline,
                        description=news.description,
                        category=news.category.value if news.category else None,
                        timestamp=news.timestamp,
                        detected_at=news.detected_at,
                        attachment_url=news.attachment_url,
                        raw_data=json.dumps(news.raw_data) if news.raw_data else None
                    )
                    
                    db.add(db_news)
                    saved_count += 1
                
                except Exception as e:
                    logger.warning(f"Error saving news item {news.news_id}: {e}")
                    continue
            
            # Commit all at once
            if saved_count > 0:
                db.commit()
                logger.info(f"💾 Saved {saved_count} news items to database")
            
            # Cleanup old news (keep last 7 days)
            cutoff = datetime.now() - timedelta(days=7)
            deleted = db.query(NewsItem).filter(
                NewsItem.timestamp < cutoff
            ).delete()
            
            if deleted > 0:
                db.commit()
                logger.info(f"🗑️ Cleaned up {deleted} old news items")
        
        except Exception as e:
            logger.error(f"❌ Error saving news to database: {e}")
            db.rollback()
        
        finally:
            db.close()
    
    def get_stats(self) -> Dict:
        """Get ingestion statistics"""
        return {
            **self.stats,
            'queue_size': len(self.news_queue),
            'last_poll': self.last_poll_time.isoformat() if self.last_poll_time else None,
            'is_polling': self.is_polling,
            'burst_symbols': self.burst_detector.get_burst_symbols(),
            'nse_health': self.nse_poller.get_health_status()
        }


# Singleton instance
_ingestion_layer = None


def get_news_ingestion_layer() -> NewsIngestionLayer:
    """Get singleton news ingestion layer"""
    global _ingestion_layer
    if _ingestion_layer is None:
        _ingestion_layer = NewsIngestionLayer()
    return _ingestion_layer


async def test_ingestion_layer():
    """Test news ingestion layer"""
    ingestion = get_news_ingestion_layer()
    
    try:
        print("\n[START] Starting news ingestion layer...")
        
        # Start polling
        poll_task = asyncio.create_task(ingestion.start_polling())
        
        # Let it run for 2 minutes
        await asyncio.sleep(120)
        
        # Check queue
        print("\n[STATS] Ingestion Statistics:")
        stats = ingestion.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        # Get news items
        news_items = ingestion.get_news_queue(max_items=5)
        print(f"\n📰 Latest {len(news_items)} news items:")
        for news in news_items:
            print(f"   [{news.symbol}] {news.headline[:60]}...")
        
        # Stop
        await ingestion.stop_polling()
        poll_task.cancel()
    
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        await ingestion.stop_polling()


if __name__ == "__main__":
    # Run test
    asyncio.run(test_ingestion_layer())
