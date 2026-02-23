"""Check recent orders"""
from database import SessionLocal
from models import Trade

db = SessionLocal()

# Check recent orders for DIVISLAB, ITC, GRASIM
symbols = ['DIVISLAB', 'ITC', 'GRASIM']
recent = db.query(Trade).filter(Trade.symbol.in_(symbols)).order_by(Trade.created_at.desc()).limit(10).all()

print(f"Recent orders for {', '.join(symbols)}: {len(recent)}\n")

if recent:
    for t in recent:
        print(f"  {t.symbol}: {t.status}")
        print(f"    Qty: {t.quantity} @ ₹{t.entry_price}")
        print(f"    Created: {t.created_at}")
        print(f"    Notes: {t.notes if t.notes else 'No notes'}")
        print()
else:
    print("No orders found for these symbols")

# Also check all recent orders
print("\n--- All recent orders (last 5) ---")
all_recent = db.query(Trade).order_by(Trade.created_at.desc()).limit(5).all()
for t in all_recent:
    print(f"{t.symbol}: {t.status} - {t.quantity} shares @ ₹{t.entry_price}")

db.close()
