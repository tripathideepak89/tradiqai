#!/usr/bin/env python3
"""
Verify dashboard news feed is working
"""
import sqlite3
from datetime import datetime, timedelta

print("=" * 80)
print("DASHBOARD NEWS FEED VERIFICATION")
print("=" * 80)

# Connect to database
conn = sqlite3.connect('autotrade.db')
cursor = conn.cursor()

# Get total news count
cursor.execute('SELECT COUNT(*) FROM news_items')
total_count = cursor.fetchone()[0]

print(f"\n✅ Total news items in database: {total_count}")

if total_count == 0:
    print("\n❌ NEWS FEED IS EMPTY")
    print("\n   To fix this, run:")
    print("   python populate_sample_news.py")
else:
    # Get recent news (last 24 hours)
    cutoff = datetime.now() - timedelta(hours=24)
    cursor.execute('''
        SELECT symbol, headline, timestamp, impact_score, direction, category
        FROM news_items 
        WHERE timestamp >= ?
        ORDER BY timestamp DESC 
        LIMIT 10
    ''', (cutoff.isoformat(),))
    
    recent_news = cursor.fetchall()
    
    print(f"\n📰 News items from last 24 hours: {len(recent_news)}")
    print("\n" + "=" * 80)
    print("DASHBOARD WILL DISPLAY:")
    print("=" * 80)
    
    for i, news in enumerate(recent_news, 1):
        symbol, headline, timestamp, score, direction, category = news
        print(f"\n{i}. [{symbol}] Score: {score}/100 | {direction} | {category}")
        print(f"   {headline}")
        print(f"   {timestamp}")
    
    if len(recent_news) < total_count:
        print(f"\n   ... and {total_count - len(recent_news)} older items")

conn.close()

print("\n" + "=" * 80)
print("HOW TO VIEW THE DASHBOARD:")
print("=" * 80)
print("\n1. Start the dashboard server:")
print("   python dashboard.py")
print("\n2. Open your browser:")
print("   http://localhost:8000")
print("\n3. The news feed should appear in the dashboard")
print("\n✅ Dashboard news feed is ready!")
print("=" * 80)
