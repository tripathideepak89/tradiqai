"""Quick script to check all broker orders and positions"""
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brokers.groww import GrowwBroker
from config import settings

async def main():
    print("\n" + "="*80)
    print("BROKER DATA CHECK - Orders & Positions")
    print("="*80 + "\n")
    
    # Initialize broker
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    
    broker = GrowwBroker(broker_config)
    connected = await broker.connect()
    
    if not connected:
        print("❌ Failed to connect to broker")
        return
    
    print("✓ Connected to Groww broker\n")
    
    # Get all orders
    print("📋 FETCHING ALL ORDERS (including pending)...")
    print("-"*80)
    
    orders = await broker.get_orders()
    
    if not orders:
        print("   No orders found")
    else:
        print(f"   Found {len(orders)} orders\n")
        
        for i, order in enumerate(orders, 1):
            print(f"{i}. {order.symbol}")
            print(f"   Type: {order.order_type.name} | Side: {order.transaction_type.name}")
            print(f"   Quantity: {order.quantity} | Price: Rs{order.price:.2f}")
            print(f"   Status: {order.status.name}")
            if order.filled_quantity:
                print(f"   Filled: {order.filled_quantity}/{order.quantity}")
                if order.average_price:
                    print(f"   Average Price: Rs{order.average_price:.2f}")
            print(f"   Order ID: {order.order_id}")
            if order.timestamp:
                print(f"   Time: {order.timestamp}")
            print()
    
    # Get positions
    print("\n📊 FETCHING POSITIONS...")
    print("-"*80)
    
    positions = await broker.get_positions()
    
    if not positions:
        print("   No positions found")
    else:
        print(f"   Found {len(positions)} positions\n")
        
        for i, pos in enumerate(positions, 1):
            print(f"{i}. {pos.symbol}")
            print(f"   Quantity: {pos.quantity}")
            print(f"   Average Price: Rs{pos.average_price:.2f}")
            if pos.last_price:
                pnl = (pos.last_price - pos.average_price) * pos.quantity
                print(f"   Last Price: Rs{pos.last_price:.2f}")
                print(f"   Unrealized P&L: Rs{pnl:.2f}")
            print()
    
    # Get margins
    print("\n💰 ACCOUNT MARGINS...")
    print("-"*80)
    
    try:
        response = await broker._make_request("GET", "margins/detail/user")
        
        if response.get("status") == "SUCCESS":
            payload = response.get("payload", {})
            available = payload.get("available_cash", 0)
            used = payload.get("collateral", 0)
            
            print(f"   Available Capital: Rs{available:,.2f}")
            print(f"   Margin Used: Rs{used:,.2f}")
            print(f"   Total Balance: Rs{available + used:,.2f}")
        else:
            print("   Could not fetch margin data")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
