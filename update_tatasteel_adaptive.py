"""Update TATASTEEL targets to new adaptive strategy"""
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
    print(f"Updating {len(positions)} TATASTEEL positions with adaptive targets\n")
    print("Stock moved +2.6% before entry → MODERATE target (+1.5% from entry)\n")
    
    total_qty = 0
    total_cost = 0
    
    for trade in positions:
        old_target = trade.target_price
        entry = trade.entry_price
        stop = trade.stop_price
        
        # MODERATE target: +1.5% from entry (stock already moved 2.6%)
        # This expects +4.1% total move from open (realistic)
        new_target = entry * 1.015  # +1.5%
        
        # Update target
        trade.target_price = new_target
        
        total_qty += trade.quantity
        total_cost += trade.quantity * entry
        
        print(f"Trade ID {trade.id}:")
        print(f"  Entry: Rs{entry:.2f}")
        print(f"  Stop: Rs{stop:.2f} (-2.0%)")
        print(f"  Old Target: Rs{old_target:.2f} (+{((old_target/entry - 1)*100):.1f}%)")
        print(f"  New Target: Rs{new_target:.2f} (+1.5%) ← MODERATE")
        print(f"  Reason: Stock moved +2.6% before entry")
        print()
    
    # Commit changes
    db.commit()
    
    avg_entry = total_cost / total_qty
    avg_target = avg_entry * 1.015
    expected_profit = (avg_target - avg_entry) * total_qty
    
    print("=" * 50)
    print(f"Total Position: {total_qty} shares @ Rs{avg_entry:.2f} avg")
    print(f"Total Investment: Rs{total_cost:.2f}")
    print(f"Target: Rs{avg_target:.2f} (+1.5% = +4.1% total from open)")
    print(f"Expected Profit: Rs{expected_profit:.2f}")
    print()
    print("✓ Targets updated to MODERATE adaptive strategy!")
    print("  (Conservative for late entries, realistic expectations)")

db.close()
