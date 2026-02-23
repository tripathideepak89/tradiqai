"""Test script to fetch top gainers from Groww"""
import asyncio
from brokers.groww import GrowwBroker
from config import settings

async def test_top_gainers():
    """Test fetching top gainers"""
    
    # Initialize broker
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    
    broker = GrowwBroker(broker_config)
    
    try:
        # Connect
        print("Connecting to Groww...")
        connected = await broker.connect()
        print(f"Connected: {connected}")
        
        if not connected:
            print("Failed to connect")
            return
        
        # Fetch top gainers
        print("\nFetching top 20 gainers...")
        gainers = await broker.get_top_gainers(limit=20)
        
        if gainers:
            print(f"\n✓ Found {len(gainers)} gainers:\n")
            print(f"{'Rank':<6} {'Symbol':<15} {'LTP':<10} {'Change %':<10}")
            print("=" * 50)
            
            for i, stock in enumerate(gainers, 1):
                symbol = stock.get('symbol', 'N/A')
                ltp = stock.get('ltp', 0)
                change = stock.get('day_change_percent', 0)
                print(f"{i:<6} {symbol:<15} ₹{ltp:<9.2f} {change:>+7.2f}%")
        else:
            print("❌ No gainers returned")
            
        await broker.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_top_gainers())
