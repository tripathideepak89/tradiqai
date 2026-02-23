#!/usr/bin/env python3
"""
Manual signal scanner for Feb 23, 2026 (IST)
Checks for eligible trades based on current market conditions
"""
import asyncio
import logging
from datetime import datetime
import pytz
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal
from brokers.factory import BrokerFactory
from brokers.base import BaseBroker
from strategies.live_simple import LiveSimpleStrategy
from transaction_cost_calculator import cost_calculator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

# NSE Nifty 50 watchlist (top liquid stocks)
WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "AXISBANK",
    "KOTAKBANK", "LT", "ASIANPAINT", "MARUTI", "TITAN"
]

def get_ist_time():
    """Get current time in IST"""
    return datetime.now(IST)

def is_market_open():
    """Check if NSE market is open (9:15 AM - 3:30 PM IST, Mon-Fri)"""
    now = get_ist_time()
    
    # Check if weekend
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False, f"Market closed (Weekend - {now.strftime('%A')})"
    
    # Check market hours (9:15 AM - 3:30 PM IST)
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if now < market_start:
        return False, f"Market opens at 9:15 AM IST (Currently: {now.strftime('%I:%M %p IST')})"
    elif now > market_end:
        return False, f"Market closed at 3:30 PM IST (Currently: {now.strftime('%I:%M %p IST')})"
    
    return True, f"Market OPEN (Current time: {now.strftime('%I:%M %p IST')})"

async def scan_for_signals():
    """Scan watchlist for eligible trading signals"""
    
    print("=" * 80)
    print("SIGNAL SCANNER - February 23, 2026")
    print("=" * 80)
    
    # Check current time
    ist_now = get_ist_time()
    print(f"\n⏰ Current Time (IST): {ist_now.strftime('%B %d, %Y - %I:%M:%S %p')}")
    print(f"   Day: {ist_now.strftime('%A')}")
    
    # Check if market is open
    is_open, market_msg = is_market_open()
    print(f"\n📊 Market Status: {'🟢 OPEN' if is_open else '🔴 CLOSED'}")
    print(f"   {market_msg}")
    
    if not is_open:
        print("\n⚠️  Cannot scan for signals - Market is closed")
        print("\nNSE Market Hours: Monday-Friday, 9:15 AM - 3:30 PM IST")
        return
    
    print("\n" + "=" * 80)
    print("SCANNING WATCHLIST FOR SIGNALS...")
    print("=" * 80)
    
    # Initialize broker
    broker_name = settings.broker.lower()
    print(f"\n🔌 Connecting to {broker_name.upper()} broker...")
    
    if broker_name == "groww":
        broker_config = {
            "api_key": settings.groww_api_key,
            "api_secret": settings.groww_api_secret,
            "api_url": settings.groww_api_url
        }
    else:
        print("❌ Only Groww broker supported in this scanner")
        return
    
    broker = BrokerFactory.create_broker(broker_name, broker_config)
    
    if not await broker.connect():
        print("❌ Failed to connect to broker")
        return
    
    print("✅ Broker connected\n")
    
    # Initialize strategy
    strategy = LiveSimpleStrategy(broker=broker)
    print(f"📈 Strategy: {strategy.name}")
    print(f"   Cost-aware filtering: ENABLED\n")
    
    # Scan watchlist
    signals_found = 0
    signals_list = []
    
    for i, symbol in enumerate(WATCHLIST, 1):
        try:
            # Get live quote
            quote = await broker.get_quote(symbol)
            
            if quote is None or quote.last_price == 0:
                print(f"{i:2}. {symbol:15} - ⚠️  No quote available")
                continue
            
            # Convert to dict for strategy
            quote_dict = {
                'ltp': quote.last_price,
                'open': quote.open,
                'high': quote.high,
                'low': quote.low,
                'close': quote.close,
                'volume': quote.volume,
                'avg_volume': getattr(quote, 'avg_volume', quote.volume),
                'vwap': getattr(quote, 'vwap', quote.last_price)
            }
            
            # Generate signal
            signal = await strategy.analyze(quote_dict, symbol)
            
            if signal:
                signals_found += 1
                signals_list.append(signal)
                
                # Validate with cost calculator
                expected_move = abs(signal.target - signal.entry_price)
                cost_approved, cost_reason, cost_metrics = cost_calculator.validate_trade_profitability(
                    quantity=signal.quantity,
                    entry_price=signal.entry_price,
                    expected_move_per_share=expected_move,
                    max_cost_ratio=0.25
                )
                
                status = "✅ ELIGIBLE" if cost_approved else "❌ REJECTED (Cost Filter)"
                
                print(f"{i:2}. {symbol:15} - 🎯 SIGNAL FOUND - {status}")
                print(f"    Action: {signal.action}, Entry: ₹{signal.entry_price:.2f}, Target: ₹{signal.target:.2f}")
                print(f"    Move: ₹{expected_move:.2f}, Cost: ₹{cost_metrics.get('total_cost', 0):.2f}")
                print(f"    Cost Ratio: {cost_metrics.get('cost_ratio', 0):.1f}%")
                if not cost_approved:
                    print(f"    Reason: {cost_reason}")
            else:
                print(f"{i:2}. {symbol:15} - No signal")
        
        except Exception as e:
            print(f"{i:2}. {symbol:15} - ⚠️  Error: {str(e)[:50]}")
    
    print("\n" + "=" * 80)
    print("SCAN RESULTS")
    print("=" * 80)
    print(f"Total Symbols Scanned: {len(WATCHLIST)}")
    print(f"Signals Generated: {signals_found}")
    
    if signals_found > 0:
        eligible = sum(1 for s in signals_list 
                      if cost_calculator.validate_trade_profitability(
                          s.quantity, s.entry_price,
                          abs(s.target - s.entry_price), 0.25
                      )[0])
        rejected = signals_found - eligible
        
        print(f"✅ Eligible Trades (Cost Filter Passed): {eligible}")
        print(f"❌ Rejected Trades (Cost Filter Failed): {rejected}")
    else:
        print("No trading signals found at this time")
    
    print("=" * 80)
    
    await broker.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(scan_for_signals())
    except KeyboardInterrupt:
        print("\n\n⚠️  Scanner interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Scanner error: {e}")
