"""Update database with final P&L from today's trading"""
from database import SessionLocal
from models import Trade, TradeStatus
from utils.timezone import now_ist
from datetime import datetime

db = SessionLocal()

print("\n" + "="*80)
print("📝 UPDATING DATABASE WITH FINAL P&L")
print("="*80 + "\n")

# Exit prices from first SELL (14:18 PM)
exit_prices = {
    "DABUR": 510.25,
    "NESTLEIND": 1298.50,
    "JSWSTEEL": 1250.10,
    "POWERGRID": 299.05,
    "NTPC": 372.60
}

# P&L calculations (LONG entry → SELL exit)
pnl_values = {
    "DABUR": 2.50,
    "NESTLEIND": 3.00,
    "JSWSTEEL": 3.50,
    "POWERGRID": -5.75,
    "NTPC": 7.50
}

# Get all OPEN trades
trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()

print(f"Found {len(trades)} OPEN trades in database\n")

exit_time = datetime(2026, 2, 20, 14, 18, 0)  # First exit at 14:18 PM IST

for trade in trades:
    symbol = trade.symbol
    
    if symbol in exit_prices:
        # Update trade record
        trade.exit_price = exit_prices[symbol]
        trade.exit_timestamp = exit_time
        trade.realized_pnl = pnl_values[symbol]
        trade.net_pnl = pnl_values[symbol]  # Simplified (should subtract brokerage)
        trade.status = TradeStatus.CLOSED
        trade.exit_reason = "manual"
        
        print(f"✅ Updated {symbol}:")
        print(f"   Exit: Rs{exit_prices[symbol]:.2f} @ {exit_time.strftime('%H:%M:%S')}")
        print(f"   P&L: Rs{pnl_values[symbol]:+.2f}")
        print()

# Commit changes
db.commit()

print("="*80)
print("✅ DATABASE UPDATE COMPLETE")
print("="*80)

# Verify
closed_count = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).count()
open_count = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).count()

print(f"\n📊 Database Status:")
print(f"   Closed trades: {closed_count}")
print(f"   Open trades: {open_count}")

total_pnl = db.query(Trade).filter(
    Trade.status == TradeStatus.CLOSED,
    Trade.exit_timestamp >= datetime(2026, 2, 20, 0, 0, 0)
).all()

day_pnl = sum([t.realized_pnl for t in total_pnl if t.realized_pnl])

print(f"   Today's P&L: Rs{day_pnl:+.2f}\n")

db.close()
print("="*80 + "\n")
