"""
Supabase Setup Checker
Helps you verify all requirements for Supabase integration
"""
import os
from dotenv import load_dotenv

load_dotenv()

def check_setup():
    print("=" * 70)
    print("🔍 TradiqAI Supabase Setup Checker")
    print("=" * 70)
    print()
    
    issues = []
    warnings = []
    
    # Check 1: .env file exists
    print("📋 Checking configuration...")
    if not os.path.exists(".env"):
        issues.append("❌ .env file not found")
        print("❌ .env file not found")
    else:
        print("✅ .env file found")
    
    # Check 2: Supabase URL
    supabase_url = os.getenv("SUPABASE_URL", "")
    if not supabase_url:
        issues.append("❌ SUPABASE_URL not set in .env")
        print("❌ SUPABASE_URL not set in .env")
    elif supabase_url == "https://lmpajbaylwrlqtcqmwoo.supabase.co":
        print("✅ SUPABASE_URL configured")
    else:
        warnings.append("⚠️  SUPABASE_URL doesn't match expected project")
        print(f"⚠️  SUPABASE_URL: {supabase_url}")
        print(f"   Expected: https://lmpajbaylwrlqtcqmwoo.supabase.co")
    
    # Check 3: Supabase Anon Key
    anon_key = os.getenv("SUPABASE_ANON_KEY", "")
    if not anon_key or anon_key == "YOUR_ANON_PUBLIC_KEY_HERE":
        issues.append("❌ SUPABASE_ANON_KEY not set in .env")
        print("❌ SUPABASE_ANON_KEY not set")
    elif len(anon_key) > 100:
        print("✅ SUPABASE_ANON_KEY configured")
    else:
        warnings.append("⚠️  SUPABASE_ANON_KEY looks too short")
        print(f"⚠️  SUPABASE_ANON_KEY looks invalid (length: {len(anon_key)})")
    
    # Check 4: Supabase Service Key
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not service_key or service_key == "YOUR_SERVICE_ROLE_KEY_HERE":
        issues.append("❌ SUPABASE_SERVICE_KEY not set in .env")
        print("❌ SUPABASE_SERVICE_KEY not set")
    elif len(service_key) > 100:
        print("✅ SUPABASE_SERVICE_KEY configured")
    else:
        warnings.append("⚠️  SUPABASE_SERVICE_KEY looks too short")
        print(f"⚠️  SUPABASE_SERVICE_KEY looks invalid (length: {len(service_key)})")
    
    # Check 5: Database Password
    db_password = os.getenv("SUPABASE_DB_PASSWORD", "")
    if not db_password or db_password == "YOUR_DATABASE_PASSWORD":
        issues.append("❌ SUPABASE_DB_PASSWORD not set in .env")
        print("❌ SUPABASE_DB_PASSWORD not set")
    else:
        print("✅ SUPABASE_DB_PASSWORD configured")
    
    # Check 6: Database URL
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        issues.append("❌ DATABASE_URL not set in .env")
        print("❌ DATABASE_URL not set")
    elif "supabase" in db_url.lower():
        print("✅ DATABASE_URL points to Supabase")
    elif "sqlite" in db_url.lower():
        warnings.append("⚠️  DATABASE_URL still using SQLite (should use Supabase)")
        print("⚠️  DATABASE_URL using SQLite (update to use Supabase)")
    else:
        print(f"✅ DATABASE_URL configured")
    
    print()
    print("=" * 70)
    print("📦 Checking Dependencies...")
    print("=" * 70)
    
    # Check 7: Supabase package installed
    try:
        import supabase
        print("✅ supabase package installed")
    except ImportError:
        issues.append("❌ supabase package not installed")
        print("❌ supabase package not installed")
        print("   Run: pip install -r requirements_supabase.txt")
    
    # Check 8: Required files exist
    print()
    print("=" * 70)
    print("📁 Checking Required Files...")
    print("=" * 70)
    
    required_files = [
        "supabase_config.py",
        "supabase_auth.py",
        "supabase_migration.sql",
        "requirements_supabase.txt"
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            issues.append(f"❌ {file} not found")
            print(f"❌ {file} not found")
    
    # Summary
    print()
    print("=" * 70)
    print("📊 Summary")
    print("=" * 70)
    
    if not issues and not warnings:
        print("✅ All checks passed! You're ready to use Supabase!")
        print()
        print("Next steps:")
        print("1. Run SQL migration in Supabase SQL Editor")
        print("   → https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/sql")
        print("2. Test connection: python test_supabase.py")
        print("3. Start dashboard: python dashboard.py")
        return True
    
    if issues:
        print(f"\n❌ Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"   {issue}")
    
    if warnings:
        print(f"\n⚠️  Found {len(warnings)} warning(s):")
        for warning in warnings:
            print(f"   {warning}")
    
    print()
    print("=" * 70)
    print("🔧 How to Fix")
    print("=" * 70)
    print()
    print("1. Get your Supabase credentials:")
    print("   → https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo")
    print()
    print("2. Update .env file with:")
    print("   - SUPABASE_URL")
    print("   - SUPABASE_ANON_KEY")
    print("   - SUPABASE_SERVICE_KEY")
    print("   - SUPABASE_DB_PASSWORD")
    print("   - DATABASE_URL")
    print()
    print("3. Install dependencies:")
    print("   pip install -r requirements_supabase.txt")
    print()
    print("4. Read the setup guide:")
    print("   → SUPABASE_QUICKSTART.md")
    print()
    
    return False

if __name__ == "__main__":
    try:
        success = check_setup()
        if success:
            exit(0)
        else:
            exit(1)
    except Exception as e:
        print(f"\n❌ Error during check: {e}")
        exit(1)
