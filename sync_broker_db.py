"""Sync broker data to database and clear cache"""
import asyncio
import os
import sys
import argparse
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brokers.groww import GrowwBroker
from config import settings
from models import Trade, TradeStatus, TradeDirection, Base
from database import engine, SessionLocal

async def sync_broker_to_database():
    """Sync all broker positions to database"""
    
    print("="*80)
    print("🔄 BROKER TO DATABASE SYNC")
    print("="*80)
    
    # 1. Clear old database (backup first)
    print("\n📦 Step 1: Backing up and cleaning database...")
    
    # Create backup
    backup_path = f"autotrade_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    if os.path.exists('autotrade.db'):
        import shutil
        shutil.copy2('autotrade.db', backup_path)
        print(f"   ✓ Backup created: {backup_path}")
    
    # Drop all tables and recreate
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("   ✓ Database schema recreated (all tables cleared)")
    
    # 2. Initialize broker
    print("\n🔌 Step 2: Connecting to broker...")
    
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "api_url": settings.groww_api_url
    }
    
    broker = GrowwBroker(broker_config)
    connected = await broker.connect()
    
    if not connected:
        print("   ✗ Failed to connect to broker")
        return False
    
    print("   ✓ Connected to Groww broker")
    
    # 3. Get broker positions
    print("\n📊 Step 3: Fetching broker data...")
    
    try:
        # Fetch positions (filled trades)
        positions = await broker.get_positions()
        
        # Fetch orders (including pending)
        orders = await broker.get_orders()
        pending_orders = [o for o in orders if o.status.name == "PENDING"]
        
        if not positions and not pending_orders:
            print("   ℹ No open positions or pending orders in broker")
        else:
            print(f"   ✓ Found {len(positions)} positions and {len(pending_orders)} pending orders")
            
            # 4. Sync to database
            print("\n💾 Step 4: Syncing data to database...")
            
            db = SessionLocal()
            synced_count = 0
            
            # Sync filled positions
            for pos in positions:
                try:
                    # Determine direction
                    direction = TradeDirection.LONG if pos.quantity > 0 else TradeDirection.SHORT
                    
                    # Create trade record
                    trade = Trade(
                        symbol=pos.symbol,
                        strategy_name="manual",  # Mark as manual trade
                        direction=direction,
                        entry_price=pos.average_price,
                        quantity=abs(pos.quantity),
                        entry_timestamp=datetime.now(),  # Approximate
                        stop_price=pos.average_price * 0.98,  # 2% default SL
                        target_price=pos.average_price * 1.03,  # 3% default target
                        risk_amount=abs(pos.quantity) * pos.average_price * 0.02,
                        status=TradeStatus.OPEN,
                        broker_entry_id=f"SYNC_{pos.symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        notes=f"Synced from broker at {datetime.now().isoformat()}"
                    )
                    
                    db.add(trade)
                    synced_count += 1
                    
                    # Calculate unrealized P&L
                    current_price = pos.last_price if pos.last_price else pos.average_price
                    unrealized_pnl = (current_price - pos.average_price) * abs(pos.quantity)
                    
                    print(f"   ✓ {pos.symbol}: {abs(pos.quantity)} shares @ Rs{pos.average_price:.2f}")
                    print(f"     Current: Rs{current_price:.2f} | Unrealized P&L: Rs{unrealized_pnl:.2f}")
                    
                except Exception as e:
                    print(f"   ✗ Error syncing {pos.symbol}: {e}")
                    continue
            
            # Sync pending orders
            for order in pending_orders:
                try:
                    # Determine direction
                    direction = TradeDirection.LONG if order.transaction_type.name == "BUY" else TradeDirection.SHORT
                    
                    # Create trade record with PENDING status
                    trade = Trade(
                        symbol=order.symbol,
                        strategy_name="manual",  # Mark as manual trade
                        direction=direction,
                        entry_price=order.price,
                        quantity=order.quantity,
                        entry_timestamp=order.timestamp if order.timestamp else datetime.now(),
                        stop_price=order.price * 0.98,  # 2% default SL
                        target_price=order.price * 1.03,  # 3% default target
                        risk_amount=order.quantity * order.price * 0.02,
                        status=TradeStatus.PENDING,
                        broker_entry_id=order.order_id,
                        notes=f"Pending {order.order_type.name} order synced from broker"
                    )
                    
                    db.add(trade)
                    synced_count += 1
                    
                    print(f"   📌 {order.symbol}: {order.quantity} shares @ Rs{order.price:.2f} [{order.order_type.name}] - PENDING")
                    
                except Exception as e:
                    print(f"   ✗ Error syncing pending order {order.symbol}: {e}")
                    continue
            
            # Commit all trades
            try:
                db.commit()
                print(f"\n   ✓ Successfully synced {synced_count} items to database")
            except Exception as e:
                db.rollback()
                print(f"\n   ✗ Database commit failed: {e}")
            finally:
                db.close()
    
    except Exception as e:
        print(f"   ✗ Error fetching positions: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Get margins/capital
    print("\n💰 Step 5: Fetching account margins...")
    
    try:
        margins = await broker.get_margins()
        if margins:
            print(f"   ✓ Available Capital: Rs{margins.get('available_cash', 0):,.2f}")
            print(f"   ✓ Margin Used: Rs{margins.get('margin_used', 0):,.2f}")
            print(f"   ✓ Available Margin: Rs{margins.get('available_margin', 0):,.2f}")
    except Exception as e:
        print(f"   ✗ Error fetching margins: {e}")
    
    # 6. Disconnect
    await broker.disconnect()
    print("\n✅ Sync completed!")
    print("="*80)
    
    return True

async def verify_database():
    """Verify database has correct data"""
    
    print("\n🔍 VERIFICATION:")
    print("-"*80)
    
    db = SessionLocal()
    
    try:
        # Count trades
        total_trades = db.query(Trade).count()
        open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).count()
        
        print(f"Total trades in database: {total_trades}")
        print(f"Open positions: {open_trades}")
        
        if total_trades > 0:
            print("\nRecent trades:")
            trades = db.query(Trade).order_by(Trade.id.desc()).limit(5).all()
            for t in trades:
                print(f"  • {t.symbol}: {t.quantity} shares @ Rs{t.entry_price:.2f} ({t.status})")
        
    finally:
        db.close()
    
    print("-"*80)

