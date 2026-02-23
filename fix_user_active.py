"""Fix user is_active status in Supabase"""
from tradiqai_supabase_config import get_supabase_admin

# Get admin client (bypasses RLS)
supabase = get_supabase_admin()

# Update user to be active
user_id = "2271263a-1d8f-44ee-8fec-c87cbc477a81"
print(f"Updating user {user_id} to active status...")

try:
    # First, check current status
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    
    if result.data:
        user = result.data[0]
        print(f"Current user data:")
        print(f"  Email: {user.get('email')}")
        print(f"  Username: {user.get('username')}")
        print(f"  Is Active: {user.get('is_active')}")
        print(f"  Capital: {user.get('capital')}")
        print()
        
        # Update to active
        update_result = supabase.table("users").update({
            "is_active": True
        }).eq("id", user_id).execute()
        
        if update_result.data:
            print("✅ User activated successfully!")
            updated_user = update_result.data[0]
            print(f"  Is Active: {updated_user.get('is_active')}")
        else:
            print("❌ Update failed")
    else:
        print(f"❌ User not found: {user_id}")
        
except Exception as e:
    print(f"❌ Error: {e}")
