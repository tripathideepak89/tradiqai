"""Simple position check - no broker needed"""
from database import SessionLocal
from models import Trade, TradeStatus

db = SessionLocal()

# Get TATASTEEL positions
positions = db.query(Trade).filter(
    Trade.symbol == "TATASTEEL",
    Trade.status == TradeStatus.OPEN
).all()

if not positions:
    print("No open TATASTEEL positions")
else:
    print(f"TATASTEEL Positions: {len(positions)}\n")
    
    total_qty = 0
    total_cost = 0
    
    for t in positions:
        print(f"Trade ID {t.id}:")
        print(f"  Qty: {t.quantity} shares")
        print(f"  Entry: Rs {t.entry_price:.2f}")
        print(f"  Stop Loss: Rs {t.stop_price:.2f}")
        print(f"  Target: Rs {t.target_price:.2f}")
        print(f"  Broker Order: {t.broker_order_id}")
        print()
        
        total_qty += t.quantity
        total_cost += t.quantity * t.entry_price
    
    avg = total_cost / total_qty
    target = positions[0].target_price
    stop = positions[0].stop_price
    
    print(f"Total Position: {total_qty} shares")
    print(f"Average Entry: Rs {avg:.2f}")
    print(f"Total Investment: Rs {total_cost:.2f}")
    print(f"\nTarget: Rs {target:.2f} (+{((target-avg)/avg*100):.2f}%)")
    print(f"Stop: Rs {stop:.2f} ({((stop-avg)/avg*100):.2f}%)")

db.close()
