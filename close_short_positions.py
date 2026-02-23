"""Buy back shares to close SHORT positions"""
import asyncio
from brokers.factory import BrokerFactory
from brokers.base import TransactionType, OrderType
from config import settings
from utils.timezone import now_ist

async def close_short_positions():
    """Buy back shares to close SHORT positions created by double-sell"""
    
    print("\n" + "="*70)
    print("🔄 CLOSING SHORT POSITIONS")
    print("="*70 + "\n")
    
    print(f"🇮🇳 IST Time: {now_ist().strftime('%Y-%m-%d %H:%M:%S IST')}\n")
    
    # Initialize broker
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    
    broker = BrokerFactory.create_broker(settings.broker, broker_config)
    
    if not await broker.connect():
        print("❌ Failed to connect to broker\n")
        return
    
    print("✅ Broker connected\n")
    
    # Get current positions to verify SHORT positions
    print("🔍 Checking current positions...\n")
    positions = await broker.get_positions()
    
    short_positions = [p for p in positions if p.quantity < 0]
    
    if not short_positions:
        print("✅ No SHORT positions found - all positions closed!\n")
        return
    
    print(f"Found {len(short_positions)} SHORT positions:\n")
    for pos in short_positions:
        print(f"   • {pos.symbol}: {pos.quantity} shares (need to BUY {abs(pos.quantity)})")
    
    print(f"\n{'='*70}")
    print("⚠️  PLACING BUY ORDERS TO CLOSE SHORT POSITIONS")
    print(f"{'='*70}\n")
    
    # Place BUY orders to close SHORT positions
    for pos in short_positions:
        symbol = pos.symbol
        quantity = abs(pos.quantity)  # Make positive
        
        try:
            print(f"📊 {symbol}: Buying {quantity} shares @ MARKET...")
            
            order_result = await broker.place_order(
                symbol=symbol,
                transaction_type=TransactionType.BUY,
                quantity=quantity,
                order_type=OrderType.MARKET,
                product="MIS"
            )
            
            if order_result and order_result.order_id:
                print(f"   ✅ BUY order placed successfully")
                print(f"   📝 Order ID: {order_result.order_id}\n")
            else:
                print(f"   ❌ Failed to place order - no order ID returned\n")
                
        except Exception as e:
            print(f"   ❌ Error placing order: {e}\n")
    
    print(f"{'='*70}")
    print("✅ SHORT POSITION CLOSURE COMPLETE")
    print(f"{'='*70}\n")
    
    print("📝 Next steps:")
    print("   1. Wait 2-3 minutes for orders to execute")
    print("   2. Verify all positions closed in broker")
    print("   3. Update database with final P&L\n")

if __name__ == "__main__":
    asyncio.run(close_short_positions())
