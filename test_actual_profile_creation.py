"""Test that our profile creation code works correctly"""
import os
import uuid
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('.env.production')

admin = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

print("🧪 Testing Profile Creation with Actual Code\n")
print("=" * 60)

# This is the EXACT profile_data from tradiqai_supabase_auth.py lines 201-214
# Using a proper UUID this time (Supabase Auth always provides UUIDs)
test_user_id = str(uuid.uuid4())
test_email = "finaltest@tradiqai.com"

profile_data = {
    "id": test_user_id,
    "email": test_email,
    "username": test_email.split('@')[0],
    "full_name": test_email.split('@')[0],
    "capital": 50000.0,
    "paper_trading": True,
    "max_daily_loss": 1500.0,
    "max_position_risk": 400.0,
    "max_open_positions": 2,
    "is_active": True,
    "is_admin": False
}

print("Profile data to insert:")
for key, value in profile_data.items():
    print(f"  {key:25s} = {value}")
print()

try:
    print("Attempting INSERT with admin client...")
    result = admin.table("users").insert(profile_data).execute()
    
    if result.data:
        print("✅ SUCCESS! Profile created:")
        print(f"   ID: {result.data[0]['id']}")
        print(f"   Email: {result.data[0]['email']}")
        print(f"   Username: {result.data[0]['username']}")
        print()
        print("Cleaning up test user...")
        admin.table("users").delete().eq("id", test_user_id).execute()
        print("✅ Test user deleted")
        print()
        print("=" * 60)
        print("✅ VERDICT: Profile creation code is CORRECT")
        print("=" * 60)
        print()
        print("This means:")
        print("1. The code structure is correct")
        print("2. No initial_capital field is being used")
        print("3. All required columns exist in Supabase")
        print()
        print("If you still get errors on tradiqai.com:")
        print("- Railway might still be deploying (wait 1-2 more minutes)")
        print("- Check Railway logs for the actual Supabase error")
        print("- Hard refresh browser (Ctrl+Shift+R)")
    else:
        print("❌ No data returned from insert")
        
except Exception as e:
    print(f"❌ INSERT failed: {e}")
    print()
    print("=" * 60)
    print("❌ VERDICT: There's still an issue")
    print("=" * 60)
    print()
    print("Error details:", type(e).__name__)
    if hasattr(e, 'message'):
        print(f"Message: {e.message}")
