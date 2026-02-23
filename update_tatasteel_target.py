"""Update TATASTEEL target to realistic level"""
from database import SessionLocal
from models import Trade, TradeStatus

db = SessionLocal()

# Get TATASTEEL positions
positions = db.query(Trade).filter(
    Trade.symbol == "TATASTEEL",
    Trade.status == TradeStatus.OPEN
).all()

if not positions:
    print("No TATASTEEL positions found")
else:
    print(f"Updating {len(positions)} TATASTEEL positions\n")
    
    for trade in positions:
        old_target = trade.target_price
        entry = trade.entry_price
        stop = trade.stop_price
        
        # Calculate new realistic target: 1.5% profit from entry
        # (since stock already moved 2.6% from open before entry)
        new_target = entry * 1.015  # 1.5% gain
        
        # Update target
        trade.target_price = new_target
        
        print(f"Trade ID {trade.id}:")
        print(f"  Entry: Rs {entry:.2f}")
        print(f"  Old Target: Rs {old_target:.2f} (+{((old_target-entry)/entry*100):.2f}%)")
        print(f"  New Target: Rs {new_target:.2f} (+{((new_target-entry)/entry*100):.2f}%)")
        print(f"  Stop: Rs {stop:.2f} (-{((entry-stop)/entry*100):.2f}%)")
        print()
    
    db.commit()
    
    # Calculate totals
    total_qty = sum(t.quantity for t in positions)
    avg_entry = sum(t.quantity * t.entry_price for t in positions) / total_qty
    new_avg_target = sum(t.quantity * t.target_price for t in positions) / total_qty
    
    expected_profit = (new_avg_target - avg_entry) * total_qty
    
    print(f"\nTotal Position: {total_qty} shares @ Rs {avg_entry:.2f}")
    print(f"New Target: Rs {new_avg_target:.2f}")
    print(f"Expected Profit: Rs {expected_profit:.2f} (+{((new_avg_target-avg_entry)/avg_entry*100):.2f}%)")
    print("\n✓ Targets updated to realistic levels!")

db.close()
