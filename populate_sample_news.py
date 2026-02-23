#!/usr/bin/env python3
"""
Populate database with sample news for dashboard testing
(Since NSE has no real announcements for Feb 2026)
"""
import hashlib
from datetime import datetime, timedelta
from database import SessionLocal, init_db
from models import NewsItem
import random

def generate_news_id(symbol: str, timestamp: datetime, headline: str, source: str) -> str:
    """Generate unique news ID"""
    key_string = f"{symbol}|{timestamp.isoformat()}|{headline}|{source}"
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]

def populate_sample_news():
    """Populate database with sample news items"""
    
    print("=" * 80)
    print("POPULATING DASHBOARD WITH SAMPLE NEWS")
    print("=" * 80)
    
    # Initialize database
    init_db()
    db = SessionLocal()
    
    # Check current count
    current_count = db.query(NewsItem).count()
    print(f"\n📊 Current news items: {current_count}")
    
    # Sample news for major stocks
    sample_news = [
        {
            "symbol": "RELIANCE",
            "headline": "Reliance Industries Q4 Results: Net Profit Up 18% YoY",
            "description": "Reliance Industries reported strong Q4 results with net profit reaching ₹19,299 crore...",
            "category": "earnings",
            "hours_ago": 2
        },
        {
            "symbol": "TCS",
            "headline": "TCS Announces Dividend of ₹27 per Share",
            "description": "Tata Consultancy Services Board announced final dividend of ₹27 per equity share...",
            "category": "corporate_action",
            "hours_ago": 4
        },
        {
            "symbol": "HDFCBANK",
            "headline": "HDFC Bank Announces Merger Completion Timeline",
            "description": "HDFC Bank announces completion of merger operations, integration on track...",
            "category": "corporate",
            "hours_ago": 6
        },
        {
            "symbol": "INFY",
            "headline": "Infosys Wins $500M Deal from European Bank",
            "description": "Infosys announces major deal win worth $500 million for digital transformation...",
            "category": "corporate",
            "hours_ago": 8
        },
        {
            "symbol": "ICICIBANK",
            "headline": "ICICI Bank Raises Rs5,000 Crore via Bonds",
            "description": "ICICI Bank successfully raises Rs5,000 crore through bond issuance at competitive rates...",
            "category": "corporate",
            "hours_ago": 10
        },
        {
            "symbol": "HINDUNILVR",
            "headline": "HUL to Increase Product Prices by 3-5%",
            "description": "Hindustan Unilever announces price increase across key product categories...",
            "category": "corporate",
            "hours_ago": 12
        },
        {
            "symbol": "ITC",
            "headline": "ITC Board Approves Demerger of Hotels Business",
            "description": "ITC Board of Directors approves demerger of hotels business into separate entity...",
            "category": "corporate",
            "hours_ago": 14
        },
        {
            "symbol": "SBIN",
            "headline": "SBI Reports 20% Growth in Retail Loans",
            "description": "State Bank of India reports strong growth in retail loan book for FY2026...",
            "category": "corporate",
            "hours_ago": 16
        },
        {
            "symbol": "BHARTIARTL",
            "headline": "Bharti Airtel 5G Rollout Reaches 500 Cities",
            "description": "Bharti Airtel announces completion of 5G rollout in 500 cities across India...",
            "category": "corporate",
            "hours_ago": 18
        },
        {
            "symbol": "AXISBANK",
            "headline": "Axis Bank Q4 NII Grows 15% YoY",
            "description": "Axis Bank reports Net Interest Income growth of 15% year-on-year in Q4FY26...",
            "category": "earnings",
            "hours_ago": 20
        },
        {
            "symbol": "KOTAKBANK",
            "headline": "Kotak Mahindra Bank Buyback Announcement",
            "description": "Kotak Mahindra Bank Board approves buyback of equity shares worth Rs3,000 crore...",
            "category": "corporate_action",
            "hours_ago": 22
        },
        {
            "symbol": "LT",
            "headline": "L&T Bags Rs12,000 Crore Infrastructure Project",
            "description": "Larsen & Toubro wins major infrastructure project worth Rs12,000 crore from government...",
            "category": "corporate",
            "hours_ago": 24
        },
        {
            "symbol": "ASIANPAINT",
            "headline": "Asian Paints Expands Manufacturing Capacity",
            "description": "Asian Paints announces new manufacturing facility in Gujarat with investment of Rs500 crore...",
            "category": "corporate",
            "hours_ago": 26
        },
        {
            "symbol": "MARUTI",
            "headline": "Maruti Suzuki Sales Surge 22% in February",
            "description": "Maruti Suzuki India reports 22% growth in domestic sales for February 2026...",
            "category": "corporate",
            "hours_ago": 28
        },
        {
            "symbol": "TITAN",
            "headline": "Titan Company Q4 Revenue Up 25%",
            "description": "Titan Company reports strong Q4 performance with 25% revenue growth across segments...",
            "category": "earnings",
            "hours_ago": 30
        }
    ]
    
    # Generate news items
    now = datetime.now()
    added_count = 0
    
    for news_data in sample_news:
        timestamp = now - timedelta(hours=news_data['hours_ago'])
        
        news_id = generate_news_id(
            news_data['symbol'],
            timestamp,
            news_data['headline'],
            'NSE'
        )
        
        # Check if exists
        existing = db.query(NewsItem).filter(NewsItem.news_id == news_id).first()
        if existing:
            continue
        
        # Create news item
        news_item = NewsItem(
            news_id=news_id,
            source='NSE',
            exchange='NSE',
            symbol=news_data['symbol'],
            headline=news_data['headline'],
            description=news_data['description'],
            category=news_data['category'],
            timestamp=timestamp,
            detected_at=timestamp,
            impact_score=random.randint(60, 90),
            direction=random.choice(['BULLISH', 'NEUTRAL', 'BEARISH']),
            action='WATCH'
        )
        
        db.add(news_item)
        added_count += 1
    
    db.commit()
    
    # Verify
    final_count = db.query(NewsItem).count()
    print(f"\n✅ Added {added_count} sample news items")
    print(f"📊 Total news items in database: {final_count}")
    
    # Show recent items
    recent = db.query(NewsItem).order_by(NewsItem.timestamp.desc()).limit(5).all()
    print("\n📰 Recent news in dashboard:")
    for item in recent:
        print(f"\n   {item.symbol} - {item.impact_score}/100 [{item.direction}]")
        print(f"   {item.headline}")
        print(f"   {item.timestamp.strftime('%b %d, %Y %I:%M %p')}")
    
    db.close()
    
    print("\n" + "=" * 80)
    print("✅ Dashboard news feed is now populated!")
    print("   Refresh your dashboard to see the news items")
    print("=" * 80)

if __name__ == '__main__':
    try:
        populate_sample_news()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
