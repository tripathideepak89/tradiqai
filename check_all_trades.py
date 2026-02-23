"""Check all trades in database"""
from database import SessionLocal
from models import Trade, TradeStatus
from datetime import datetime

db = SessionLocal()

print("\n" + "="*80)
print("📊 ALL TRADES IN DATABASE (Today - Feb 20, 2026)")
print("="*80 + "\n")

# Get all trades from today
today = datetime(2026, 2, 20, 0, 0, 0)
all_trades = db.query(Trade).filter(Trade.entry_timestamp >= today).all()

print(f"Total trades today: {len(all_trades)}\n")

# Group by status
open_trades = [t for t in all_trades if t.status == TradeStatus.OPEN]
closed_trades = [t for t in all_trades if t.status == TradeStatus.CLOSED]

print(f"📈 OPEN TRADES: {len(open_trades)}")
for trade in open_trades:
    print(f"   • {trade.symbol}: {trade.quantity} @ Rs{trade.entry_price:.2f}")
    print(f"     Entry: {trade.entry_timestamp}")

print(f"\n✅ CLOSED TRADES: {len(closed_trades)}")
total_pnl = 0
for trade in closed_trades:
    pnl = trade.realized_pnl if trade.realized_pnl else 0
    total_pnl += pnl
    print(f"   • {trade.symbol}: {trade.quantity} @ Rs{trade.entry_price:.2f} → Rs{trade.exit_price:.2f}")
    print(f"     P&L: Rs{pnl:+.2f} | Exit: {trade.exit_timestamp}")

print(f"\n💰 TOTAL P&L: Rs{total_pnl:+.2f}")
print("="*80 + "\n")

db.close()
