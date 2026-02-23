"""Place sell orders for TATASTEEL profit booking"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Trade, TradeStatus
from brokers.groww import GrowwBroker
from brokers.base import TransactionType, OrderType
from config import settings

async def place_exit_orders():
    db = SessionLocal()
    
    # Configure broker
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "jwt_token": settings.groww_jwt_token
    }
    broker = GrowwBroker(broker_config)
    
    # Get TATASTEEL positions
    positions = db.query(Trade).filter(
        Trade.symbol == "TATASTEEL",
        Trade.status == TradeStatus.OPEN
    ).all()
    
    if not positions:
        print("No open TATASTEEL positions found")
        return
    
    print(f"Found {len(positions)} TATASTEEL positions:\n")
    
    total_qty = 0
    for trade in positions:
        print(f"Trade ID {trade.id}: {trade.quantity} shares @ Rs {trade.entry_price}")
        print(f"  Stop: Rs {trade.stop_price} | Target: Rs {trade.target_price}")
        total_qty += trade.quantity
    
    avg_entry = sum(t.quantity * t.entry_price for t in positions) / total_qty
    print(f"\nTotal: {total_qty} shares @ Rs {avg_entry:.2f} avg\n")
    
    # Get current price
    try:
        quote = await broker.get_quote("TATASTEEL")
        current_price = quote.last_price
        current_pnl = (current_price - avg_entry) * total_qty
        current_pnl_pct = ((current_price - avg_entry) / avg_entry) * 100
        
        print(f"Current Price: Rs {current_price:.2f}")
        print(f"Unrealized P&L: Rs {current_pnl:.2f} ({current_pnl_pct:+.2f}%)\n")
        
        # Calculate exit prices
        target = positions[0].target_price
        print(f"Strategy Target: Rs {target:.2f} (+{((target - avg_entry) / avg_entry * 100):.2f}%)")
        
        # Place limit sell order at target price
        print(f"\nPlacing SELL order for {total_qty} shares @ Rs {target:.2f} (TARGET)")
        
        # Paper trading mode - just log
        if settings.paper_trading:
            print("[PAPER TRADING] Order simulated - not sent to broker")
            print(f"[PAPER] Would sell {total_qty} TATASTEEL @ Rs {target:.2f}")
        else:
            # Place actual sell order
            order = await broker.place_order(
                symbol="TATASTEEL",
                transaction_type=TransactionType.SELL,
                quantity=total_qty,
                order_type=OrderType.LIMIT,
                price=target,
                product="MIS"
            )
            print(f"Order placed: {order.order_id} - {order.status}")
            
        print("\nSuccess! Exit order placed at target price")
        print(f"Order will execute when TATASTEEL hits Rs {target:.2f}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(place_exit_orders())
