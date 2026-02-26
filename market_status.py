"""Check market status"""
from utils import now_ist
from datetime import time

current_time = now_ist()
market_open = time(9, 15)
market_close = time(15, 30)
is_open = market_open <= current_time.time() <= market_close and current_time.weekday() < 5

print(f"📅 Current Time: {current_time.strftime('%I:%M %p IST')} ({current_time.strftime('%A')})")
print(f"🕒 Market Hours: 9:15 AM - 3:30 PM IST (Mon-Fri)")
print(f"🔴 Status: {'🟢 OPEN - Bot actively scanning stocks' if is_open else '🔴 CLOSED - Bot waiting for 9:15 AM'}")

if not is_open:
    from datetime import datetime, timedelta
    # Calculate time until market opens
    if current_time.time() < market_open:
        # Market opens today
        market_open_today = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
        time_until_open = market_open_today - current_time
    else:
        # Market opens tomorrow
        tomorrow = current_time + timedelta(days=1)
        market_open_tomorrow = tomorrow.replace(hour=9, minute=15, second=0, microsecond=0)
        time_until_open = market_open_tomorrow - current_time
    
    hours = int(time_until_open.total_seconds() // 3600)
    minutes = int((time_until_open.total_seconds() % 3600) // 60)
    print(f"⏰ Market opens in: {hours}h {minutes}m")
    print("\n💡 Trading bot will:")
    print("   - Start scanning stocks at 9:15 AM")
    print("   - Detect trading signals")
    print("   - Place orders automatically")
    print("   - Trades will sync to dashboard")
