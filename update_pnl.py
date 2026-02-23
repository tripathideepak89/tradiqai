"""Update P&L for exited positions"""
import asyncio
from datetime import datetime
from database import SessionLocal
from models import Trade, TradeStatus, TradeDirection
from brokers.factory import BrokerFactory
from config import settings
from utils.timezone import now_ist, format_ist

async def update_pnl():
    """Fetch exit prices from broker and update P&L"""
    print(f"\n{'='*70}")
    print(f"💰 P&L CALCULATION & UPDATE")
    print(f"{'='*70}\n")
    print(f"🇮🇳 IST Time: {format_ist(now_ist())}")
    print(f"📅 Date: {now_ist().date()}\n")
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Initialize broker
        broker_config = {
            "api_key": settings.groww_api_key,
            "api_secret": settings.groww_api_secret,
            "api_url": settings.groww_api_url
        }
        broker = BrokerFactory.create_broker(settings.broker, broker_config)
        
        if not await broker.connect():
            print("❌ Failed to connect to broker\n")
            return
        
        print("✅ Broker connected\n")
        
        # Fetch current positions from broker
        print("🔍 Fetching positions from broker...\n")
        broker_positions = await broker.get_positions()
        
        # Get all open positions from database
        open_trades = db.query(Trade).filter(
            Trade.status == TradeStatus.OPEN
        ).all()
        
        if not open_trades:
            print("✅ No open positions in database\n")
            return
        
        print(f"📊 Found {len(open_trades)} positions in database:\n")
        
        total_pnl = 0.0
        updated_count = 0
        
        for trade in open_trades:
            print(f"{'─'*70}")
            print(f"📈 {trade.symbol}")
            print(f"{'─'*70}")
            print(f"   Entry: {trade.quantity} shares @ Rs{trade.entry_price:.2f}")
            print(f"   Direction: {trade.direction.value.upper()}")
            if trade.entry_timestamp:
                print(f"   Entry Time: {trade.entry_timestamp.strftime('%Y-%m-%d %H:%M:%S IST')}")
            
            # Check if position is closed in broker
            position_in_broker = False
            for bp in broker_positions:
                if bp.symbol == trade.symbol and bp.quantity != 0:
                    position_in_broker = True
                    break
            
            if position_in_broker:
                print(f"   ⚠️  Position STILL OPEN in broker")
                print(f"   📝 Exit order may be pending or partially filled")
                continue
            
            # Position closed in broker - need to get execution details
            print(f"   ✅ Position CLOSED in broker")
            print(f"   🔍 Fetching exit price from orders...")
            
            # Get today's orders
            orders = await broker.get_orders()
            
            # Find exit order for this symbol (SELL order placed today)
            exit_order = None
            for order in orders:
                if (order.symbol == trade.symbol and 
                    order.transaction_type.value == 'sell' and
                    order.status.value in ['complete', 'executed']):
                    exit_order = order
                    break
            
            if exit_order:
                exit_price = exit_order.average_price
                if exit_price > 0:
                    print(f"   Exit: {trade.quantity} shares @ Rs{exit_price:.2f}")
                    
                    # Calculate P&L
                    if trade.direction == TradeDirection.LONG:
                        pnl = (exit_price - trade.entry_price) * trade.quantity
                    else:  # SHORT
                        pnl = (trade.entry_price - exit_price) * trade.quantity
                    
                    pnl_pct = (pnl / (trade.entry_price * trade.quantity)) * 100
                    
                    print(f"   💰 P&L: Rs{pnl:.2f} ({pnl_pct:+.2f}%)")
                    
                    # Update database
                    trade.exit_pricstamp = now_ist()
                    trade.realized_pnl = pnl
                    trade.net_pnl = pnl  # Will be updated with charges later
                    trade.status = TradeStatus.CLOSED
                    trade.exit_reason = 'manual'
                    trade.status = TradeStatus.CLOSED
                    
                    db.commit()
                    
                    total_pnl += pnl
                    updated_count += 1
                    
                    print(f"   ✅ Database updated")
                else:
                    print(f"   ❌ No valid exit price found")
            else:
                print(f"   ⚠️  No executed exit order found yet")
                print(f"   📝 Order may still be processing")
            
            print()
        
        print(f"{'='*70}")
        print(f"📊 P&L UPDATE SUMMARY")
        print(f"{'='*70}\n")
        print(f"   ✅ Positions updated: {updated_count}/{len(open_trades)}")
        print(f"   💰 Total P&L: Rs{total_pnl:.2f}")
        
        if total_pnl > 0:
            print(f"   🎯 Result: PROFIT ✓")
        elif total_pnl < 0:
            print(f"   ⚠️  Result: LOSS")
        else:
            print(f"   📝 Result: BREAKEVEN")
        
        if updated_count < len(open_trades):
            print(f"\n⚠️  Note: {len(open_trades) - updated_count} positions not yet updated")
            print(f"   Exit orders may still be processing")
            print(f"   Run this script again in a few minutes")
        
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()
        print(f"{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(update_pnl())
