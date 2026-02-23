"""
Get Database Password from Supabase - Interactive Helper
"""
import webbrowser
import time

PROJECT_REF = "lmpajbaylwrlqtcqmwoo"

def open_database_settings():
    """Open Supabase database settings page"""
    
    print("=" * 70)
    print("🔐 Get Your Supabase Database Password")
    print("=" * 70)
    print()
    print("I'll open your Supabase database settings page in your browser.")
    print()
    print("📋 Steps to get your database password:")
    print()
    print("1. In the opened page, scroll down to 'Connection string'")
    print("2. Click the 'URI' tab")
    print("3. You'll see: postgresql://postgres:[YOUR-PASSWORD]@...")
    print("4. Copy the password (the part after postgres: and before @)")
    print()
    print("OR")
    print()
    print("5. If you don't see the password, scroll up")
    print("6. Click 'Reset Database Password'")
    print("7. Copy the new password shown")
    print()
    print("=" * 70)
    print()
    
    response = input("Press ENTER to open Supabase dashboard...")
    
    # Open browser
    url = f"https://supabase.com/dashboard/project/{PROJECT_REF}/settings/database"
    print(f"\n🌐 Opening: {url}")
    webbrowser.open(url)
    
    print()
    print("=" * 70)
    print()
    
    # Get password from user
    db_password = input("Enter your database password: ").strip()
    
    if not db_password:
        print("❌ No password entered. Please run this script again.")
        return
    
    print()
    print("✅ Password received!")
    print()
    
    # Update .env file
    response = input("💾 Update .env file with this password? (y/n): ")
    
    if response.lower() == 'y':
        update_env_with_password(db_password)
    else:
        print()
        print("👍 Manual update instructions:")
        print(f"   1. Open .env file")
        print(f"   2. Find: SUPABASE_DB_PASSWORD=YOUR_DATABASE_PASSWORD")
        print(f"   3. Replace with: SUPABASE_DB_PASSWORD={db_password}")
        print()
        print(f"   Also update DATABASE_URL:")
        print(f"   DATABASE_URL=postgresql://postgres.{PROJECT_REF}:{db_password}@aws-0-ap-south-1.pooler.supabase.com:6543/postgres")

def update_env_with_password(password):
    """Update .env file with database password"""
    try:
        # Read .env file
        with open('.env', 'r') as f:
            content = f.read()
        
        # Replace placeholder password
        content = content.replace(
            'SUPABASE_DB_PASSWORD=YOUR_DATABASE_PASSWORD',
            f'SUPABASE_DB_PASSWORD={password}'
        )
        
        # Also update DATABASE_URL
        content = content.replace(
            'DATABASE_URL=postgresql://postgres.lmpajbaylwrlqtcqmwoo:YOUR_DB_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres',
            f'DATABASE_URL=postgresql://postgres.lmpajbaylwrlqtcqmwoo:{password}@aws-0-ap-south-1.pooler.supabase.com:6543/postgres'
        )
        
        # Write updated content
        with open('.env', 'w') as f:
            f.write(content)
        
        print()
        print("✅ .env file updated successfully!")
        print()
        print("=" * 70)
        print("🎉 Supabase Configuration Complete!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Install dependencies: pip install -r requirements_supabase.txt")
        print("2. Run SQL migration in Supabase SQL Editor")
        print("   → https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/sql")
        print("   → Copy content from supabase_migration.sql and run it")
        print("3. Test connection: python test_supabase.py")
        print("4. Start dashboard: python dashboard.py")
        print()
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        print()
        print("Please update manually:")
        print(f"   SUPABASE_DB_PASSWORD={password}")

if __name__ == "__main__":
    try:
        open_database_settings()
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
