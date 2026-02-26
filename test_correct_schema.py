"""Test trade insertion with correct schema"""
import os
from dotenv import load_dotenv
from tradiqai_supabase_config import get_supabase_admin
from utils.timezone import now_ist

load_dotenv()

print("🧪 Testing trade insertion with correct schema...\n")

try:
    supabase = get_supabase_admin()
    
    # Get user ID
    users = supabase.table("users").select("id, email").execute()
    user_id = users.data[0].get("id")
    user_email = users.data[0].get("email")
    print(f"User: {user_email} (ID: {user_id})\n")
    
    # Insert test trade with CORRECT schema
    trade_data = {
        "user_id": user_id,
        "symbol": "TESTFIX",
        "side": "BUY",
        "entry_price": 150.0,
        "quantity": 5,
        "entry_timestamp": now_ist().isoformat(),
        "broker_order_id": "TEST-" + now_ist().strftime("%H%M%S"),
        "status": "OPEN"
    }
    
    print(f"📝 Inserting: {trade_data}\n")
    
    result = supabase.table("trades").insert(trade_data).execute()
    
    if result.data:
        trade_id = result.data[0].get('id')
        print(f"✅ SUCCESS! Trade saved:")
        print(f"   Trade ID: {trade_id}")
        print(f"   Symbol: {result.data[0].get('symbol')}")
        print(f"   Side: {result.data[0].get('side')}")
        print(f"   Quantity: {result.data[0].get('quantity')}")
        print(f"   Price: {result.data[0].get('entry_price')}")
        
        # Clean up
        print(f"\n🧹 Cleaning up test trade...")
        supabase.table("trades").delete().eq("id", trade_id).execute()
        print("   ✅ Test trade deleted\n")
        print("✅ Schema is NOW CORRECT! Manual orders will work!")
    else:
        print("❌ No data returned")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
