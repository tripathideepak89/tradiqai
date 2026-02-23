"""Health check endpoint for monitoring"""
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path


def check_log_file():
    """Check if log file exists and is recent"""
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = Path(f"logs/trading_{today}.log")
    
    if not log_file.exists():
        return False, "Log file not found"
    
    # Check if log was updated in last 5 minutes
    mod_time = datetime.fromtimestamp(log_file.stat().st_mtime)
    if datetime.now() - mod_time > timedelta(minutes=5):
        return False, f"Log file not updated (last: {mod_time})"
    
    return True, "OK"


def check_database():
    """Check if database is accessible"""
    db_file = Path("autotrade.db")
    
    if not db_file.exists():
        return False, "Database file not found"
    
    try:
        # Try to import and connect
        from database import SessionLocal
        db = SessionLocal()
        db.close()
        return True, "OK"
    except Exception as e:
        return False, f"Database error: {str(e)}"


def check_env_file():
    """Check if .env file exists"""
    env_file = Path(".env")
    
    if not env_file.exists():
        return False, ".env file not found"
    
    return True, "OK"


def main():
    """Run all health checks"""
    checks = {
        "Log File": check_log_file(),
        "Database": check_database(),
        "Environment": check_env_file(),
    }
    
    all_ok = all(status for status, _ in checks.values())
    
    # Print results
    print(f"\n{'='*50}")
    print("AutoTrade AI - Health Check")
    print(f"{'='*50}\n")
    
    for check_name, (status, message) in checks.items():
        status_str = "✓ OK" if status else "✗ FAIL"
        color = '\033[92m' if status else '\033[91m'
        print(f"{color}{status_str}\033[0m {check_name}: {message}")
    
    print(f"\n{'='*50}\n")
    
    # Exit code
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
