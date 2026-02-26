"""Test inserting a trade to Supabase"""
import os
from dotenv import load_dotenv
from tradiqai_supabase_config import get_supabase_admin
from utils.timezone import now_ist
import uuid

load_dotenv()

print("🧪 Testing trade insertion to Supabase...\n")

try:
    supabase = get_supabase_admin()
    
    # First, get the user ID
    print("1️⃣ Getting user ID...")
    users = supabase.table("users").select("id, email").execute()
    if not users.data:
        print("❌ No users found!")
        exit(1)
    
    user_id = users.data[0].get("id")
    user_email = users.data[0].get("email")
    print(f"   User: {user_email} (ID: {user_id})")
    print(f"   User ID type: {type(user_id)}")
    
    # Try to insert a minimal trade
    print("\n2️⃣ Attempting minimal trade insert...")
    trade_data = {
        "user_id": user_id,
        "symbol": "TEST",
        "strategy_name": "Test Insert",
        "direction": "BUY",
        "entry_price": 100.0,
        "quantity": 1,
        "entry_timestamp": now_ist().isoformat(),
        "stop_price": 95.0,
        "risk_amount": 5.0,
        "status": "OPEN"
    }
    
    print(f"   Data to insert: {trade_data}")
    
    result = supabase.table("trades").insert(trade_data).execute()
    
    print(f"\n✅ SUCCESS! Trade inserted:")
    print(f"   Trade ID: {result.data[0].get('id') if result.data else 'unknown'}")
    print(f"   Response: {result.data}")
    
    # Clean up - delete the test trade
    if result.data and result.data[0].get('id'):
        print(f"\n🧹 Cleaning up test trade...")
        supabase.table("trades").delete().eq("id", result.data[0].get('id')).execute()
        print("   ✅ Test trade deleted")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print(f"   Error type: {type(e).__name__}")
    if hasattr(e, 'message'):
        print(f"   Message: {e.message}")
    import traceback
    traceback.print_exc()
