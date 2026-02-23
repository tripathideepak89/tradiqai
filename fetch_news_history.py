#!/usr/bin/env python3
"""
Fetch news from NSE for last 7 days to populate dashboard
"""
import asyncio
import logging
from datetime import datetime, timedelta
from news_ingestion_layer import get_news_ingestion_layer
from nse_announcements_poller import get_nse_poller
from database import SessionLocal
from models import NewsItem

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def fetch_news_last_week():
    """Fetch news from last 7 days"""
    
    print("=" * 80)
    print("FETCHING NEWS FROM LAST 7 DAYS")
    print("=" * 80)
    
    # Calculate date range
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    print(f"\n📅 Date Range:")
    print(f"   From: {week_ago.strftime('%d-%b-%Y')}")
    print(f"   To:   {today.strftime('%d-%b-%Y')}")
    
    # Initialize NSE poller
    nse_poller = get_nse_poller()
    await nse_poller.initialize()
    
    print("\n🔄 Fetching announcements from NSE...")
    
    try:
        # Fetch for each day in the last week
        all_announcements = []
        
        for i in range(8):
            date = today - timedelta(days=i)
            date_str = date.strftime('%d-%b-%Y')
            
            print(f"\n   Checking {date_str}...", end=" ")
            
            announcements = await nse_poller.fetch_announcements(
                from_date=date_str,
                to_date=date_str
            )
            
            if announcements:
                print(f"✅ Found {len(announcements)} announcements")
                all_announcements.extend(announcements)
            else:
                print("⚪ No announcements")
        
        print(f"\n📊 Total announcements fetched: {len(all_announcements)}")
        
        if all_announcements:
            # Process and save via news ingestion layer
            print("\n📰 Processing and saving to database...")
            
            news_layer = get_news_ingestion_layer()
            
            # Manually normalize and save each announcement
            normalized_news = []
            for raw in all_announcements:
                normalized = news_layer.normalize_nse_announcement(raw)
                if normalized and not news_layer.deduplicator.is_duplicate(normalized.news_id):
                    normalized_news.append(normalized)
                    news_layer.deduplicator.mark_seen(normalized.news_id)
            
            print(f"   Normalized: {len(normalized_news)} unique items")
            
            if normalized_news:
                news_layer._save_news_to_db(normalized_news)
                
                # Verify
                db = SessionLocal()
                total_count = db.query(NewsItem).count()
                db.close()
                
                print(f"\n✅ SUCCESS: Database now has {total_count} news items")
                
                # Show samples
                db = SessionLocal()
                samples = db.query(NewsItem).order_by(NewsItem.timestamp.desc()).limit(5).all()
                print("\n📰 Recent news items:")
                for item in samples:
                    print(f"   • {item.symbol:12} {item.headline[:60]}...")
                    print(f"     {item.timestamp.strftime('%d-%b-%Y %H:%M')} | {item.category or 'N/A'}")
                db.close()
            else:
                print("\n⚠️  All announcements were duplicates (already in database)")
        
        else:
            print("\n⚠️  NSE returned no announcements for the last 7 days")
            print("   This could mean:")
            print("   • NSE API is not providing data")
            print("   • No corporate announcements during this period")
            print("   • API endpoint or query parameters need adjustment")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await nse_poller.close()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    try:
        asyncio.run(fetch_news_last_week())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
