"""Check actual Supabase trades table schema"""
import os
from dotenv import load_dotenv
from tradiqai_supabase_config import get_supabase_admin

load_dotenv()

print("🔍 Checking actual Supabase trades table schema...\n")

try:
    supabase = get_supabase_admin()
    
    # Try to select all columns (will show us what exists)
    print("1️⃣ Trying to select * from trades...")
    result = supabase.table("trades").select("*").limit(1).execute()
    
    print(f"✅ Query succeeded")
    print(f"   Data returned: {result.data}")
    
    # Now try different possible column names
    print("\n2️⃣ Testing individual columns:")
    
    test_columns = [
        "id", "user_id", "symbol", "strategy_name", "direction", "side",
        "entry_price", "quantity", "entry_timestamp", "stop_price",
        "target_price", "risk_amount", "broker_order_id", "status",
        "exit_price", "exit_timestamp", "realized_pnl", "charges",
        "net_pnl", "created_at", "updated_at"
    ]
    
    existing_columns = []
    missing_columns = []
    
    for col in test_columns:
        try:
            supabase.table("trades").select(col).limit(1).execute()
            existing_columns.append(col)
            print(f"   ✅ {col}")
        except Exception as e:
            missing_columns.append(col)
            print(f"   ❌ {col} - {str(e)[:80]}")
    
    print(f"\n📊 Summary:")
    print(f"   Existing columns ({len(existing_columns)}): {', '.join(existing_columns)}")
    print(f"   Missing columns ({len(missing_columns)}): {', '.join(missing_columns)}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
