#!/usr/bin/env python3
"""Add TATASTEEL trade to database manually"""
import sys
from datetime import datetime, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Trade, TradeStatus, TradeDirection

# Database URL
DATABASE_URL = "sqlite:///./autotrade.db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# TATASTEEL trade details from today
# Entry: 190 shares @ Rs208.93
# Exit: Rs208.84  
# Loss: -Rs17.10 realized + ~Rs40 brokerage = -Rs57 total

# Create entry trade
entry_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
exit_time = datetime.now().replace(hour=15, minute=20, second=0, microsecond=0)

trade = Trade(
    symbol="TATASTEEL",
    direction=TradeDirection.LONG,
    quantity=190,
    entry_price=208.93,
    entry_timestamp=entry_time,
    exit_price=208.84,
    exit_timestamp=exit_time,
    stop_price=208.93 * 0.98,  # 2% below entry
    target_price=208.93 * 1.03,      # 3% above entry
    risk_amount=208.93 * 190 * 0.02,  # 2% risk
    strategy_name="mean_reversion",
    status=TradeStatus.CLOSED,
    exit_reason="eod_cutoff",
    notes="Historical trade - manually added after database fix",
    created_at=entry_time,
    updated_at=exit_time
)

# Calculate P&L
trade.realized_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
trade.charges = 40.0  # Approximate brokerage
trade.net_pnl = trade.realized_pnl - trade.charges

print(f"Adding TATASTEEL trade to database:")
print(f"  Symbol: {trade.symbol}")
print(f"  Quantity: {trade.quantity}")
print(f"  Entry: Rs{trade.entry_price} @ {entry_time.strftime('%H:%M:%S')}")
print(f"  Exit: Rs{trade.exit_price} @ {exit_time.strftime('%H:%M:%S')}")
print(f"  Realized P&L: Rs{trade.realized_pnl:.2f}")
print(f"  Charges: Rs{trade.charges:.2f}")
print(f"  Net P&L: Rs{trade.realized_pnl - trade.charges:.2f}")
print(f"  Status: {trade.status.value}")

# Add to database
session.add(trade)
session.commit()
session.refresh(trade)

print(f"\n✅ Trade added successfully with ID: {trade.id}")

# Verify
verify = session.query(Trade).filter(Trade.id == trade.id).first()
if verify:
    print(f"✅ Verification passed - Trade exists in database")
else:
    print(f"❌ Verification failed - Trade not found after commit")

session.close()
