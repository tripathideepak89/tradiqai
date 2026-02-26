"""Test user profile creation to diagnose RLS issues"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment
load_dotenv('.env.production')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

print(f"🔍 Testing Profile Creation")
print(f"URL: {SUPABASE_URL}")
print(f"Anon Key: {SUPABASE_ANON_KEY[:20] if SUPABASE_ANON_KEY else 'NOT SET'}...")
print(f"Service Key: {SUPABASE_SERVICE_KEY[:20] if SUPABASE_SERVICE_KEY else 'NOT SET'}...")
print()

# Test 1: Check with anon client
print("=" * 60)
print("Test 1: Anon Client (Regular Supabase Client)")
print("=" * 60)
anon_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

try:
    # Try to fetch users table
    result = anon_client.table("users").select("*").limit(5).execute()
    print(f"✅ Can read users table: {len(result.data)} rows")
    if result.data:
        print(f"   Sample: {result.data[0].get('email', 'N/A')}")
except Exception as e:
    print(f"❌ Cannot read users table: {e}")

print()

# Test 2: Try to insert with anon client
print("Test 2: Try INSERT with anon client")
try:
    test_profile = {
        "id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "capital": 50000.0,
        "initial_capital": 50000.0,
        "paper_trading": True,
        "is_active": True
    }
    result = anon_client.table("users").insert(test_profile).execute()
    print(f"✅ INSERT succeeded with anon client!")
    print(f"   Clean up: deleting test user...")
    anon_client.table("users").delete().eq("id", "test-user-123").execute()
except Exception as e:
    print(f"❌ INSERT failed with anon client: {e}")
    print(f"   This is expected if RLS policies require authentication")

print()

# Test 3: Check with service role key (admin)
if SUPABASE_SERVICE_KEY:
    print("=" * 60)
    print("Test 3: Service Role Client (Admin/Bypass RLS)")
    print("=" * 60)
    admin_client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    try:
        result = admin_client.table("users").select("*").limit(5).execute()
        print(f"✅ Admin can read users table: {len(result.data)} rows")
    except Exception as e:
        print(f"❌ Admin cannot read users table: {e}")
    
    print()
    print("Test 4: Try INSERT with admin client")
    try:
        test_profile = {
            "id": "test-admin-456",
            "username": "testadmin",
            "email": "testadmin@example.com",
            "capital": 50000.0,
            "initial_capital": 50000.0,
            "paper_trading": True,
            "is_active": True
        }
        result = admin_client.table("users").insert(test_profile).execute()
        print(f"✅ INSERT succeeded with admin client!")
        print(f"   Created: {result.data}")
        print(f"   Clean up: deleting test user...")
        admin_client.table("users").delete().eq("id", "test-admin-456").execute()
    except Exception as e:
        print(f"❌ INSERT failed with admin client: {e}")
        print(f"   Details: {type(e).__name__}")
else:
    print("=" * 60)
    print("⚠️  SUPABASE_SERVICE_KEY not set in .env.production")
    print("=" * 60)
    print()
    print("The service role key is CRITICAL for creating user profiles!")
    print("This key bypasses RLS policies and allows admin operations.")
    print()
    print("HOW TO FIX:")
    print("1. Go to Supabase Dashboard → Settings → API")
    print("2. Copy the 'service_role' secret key (NOT the anon public key)")
    print("3. Add to Railway environment variables:")
    print("   SUPABASE_SERVICE_KEY=your-service-role-key-here")
    print("4. Add to .env.production locally")

print()
print("=" * 60)
print("🔍 RLS Policy Check")
print("=" * 60)
print()
print("If admin INSERT failed, check Supabase RLS policies:")
print()
print("Go to: Supabase Dashboard → Table Editor → users table → RLS")
print()
print("Required policies for this app:")
print("1. SELECT policy: Allow authenticated users to read their own profile")
print("   WITH CHECK: auth.uid() = id")
print()
print("2. INSERT policy: Allow service role to create any profile")
print("   (Service role key bypasses RLS, so this should work automatically)")
print()
print("3. UPDATE policy: Allow users to update their own profile")
print("   WITH CHECK: auth.uid() = id")
print()
print("If admin client still can't INSERT:")
print("- Verify SUPABASE_SERVICE_KEY is the correct service_role key")
print("- Check for any database triggers that might be blocking inserts")
print("- Check for foreign key constraints (id should match auth.users.id)")
