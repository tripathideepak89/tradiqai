"""Check database trade status"""
from database import SessionLocal
from models import Trade, TradeStatus

db = SessionLocal()

print("\n" + "="*70)
print("📊 DATABASE TRADE STATUS")
print("="*70 + "\n")

trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()

print(f"Found {len(trades)} OPEN trades in database:\n")

for trade in trades:
    print(f"   • {trade.symbol}: {trade.quantity} shares @ Rs{trade.entry_price:.2f}")
    print(f"     Direction: {trade.direction.value}")
    print(f"     Entry Time: {trade.entry_timestamp}")
    print(f"     Status: {trade.status.value}")
    print()

print("="*70 + "\n")

db.close()
