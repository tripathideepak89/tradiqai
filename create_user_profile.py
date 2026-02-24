"""
Create missing user profile
Run this to create a user profile for an authenticated user who doesn't have one
"""
from tradiqai_supabase_config import get_supabase_admin
from datetime import datetime

def create_user_profile(user_id: str, email: str, username: str = None):
    """Create user profile in users table"""
    
    supabase_admin = get_supabase_admin()
    
    # Check if profile exists
    existing = supabase_admin.table("users").select("*").eq("id", user_id).execute()
    
    if existing.data:
        print(f"✅ User profile already exists: {email}")
        print(f"   User ID: {user_id}")
        print(f"   Username: {existing.data[0].get('username')}")
        return existing.data[0]
    
    # Create profile
    profile_data = {
        "id": user_id,
        "email": email,
        "username": username or email.split('@')[0],
        "full_name": username or email.split('@')[0],
        "capital": 50000.0,  # Default capital
        "paper_trading": True,  # Start in paper trading mode
        "max_daily_loss": 1500.0,
        "max_position_risk": 400.0,
        "max_open_positions": 2,
        "is_active": True,
        "is_admin": False,
        "created_at": datetime.utcnow().isoformat()
    }
    
    result = supabase_admin.table("users").insert(profile_data).execute()
    
    if result.data:
        print(f"✅ User profile created successfully!")
        print(f"   User ID: {user_id}")
        print(f"   Email: {email}")
        print(f"   Username: {profile_data['username']}")
        print(f"   Capital: ₹{profile_data['capital']:,.2f}")
        return result.data[0]
    else:
        print(f"❌ Failed to create user profile")
        return None


def get_all_auth_users():
    """Get all authenticated users from Supabase"""
    supabase_admin = get_supabase_admin()
    
    # Get all auth users (requires admin)
    users = supabase_admin.auth.admin.list_users()
    
    return users


def sync_auth_users_to_profiles():
    """Create profiles for all authenticated users who don't have one"""
    print("=" * 80)
    print("SYNCING SUPABASE AUTH USERS TO USER PROFILES")
    print("=" * 80)
    
    supabase_admin = get_supabase_admin()
    
    # Get all users from auth.users
    try:
        # Note: This requires Supabase admin API access
        # For now, we'll just create for the current logged-in user
        print("\n⚠️  This script creates a profile for a specific user")
        print("    You need the user_id from Supabase Auth\n")
        
        user_id = input("Enter user ID (from Supabase Auth): ").strip()
        email = input("Enter email: ").strip()
        username = input("Enter username (optional): ").strip() or email.split('@')[0]
        
        if user_id and email:
            create_user_profile(user_id, email, username)
        else:
            print("❌ User ID and email are required")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Quick create for current user
    import sys
    
    if len(sys.argv) >= 3:
        user_id = sys.argv[1]
        email = sys.argv[2]
        username = sys.argv[3] if len(sys.argv) > 3 else None
        create_user_profile(user_id, email, username)
    else:
        sync_auth_users_to_profiles()
