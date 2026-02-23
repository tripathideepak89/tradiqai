"""Test dashboard data retrieval"""
import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard import get_dashboard_data, init_broker

async def test():
    print("Initializing broker...")
    await init_broker()
    
    print("\nFetching dashboard data...")
    data = await get_dashboard_data()
    
    print("\n=== Account Data ===")
    print(f"Capital: ₹{data['account']['capital']:,.2f}")
    print(f"Margin Used: ₹{data['account']['margin_used']:,.2f}")
    print(f"Exposure: {data['account']['exposure']:.2f}%")
    
    print("\n=== Performance ===")
    print(f"Today P&L: ₹{data['performance']['today_pnl']:,.2f}")
    print(f"Trades: {data['performance']['trades_count']}")
    
    print("\n=== Market Status ===")
    print(f"Market Open: {data['market_open']}")
    
if __name__ == "__main__":
    asyncio.run(test())
