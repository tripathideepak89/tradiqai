"""Check today's trading activity and eligible trades"""
import os
from dotenv import load_dotenv
from tradiqai_supabase_config import get_supabase_admin
from utils.timezone import now_ist, today_ist
from datetime import datetime

load_dotenv()

print("📊 Checking Today's Trading Activity...\n")
print(f"Current Time: {now_ist().strftime('%Y-%m-%d %H:%M:%S IST')}\n")

try:
    supabase = get_supabase_admin()
    
    # Get today's date range
    today_start = today_ist().isoformat()
    
    # 1. Check today's trades
    print("=" * 60)
    print("📈 TODAY'S TRADES")
    print("=" * 60)
    
    trades_response = supabase.table("trades").select("*").gte(
        "entry_timestamp", today_start
    ).order("entry_timestamp", desc=True).execute()
    
    if trades_response.data:
        print(f"\n✅ Found {len(trades_response.data)} trade(s) today:\n")
        
        total_pnl = 0
        for i, trade in enumerate(trades_response.data, 1):
            symbol = trade.get('symbol')
            side = trade.get('side')
            quantity = trade.get('quantity')
            entry_price = trade.get('entry_price')
            exit_price = trade.get('exit_price')
            status = trade.get('status')
            broker_id = trade.get('broker_order_id')
            
            print(f"{i}. {symbol} - {side}")
            print(f"   Quantity: {quantity}")
            print(f"   Entry: ₹{entry_price:.2f}" if entry_price else "   Entry: N/A")
            if exit_price:
                print(f"   Exit: ₹{exit_price:.2f}")
                if side == "BUY":
                    pnl = (exit_price - entry_price) * quantity
                else:
                    pnl = (entry_price - exit_price) * quantity
                total_pnl += pnl
                print(f"   P&L: ₹{pnl:.2f}")
            print(f"   Status: {status}")
            print(f"   Order ID: {broker_id}")
            print()
        
        if total_pnl != 0:
            print(f"💰 Total Realized P&L: ₹{total_pnl:.2f}\n")
    else:
        print("\n❌ No trades executed today\n")
    
    # 2. Check monitored stocks (if table exists)
    print("=" * 60)
    print("👀 MONITORED STOCKS")
    print("=" * 60)
    
    try:
        stocks_response = supabase.table("monitored_stocks").select("*").eq(
            "is_active", True
        ).order("symbol").execute()
        
        if stocks_response.data:
            print(f"\n✅ {len(stocks_response.data)} stocks being monitored:\n")
            for stock in stocks_response.data:
                print(f"  • {stock.get('symbol')} - {stock.get('strategy_name', 'N/A')}")
            print()
        else:
            print("\n⚠️ No stocks currently monitored\n")
    except Exception as e:
        print("\n⚠️ Monitored stocks table not found in Supabase")
        print("   (This is tracked by local trading bot only)\n")
    
    # 3. Check recent news (if table exists)
    print("=" * 60)
    print("📰 TODAY'S NEWS (Last 5)")
    print("=" * 60)
    
    try:
        news_response = supabase.table("news_items").select("*").gte(
            "timestamp", today_start
        ).order("timestamp", desc=True).limit(5).execute()
        
        if news_response.data:
            print(f"\n✅ {len(news_response.data)} news item(s) today:\n")
            for news in news_response.data:
                symbol = news.get('symbol', 'N/A')
                headline = news.get('headline', 'N/A')
                action = news.get('action', 'NONE')
                print(f"  • [{symbol}] {headline[:80]}...")
                print(f"    Action: {action}")
                print()
        else:
            print("\n❌ No news items today\n")
    except Exception as e:
        print("\n⚠️ News items table not found in Supabase")
        print("   (News is tracked by local trading bot)\n")
    
    # 4. Check if trading bot is supposed to be running
    print("=" * 60)
    print("🤖 TRADING BOT STATUS")
    print("=" * 60)
    
    current_time = now_ist()
    market_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
    is_weekday = current_time.weekday() < 5
    is_market_hours = is_weekday and market_open <= current_time <= market_close
    
    print(f"\n  Market Status: {'🟢 OPEN' if is_market_hours else '🔴 CLOSED'}")
    print(f"  Day: {current_time.strftime('%A')}")
    print(f"  Time: {current_time.strftime('%H:%M:%S IST')}")
    print(f"  Market Hours: 09:15 - 15:30 IST (Mon-Fri)")
    
    if is_market_hours:
        print("\n  ✅ This is a good time for trading!")
        print("  💡 Run 'python main.py' to start the trading bot")
    else:
        print("\n  ⏰ Market is currently closed")
        print("  📊 Dashboard broker sync runs every hour outside market hours")
    
    print()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
