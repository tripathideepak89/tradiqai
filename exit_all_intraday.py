"""Emergency exit script - Close all intraday positions"""
import asyncio
from datetime import datetime
from database import SessionLocal
from models import Trade, TradeStatus, TradeDirection
from brokers.factory import BrokerFactory
from brokers.base import TransactionType, OrderType
from config import settings
from utils.timezone import now_ist, format_ist

async def exit_all_intraday():
    """Exit all open intraday positions"""
    print(f"\n{'='*70}")
    print(f"⚠️  EMERGENCY EXIT - CLOSING ALL INTRADAY POSITIONS")
    print(f"{'='*70}\n")
    print(f"🇮🇳 IST Time: {format_ist(now_ist())}")
    print(f"📅 Date: {now_ist().date()}\n")
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Get all open positions
        open_trades = db.query(Trade).filter(
            Trade.status == TradeStatus.OPEN
        ).all()
        
        if not open_trades:
            print("✅ NO OPEN POSITIONS - Nothing to exit\n")
            return
        
        print(f"📊 Found {len(open_trades)} open positions:\n")
        for idx, trade in enumerate(open_trades, 1):
            print(f"   {idx}. {trade.symbol}: {trade.direction.value.upper()} "
                  f"{trade.quantity} shares @ Rs{trade.entry_price:.2f}")
        
        print(f"\n{'='*70}")
        print("🔄 EXECUTING EXIT ORDERS...")
        print(f"{'='*70}\n")
        
        # Initialize broker
        broker_config = {
            "api_key": settings.groww_api_key,
            "api_secret": settings.groww_api_secret,
            "api_url": settings.groww_api_url
        }
        broker = BrokerFactory.create_broker(settings.broker, broker_config)
        
        # Connect to broker
        if not await broker.connect():
            print("❌ Failed to connect to broker\n")
            return
        
        print("✅ Broker connected\n")
        
        # Exit each position
        success_count = 0
        fail_count = 0
        
        for trade in open_trades:
            try:
                print(f"🔄 Exiting {trade.symbol}...")
                
                # Determine transaction type (opposite of entry)
                if trade.direction == TradeDirection.LONG:
                    transaction_type = TransactionType.SELL
                else:
                    transaction_type = TransactionType.BUY
                
                # Place market order to exit
                order_result = await broker.place_order(
                    symbol=trade.symbol,
                    transaction_type=transaction_type,
                    quantity=trade.quantity,
                    order_type=OrderType.MARKET,
                    product="MIS"  # Intraday
                )
                
                if order_result and order_result.order_id:
                    print(f"   ✅ {trade.symbol}: Exit order placed successfully")
                    print(f"   📝 Order ID: {order_result.order_id}")
                    success_count += 1
                else:
                    print(f"   ❌ {trade.symbol}: Exit order FAILED")
                    if order_result and order_result.message:
                        print(f"   📝 Error: {order_result.message}")
                    fail_count += 1
                
            except Exception as e:
                print(f"   ❌ {trade.symbol}: Exception - {str(e)}")
                fail_count += 1
        
        print(f"\n{'='*70}")
        print(f"📊 EXIT SUMMARY")
        print(f"{'='*70}\n")
        print(f"   ✅ Successful exits: {success_count}")
        print(f"   ❌ Failed exits: {fail_count}")
        print(f"   📊 Total positions: {len(open_trades)}\n")
        
        if success_count > 0:
            print("💡 Note: Orders placed at MARKET price for immediate execution")
            print("   Check broker app for final exit prices and confirmation\n")
        
        if fail_count > 0:
            print("⚠️  WARNING: Some exits failed. Please check positions manually")
            print("   in your broker app and exit manually if needed.\n")
    
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()
        print(f"{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(exit_all_intraday())
