"""Check what's in Supabase trades table"""
import os
from dotenv import load_dotenv
from tradiqai_supabase_config import get_supabase_admin

load_dotenv()

print("🔍 Checking Supabase trades table...\n")

try:
    supabase = get_supabase_admin()
    
    # Get all trades
    result = supabase.table("trades").select("*").order("created_at", desc=True).limit(10).execute()
    
    if result.data:
        print(f"✅ Found {len(result.data)} trades:\n")
        for trade in result.data:
            print(f"  ID: {trade.get('id')}")
            print(f"  User ID: {trade.get('user_id')}")
            print(f"  Symbol: {trade.get('symbol')}")
            print(f"  Direction: {trade.get('direction')}")
            print(f"  Quantity: {trade.get('quantity')}")
            print(f"  Entry Price: {trade.get('entry_price')}")
            print(f"  Status: {trade.get('status')}")
            print(f"  Order ID: {trade.get('broker_order_id')}")
            print(f"  Created: {trade.get('created_at')}")
            print()
    else:
        print("❌ No trades found in database\n")
        
    # Check table structure
    print("\n📋 Checking table structure...")
    # Try to get the schema by attempting an insert with empty data (will fail but show required fields)
    try:
        supabase.table("trades").select("id").limit(1).execute()
        print("✅ Trades table exists and is accessible")
    except Exception as e:
        print(f"⚠️ Error accessing trades table: {e}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
