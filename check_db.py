#!/usr/bin/env python3
"""Quick database check script"""
import sys
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# Database URL
DATABASE_URL = "sqlite:///./autotrade.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Check if tables exist
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Tables in database: {tables}")

if 'trades' in tables:
    result = session.execute("SELECT COUNT(*) FROM trades")
    count = result.scalar()
    print(f"\nTotal trades in 'trades' table: {count}")
    
    # Get all trades
    result = session.execute("SELECT * FROM trades")
    rows = result.fetchall()
    
    if rows:
        print("\nTrades:")
        for row in rows:
            print(f"  {row}")
    else:
        print("\nNo trades found in database.")
        
    # Check today's trades
    result = session.execute("""
        SELECT symbol, quantity, entry_price, status, created_at 
        FROM trades 
        WHERE DATE(created_at) = DATE('now')
    """)
    today_trades = result.fetchall()
    
    if today_trades:
        print(f"\nToday's trades: {len(today_trades)}")
        for trade in today_trades:
            print(f"  {trade}")
    else:
        print("\nNo trades for today found.")
else:
    print("\n'trades' table does not exist!")

session.close()