async def main(force=False):
    """Main sync function"""
    
    print("\n")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║       AUTOTRADE AI - BROKER DATABASE SYNC UTILITY             ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print("\n")
    
    # Check database URL
    print(f"Database: {settings.database_url}")
    
    if "sqlite" not in settings.database_url.lower():
        print("\n⚠️  WARNING: Database is not SQLite!")
        print("This script is designed for SQLite. PostgreSQL sync not implemented.")
        if not force:
            confirm = input("\nContinue anyway? (yes/no): ")
            if confirm.lower() != "yes":
                return
    
    print("\n⚠️  This will:")
    print("  1. Backup current database")
    print("  2. Clear all database tables")
    print("  3. Fetch positions from broker")
    print("  4. Sync broker data to database")
    
    if not force:
        confirm = input("\nProceed? (yes/no): ")
        
        if confirm.lower() != "yes":
            print("\n❌ Sync cancelled")
            return
    else:
        print("\n✓ Running in force mode (--yes flag)")
        print("")
    
    # Run sync
    success = await sync_broker_to_database()
    
    if success:
        # Verify
        await verify_database()
        
        print("\n✅ Database is now synced with broker!")
        print("\nNext steps:")
        print("  1. Restart trading system: python main.py")
        print("  2. Restart dashboard: python dashboard.py")
        print("  3. Both will now use the synced database")
    else:
        print("\n❌ Sync failed. Check errors above.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync broker positions to database")
    parser.add_argument('-y', '--yes', action='store_true', 
                        help='Skip confirmation prompts')
    args = parser.parse_args()
    
    asyncio.run(main(force=args.yes))
