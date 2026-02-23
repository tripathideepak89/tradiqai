"""Verify database and broker sync status"""
import asyncio
from database import SessionLocal
from models import Trade, TradeStatus
from brokers.factory import BrokerFactory
from config import settings
from datetime import datetime

async def verify_sync():
    print("\n" + "="*80)
    print("🔍 DATABASE & BROKER SYNC VERIFICATION")
    print("="*80 + "\n")
    
    # Check database
    db = SessionLocal()
    today = datetime(2026, 2, 20, 0, 0, 0)
    all_trades = db.query(Trade).filter(Trade.entry_timestamp >= today).all()
    open_trades = [t for t in all_trades if t.status == TradeStatus.OPEN]
    closed_trades = [t for t in all_trades if t.status == TradeStatus.CLOSED]
    
    print("📊 DATABASE STATUS:")
    print("-" * 80)
    print(f"   Total trades today: {len(all_trades)}")
    print(f"   Open trades: {len(open_trades)}")
    print(f"   Closed trades: {len(closed_trades)}")
    
    if closed_trades:
        total_pnl = sum([t.realized_pnl for t in closed_trades if t.realized_pnl])
        print(f"   Today's P&L: Rs{total_pnl:+.2f}")
    
    # Check broker
    print("\n📊 BROKER STATUS:")
    print("-" * 80)
    
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    broker = BrokerFactory.create_broker(settings.broker, broker_config)
    
    if await broker.connect():
        positions = await broker.get_positions()
        open_positions = [p for p in positions if p.quantity != 0]
        
        print(f"   Open positions: {len(open_positions)}")
        
        if open_positions:
            print("\n   ⚠️  Positions in broker:")
            for pos in open_positions:
                print(f"      • {pos.symbol}: {pos.quantity} @ Rs{pos.average_price:.2f}")
        else:
            print("   ✅ No open positions in broker")
    
    # Sync verification
    print("\n\n" + "="*80)
    print("✅ SYNC STATUS")
    print("="*80)
    
    if len(open_trades) == 0 and len(open_positions) == 0:
        print("\n🎉 PERFECT SYNC!")
        print("   ✓ Database: 0 open trades")
        print("   ✓ Broker: 0 open positions")
        print("   ✓ All positions properly closed and recorded")
        print(f"\n💰 Today's realized P&L: Rs{total_pnl:+.2f}")
        print("\n⚠️  NO SYNC NEEDED - Everything is already synchronized!")
    else:
        print("\n⚠️  SYNC MISMATCH DETECTED!")
        print(f"   Database open trades: {len(open_trades)}")
        print(f"   Broker open positions: {len(open_positions)}")
        print("\n   → Sync recommended to resolve discrepancies")
    
    print("\n" + "="*80 + "\n")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(verify_sync())
