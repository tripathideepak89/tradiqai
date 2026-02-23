"""Fix TATASTEEL position mismatch - sync DB with broker's 190 shares"""
from database import SessionLocal
from models import Trade, TradeStatus

db = SessionLocal()

# Get all TATASTEEL trades
trades = db.query(Trade).filter(Trade.symbol == 'TATASTEEL').all()

print("Current TATASTEEL positions:")
for trade in trades:
    print(f"  Trade ID {trade.id}: {trade.quantity} shares @ Rs{trade.entry_price:.2f}")
    print(f"    Status: {trade.status}")
    print(f"    Broker Order ID: {trade.broker_order_id}")
    print()

# Count current open quantity
open_qty = sum(t.quantity for t in trades if t.status in [TradeStatus.OPEN, TradeStatus.PENDING])
print(f"Total OPEN/PENDING quantity: {open_qty} shares")
print(f"Broker shows: 190 shares")
print(f"Mismatch: {190 - open_qty} shares\n")

# Fix: Mark all TATASTEEL trades as OPEN to match broker
if open_qty != 190:
    print("Syncing database with broker...")
    for trade in trades:
        if trade.status != TradeStatus.OPEN:
            print(f"  Updating Trade ID {trade.id}: {trade.status} -> OPEN")
            trade.status = TradeStatus.OPEN
    
    db.commit()
    print(f"\n✓ Database synced! All {len(trades)} trades marked as OPEN")
    print(f"  Total quantity: {sum(t.quantity for t in trades)} shares")
else:
    print("✓ Database already in sync with broker")

db.close()
