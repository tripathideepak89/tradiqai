"""Check specific stock positions"""
from models import Trade
from database import SessionLocal

db = SessionLocal()
symbols = ['HINDALCO', 'NTPC', 'COALINDIA']

print("\n" + "="*60)
print("📊 POSITIONS IN DATABASE")
print("="*60)

all_trades = db.query(Trade).filter(Trade.symbol.in_(symbols)).all()

if not all_trades:
    print("\n❌ No positions found for these stocks in database")
else:
    for t in all_trades:
        print(f"\n{t.symbol}:")
        print(f"  Status: {t.status}")
        print(f"  Side: {t.side}")
        print(f"  Quantity: {t.quantity}")
        print(f"  Entry Price: Rs{t.entry_price}")
        print(f"  Entry Time: {t.entry_timestamp}")
        if t.exit_price:
            print(f"  Exit Price: Rs{t.exit_price}")
        if t.net_pnl:
            print(f"  Net P&L: Rs{t.net_pnl:.2f}")

db.close()
print("\n" + "="*60)
