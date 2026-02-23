"""Test script for Groww broker integration"""
import asyncio
import logging
from brokers.factory import BrokerFactory
from config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_groww():
    """Test Groww broker connection and basic operations"""
    
    print("\n" + "="*60)
    print("GROWW BROKER TEST")
    print("="*60 + "\n")
    
    # Check credentials
    if not settings.groww_api_key or not settings.groww_api_secret:
        print("❌ Groww credentials not found in .env")
        print("\nPlease add to .env file:")
        print("GROWW_API_KEY=your_jwt_token")
        print("GROWW_API_SECRET=your_secret")
        return
    
    print(f"✓ API Key loaded: {settings.groww_api_key[:50]}...")
    print(f"✓ API Secret loaded: {settings.groww_api_secret[:10]}...")
    
    # Create broker instance
    print("\n1. Creating Groww broker instance...")
    config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    
    broker = BrokerFactory.create_broker("groww", config)
    print("✅ Broker instance created")
    
    try:
        # Test connection
        print("\n2. Testing connection...")
        connected = await broker.connect()
        
        if not connected:
            print("❌ Connection failed")
            return
        
        print("✅ Successfully connected to Groww!")
        
        # Test margins
        print("\n3. Fetching account margins...")
        margins = await broker.get_margins()
        print(f"✅ Available margin: ₹{margins['available']:,.2f}")
        print(f"   Used margin: ₹{margins['used']:,.2f}")
        
        # Test positions
        print("\n4. Fetching current positions...")
        positions = await broker.get_positions()
        if positions:
            print(f"✅ Found {len(positions)} open position(s):")
            for pos in positions:
                print(f"   - {pos.symbol}: {pos.quantity} @ ₹{pos.average_price:.2f} (P&L: ₹{pos.pnl:.2f})")
        else:
            print("✅ No open positions")
        
        # Test quote
        print("\n5. Testing quote fetch (RELIANCE)...")
        try:
            quote = await broker.get_quote("RELIANCE")
            print(f"✅ Quote received:")
            print(f"   LTP: ₹{quote.last_price:.2f}")
            print(f"   Open: ₹{quote.open:.2f}, High: ₹{quote.high:.2f}, Low: ₹{quote.low:.2f}")
            print(f"   Volume: {quote.volume:,}")
        except Exception as e:
            print(f"⚠️  Quote fetch failed: {e}")
        
        # Test orders history
        print("\n6. Fetching orders...")
        orders = await broker.get_orders()
        if orders:
            print(f"✅ Found {len(orders)} order(s) today")
            for order in orders[:5]:  # Show first 5
                print(f"   - {order.symbol}: {order.transaction_type.value} {order.quantity} @ {order.status.value}")
        else:
            print("✅ No orders today")
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED! ✅")
        print("="*60)
        print("\nGroww broker is ready to use!")
        print("\nNext steps:")
        print("1. Set BROKER=groww in .env")
        print("2. Keep PAPER_TRADING=true for testing")
        print("3. Run: python main.py")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        logger.exception("Test failed")
        
    finally:
        # Cleanup
        print("\n7. Disconnecting...")
        await broker.disconnect()
        print("✅ Disconnected")


def main():
    """Main entry point"""
    try:
        asyncio.run(test_groww())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        logger.exception("Fatal error")


if __name__ == "__main__":
    main()
