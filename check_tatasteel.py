"""Check TATASTEEL positions and place exit orders"""
import asyncio
from database import SessionLocal
from models import Trade, TradeStatus
from brokers.groww import GrowwBroker
from config import settings

async def check_and_exit():
    db = SessionLocal()
    broker = GrowwBroker()
    
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
    total_cost = 0
    
    for trade in positions:
        print(f"Trade ID {trade.id}:")
        print(f"  Quantity: {trade.quantity} shares")
        print(f"  Entry: ₹{trade.entry_price}")
        print(f"  Stop Loss: ₹{trade.stop_price}")
        print(f"  Target: ₹{trade.target_price}")
        print(f"  Broker Order ID: {trade.broker_order_id}")
        print(f"  Broker SL ID: {trade.broker_sl_id}")
        print()
        
        total_qty += trade.quantity
        total_cost += trade.quantity * trade.entry_price
    
    avg_entry = total_cost / total_qty
    print(f"Total Position: {total_qty} shares @ ₹{avg_entry:.2f} avg")
    print(f"Total Investment: ₹{total_cost:.2f}")
    print()
    
    # Get current price
    try:
        quote = await broker.get_quote("TATASTEEL")
        current_price = quote.last_price
        current_pnl = (current_price - avg_entry) * total_qty
        current_pnl_pct = ((current_price - avg_entry) / avg_entry) * 100
        
        print(f"Current Price: ₹{current_price}")
        print(f"Current P&L: ₹{current_pnl:.2f} ({current_pnl_pct:+.2f}%)")
        print()
        
        # Check if we should take profit
        target = positions[0].target_price
        stop = positions[0].stop_price
        
        print(f"Target: ₹{target:.2f} (+{((target - avg_entry) / avg_entry * 100):.2f}%)")
        print(f"Stop Loss: ₹{stop:.2f} ({((stop - avg_entry) / avg_entry * 100):.2f}%)")
        print()
        
        if current_price >= target:
            print("✅ TARGET REACHED! Consider booking profit")
        elif current_price >= avg_entry + (avg_entry * 0.015):  # 1.5% profit
            print("⚠️ In profit zone (1.5%+). Consider partial profit booking")
        elif current_price <= stop:
            print("❌ STOP LOSS HIT! Exit immediately")
        else:
            print("📊 Position within range. Hold or trail stop loss")
            
    except Exception as e:
        print(f"Error fetching current price: {e}")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(check_and_exit())
