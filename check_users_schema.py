"""Check actual schema of users table in Supabase"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('.env.production')

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

print("🔍 Checking users table schema\n")

# Try to get one user to see actual columns
try:
    result = supabase.table("users").select("*").limit(1).execute()
    if result.data:
        user = result.data[0]
        print("✅ Existing columns in users table:")
        print("-" * 60)
        for key, value in user.items():
            print(f"  {key:25s} = {value}")
        print("-" * 60)
        print(f"\nTotal columns: {len(user)}")
    else:
        print("⚠️  No users found in table")
        print("\nTrying to get schema from Supabase...")
        # Try empty insert to get error with field names
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("Required columns for profile creation:")
print("=" * 60)
required_fields = [
    "id",
    "username",
    "email",
    "capital",
    "initial_capital",
    "paper_trading",
    "max_daily_loss",
    "max_position_risk",
    "max_open_positions",
    "is_active"
]
for field in required_fields:
    print(f"  - {field}")

print("\n" + "=" * 60)
print("SOLUTION:")
print("=" * 60)
print("""
The users table needs these columns. You have 2 options:

OPTION 1: Add missing columns to Supabase users table
---------------------------------------------------------
Go to Supabase Dashboard → Table Editor → users table → Add Column

Add these columns:
- initial_capital (numeric/float8)
- paper_trading (boolean, default: true)
- max_daily_loss (numeric/float8)
- max_position_risk (numeric/float8)
- max_open_positions (integer/int4)

OPTION 2: Update the code to only use existing columns
---------------------------------------------------------
Modify tradiqai_supabase_auth.py to only insert columns that exist
in the current schema.

I recommend OPTION 2 (update code) to avoid breaking changes.
""")
