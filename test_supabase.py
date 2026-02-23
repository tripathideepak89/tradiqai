"""
Quick script to test Supabase connection and authentication
"""
import asyncio
from tradiqai_supabase_config import get_supabase_client, SUPABASE_URL
from tradiqai_supabase_auth import SupabaseAuth, UserRegister, UserLogin

async def test_supabase():
    print("🧪 Testing Supabase Connection...")
    print(f"📍 Supabase URL: {SUPABASE_URL}")
    print()
    
    # Test 1: Connection
    try:
        supabase = get_supabase_client()
        print("✅ Supabase client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Supabase: {e}")
        return
    
    # Test 2: Database connection
    try:
        result = supabase.table("users").select("count", count="exact").execute()
        print(f"✅ Database connected - {result.count} users in database")
    except Exception as e:
        print(f"⚠️  Database query failed: {e}")
        print("   Make sure you've run the SQL migration in Supabase SQL Editor")
    
    print()
    print("=" * 60)
    print("🧪 Testing Authentication Flow")
    print("=" * 60)
    
    auth = SupabaseAuth()
    
    # Test 3: Register a test user
    print("\n📝 Test 1: Register new user...")
    test_user = UserRegister(
        email="test@tradiqai.com",
        password="test123456",
        username="testuser",
        full_name="Test User"
    )
    
    try:
        result = await auth.register_user(test_user)
        print(f"✅ Registration successful!")
        print(f"   User ID: {result['user'].id}")
        print(f"   Email: {result['user'].email}")
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
            print(f"⚠️  User already exists (this is OK for testing)")
        else:
            print(f"❌ Registration failed: {e}")
    
    # Test 4: Login
    print("\n🔐 Test 2: Login...")
    credentials = UserLogin(
        email="test@tradiqai.com",
        password="test123456"
    )
    
    try:
        result = await auth.login_user(credentials)
        print(f"✅ Login successful!")
        print(f"   Access Token: {result['access_token'][:50]}...")
        print(f"   Username: {result['user']['username']}")
        print(f"   Capital: ₹{result['user']['capital']:,.2f}")
        
        # Save token for next test
        access_token = result['access_token']
        
        # Test 5: Get user profile
        print("\n👤 Test 3: Get current user...")
        from fastapi.security import HTTPAuthCredentials
        
        # Create mock credentials
        class MockCredentials:
            def __init__(self, token):
                self.credentials = token
        
        mock_creds = MockCredentials(access_token)
        user = await auth.get_current_user(mock_creds)
        print(f"✅ User profile retrieved!")
        print(f"   ID: {user['id']}")
        print(f"   Username: {user['username']}")
        print(f"   Email: {user['email']}")
        print(f"   Capital: ₹{user['capital']:,.2f}")
        print(f"   Paper Trading: {user['paper_trading']}")
        print(f"   Active: {user['is_active']}")
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
    
    print()
    print("=" * 60)
    print("✅ Supabase Integration Test Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Update your .env file with actual Supabase credentials")
    print("2. Run the SQL migration in Supabase SQL Editor")
    print("3. Start the dashboard: python dashboard.py")
    print("4. Visit: http://localhost:8080/login")
    print()

if __name__ == "__main__":
    asyncio.run(test_supabase())
