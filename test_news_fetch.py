#!/usr/bin/env python3
"""
Test script to manually fetch news from NSE and populate database
"""
import asyncio
import logging
from datetime import datetime, timedelta
from news_ingestion_layer import get_news_ingestion_layer
from database import SessionLocal
from models import NewsItem

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_news_fetch():
    """Test news fetching and database population"""
    
    print("=" * 80)
    print("NEWS FETCH TEST - February 23, 2026")
    print("=" * 80)
    
    # Check current database state
    db = SessionLocal()
    current_count = db.query(NewsItem).count()
    print(f"\n📊 Current news items in database: {current_count}")
    
    if current_count > 0:
        recent = db.query(NewsItem).order_by(NewsItem.timestamp.desc()).limit(3).all()
        print("\nMost recent news items:")
        for item in recent:
            print(f"  • {item.symbol:10} {item.headline[:60]}...")
            print(f"    Timestamp: {item.timestamp}")
    
    db.close()
    
    # Initialize news ingestion layer
    print("\n" + "=" * 80)
    print("INITIALIZING NEWS INGESTION LAYER")
    print("=" * 80)
    
    news_layer = get_news_ingestion_layer()
    
    # Perform one-time poll
    print("\n🔄 Fetching latest news from NSE...")
    print("   This may take 10-30 seconds...\n")
    
    try:
        new_news = await news_layer.poll_nse_once()
        
        if new_news:
            print(f"\n✅ SUCCESS: Fetched {len(new_news)} new news items")
            
            print("\n📰 Sample news items:")
            for i, news in enumerate(new_news[:5], 1):
                print(f"\n{i}. {news.symbol} - {news.source}")
                print(f"   Headline: {news.headline}")
                print(f"   Timestamp: {news.timestamp}")
                print(f"   Category: {news.category}")
                if news.attachment_url:
                    print(f"   Attachment: {news.attachment_url[:60]}...")
            
            if len(new_news) > 5:
                print(f"\n   ... and {len(new_news) - 5} more items")
            
            # Save to database
            print("\n💾 Saving to database...")
            news_layer._save_news_to_db(new_news)
            
            # Verify database
            db = SessionLocal()
            final_count = db.query(NewsItem).count()
            print(f"   Database now has {final_count} total news items")
            db.close()
            
            print("\n✅ News fetch and save SUCCESSFUL")
            
        else:
            print("\n⚠️  No new news items found")
            print("   Possible reasons:")
            print("   1. NSE API returned no announcements")
            print("   2. All items already in database (deduplication)")
            print("   3. NSE session/cookie issues")
            
            # Check NSE poller stats
            stats = news_layer.get_stats()
            print(f"\n📊 Ingestion Stats:")
            print(f"   Total fetched: {stats['total_fetched']}")
            print(f"   Total duplicates: {stats['total_duplicates']}")
            print(f"   Total new: {stats['total_new']}")
    
    except Exception as e:
        print(f"\n❌ ERROR during news fetch: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await news_layer.stop_polling()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    try:
        asyncio.run(test_news_fetch())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
