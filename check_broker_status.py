"""Check broker positions and orders"""
import asyncio
from brokers.factory import BrokerFactory
from config import settings

async def check_broker():
    """Check current broker status"""
    print("\n" + "="*70)
    print("🔍 BROKER STATUS CHECK")
    print("="*70 + "\n")
    
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
    
    # Get positions
    print("📊 CURRENT POSITIONS:")
    print("-" * 70)
    positions = await broker.get_positions()
    
    if not positions or len(positions) == 0:
        print("   ✅ No open positions")
    else:
        for pos in positions:
            if pos.quantity != 0:
                print(f"   • {pos.symbol}: {pos.quantity} @ Rs{pos.average_price:.2f}")
                print(f"     Product: {pos.product} | LTP: Rs{pos.last_price:.2f} | P&L: Rs{pos.pnl:.2f}")
    
    # Get orders
    print("\n📋 TODAY'S ORDERS:")
    print("-" * 70)
    orders = await broker.get_orders()
    
    if not orders or len(orders) == 0:
        print("   No orders found")
    else:
        print(f"   Total orders today: {len(orders)}\n")
        
        # Show all orders
        for order in orders:
            trans_type = order.transaction_type.value if hasattr(order.transaction_type, 'value') else str(order.transaction_type)
            status = order.status.value if hasattr(order.status, 'value') else str(order.status)
            order_type = order.order_type.value if hasattr(order.order_type, 'value') else str(order.order_type)
            
            print(f"   • {order.symbol}: {trans_type.upper()} {order.quantity}")
            print(f"     Status: {status.upper()} | Type: {order_type}")
            if hasattr(order, 'average_price') and order.average_price > 0:
                print(f"     Avg Price: Rs{order.average_price:.2f}")
            if hasattr(order, 'price') and order.price > 0:
                print(f"     Order Price: Rs{order.price:.2f}")
            print(f"     Order ID: {order.order_id}")
            print()
    
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(check_broker())
