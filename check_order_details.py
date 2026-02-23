"""Check detailed order information including rejection reasons"""
import asyncio
from brokers.factory import BrokerFactory
from config import settings

async def check_orders():
    print("\n" + "="*80)
    print(" 🔍 DETAILED ORDER ANALYSIS")
    print("="*80 + "\n")
    
    # Initialize broker
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    broker = BrokerFactory.create_broker(settings.broker, broker_config)
    
    if not await broker.connect():
        print("❌ Failed to connect\n")
        return
    
    orders = await broker.get_orders()
    
    if not orders:
        print("No orders found\n")
        return
    
    print(f"Total orders: {len(orders)}\n")
    
    # Group by status
    by_status = {}
    for order in orders:
        status = order.status.value
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(order)
    
    for status, status_orders in by_status.items():
        print(f"\n{'='*80}")
        print(f"Status: {status.upper()} ({len(status_orders)} orders)")
        print(f"{'='*80}\n")
        
        for i, order in enumerate(status_orders, 1):
            print(f"{i}. {order.symbol}: {order.transaction_type.value.upper()} {order.quantity} @ {order.order_type.value.upper()}")
            
            # Show filled vs pending
            filled = order.filled_quantity if hasattr(order, 'filled_quantity') else 0
            print(f"   Filled: {filled}/{order.quantity}")
            
            # Show prices
            if hasattr(order, 'average_price') and order.average_price > 0:
                print(f"   Avg Price: Rs{order.average_price:.2f}")
            if hasattr(order, 'price') and order.price > 0:
                print(f"   Order Price: Rs{order.price:.2f}")
            
            # Show rejection/error message
            if hasattr(order, 'message') and order.message:
                print(f"   ⚠️  Message: {order.message}")
            
            # Show timestamp
            if hasattr(order, 'timestamp'):
                print(f"   Time: {order.timestamp}")
            
            print(f"   Order ID: {order.order_id}")
            print()
    
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(check_orders())
