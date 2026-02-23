"""
Database Migration Script - Add User Authentication
Run this ONCE to upgrade your database to support multi-user
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Base, engine
from models import User, Trade, DailyMetrics, SystemLog
from user_auth import get_password_hash

load_dotenv()


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    if not check_table_exists(table_name):
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate_database():
    """
    Migrate database to support user authentication
    
    Steps:
    1. Create users table if it doesn't exist
    2. Add user_id columns to existing tables
    3. Create default admin user
    4. Link existing data to admin user
    """
    print("=" * 60)
    print("TradiqAI Database Migration - User Authentication")
    print("=" * 60)
    print()
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Step 1: Create users table
        print("Step 1: Creating users table...")
        if not check_table_exists("users"):
            User.__table__.create(engine)
            print("✓ Users table created")
        else:
            print("✓ Users table already exists")
        print()
        
        # Step 2: Create default admin user
        print("Step 2: Creating default admin user...")
        admin_user = session.query(User).filter(User.username == "admin").first()
        
        if not admin_user:
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
            admin_user = User(
                username="admin",
                email="admin@tradiqai.com",
                hashed_password=get_password_hash(admin_password),
                full_name="System Administrator",
                is_active=True,
                is_admin=True,
                capital=50000.0,
                paper_trading=True,
                broker_name="groww"
            )
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            print(f"✓ Admin user created")
            print(f"  Username: admin")
            print(f"  Password: {admin_password}")
            print(f"  ** CHANGE THIS PASSWORD IMMEDIATELY **")
        else:
            print("✓ Admin user already exists")
            print(f"  User ID: {admin_user.id}")
        print()
        
        admin_id = admin_user.id
        
        # Step 3: Add user_id to trades table
        print("Step 3: Migrating trades table...")
        if not check_column_exists("trades", "user_id"):
            with engine.begin() as conn:
                # Add column as nullable first
                conn.execute(text(
                    "ALTER TABLE trades ADD COLUMN user_id INTEGER"
                ))
                # Set all existing trades to admin user
                conn.execute(text(
                    f"UPDATE trades SET user_id = {admin_id} WHERE user_id IS NULL"
                ))
                # Make column not nullable
                conn.execute(text(
                    "ALTER TABLE trades ALTER COLUMN user_id SET NOT NULL"
                ))
                # Add foreign key (PostgreSQL syntax)
                try:
                    conn.execute(text(
                        "ALTER TABLE trades ADD CONSTRAINT fk_trades_user "
                        "FOREIGN KEY (user_id) REFERENCES users(id)"
                    ))
                except Exception as e:
                    print(f"  Note: Foreign key might already exist - {e}")
                # Add index
                try:
                    conn.execute(text(
                        "CREATE INDEX ix_trades_user_id ON trades(user_id)"
                    ))
                except Exception as e:
                    print(f"  Note: Index might already exist - {e}")
            
            print(f"✓ Added user_id to trades table")
            print(f"  All existing trades linked to user_id: {admin_id}")
        else:
            print("✓ Trades table already has user_id column")
        print()
        
        # Step 4: Add user_id to daily_metrics table
        print("Step 4: Migrating daily_metrics table...")
        if check_table_exists("daily_metrics"):
            if not check_column_exists("daily_metrics", "user_id"):
                with engine.begin() as conn:
                    # Add column
                    conn.execute(text(
                        "ALTER TABLE daily_metrics ADD COLUMN user_id INTEGER"
                    ))
                    # Set existing metrics to admin
                    conn.execute(text(
                        f"UPDATE daily_metrics SET user_id = {admin_id} WHERE user_id IS NULL"
                    ))
                    # Make not nullable
                    conn.execute(text(
                        "ALTER TABLE daily_metrics ALTER COLUMN user_id SET NOT NULL"
                    ))
                    # Add foreign key
                    try:
                        conn.execute(text(
                            "ALTER TABLE daily_metrics ADD CONSTRAINT fk_daily_metrics_user "
                            "FOREIGN KEY (user_id) REFERENCES users(id)"
                        ))
                    except Exception as e:
                        print(f"  Note: Foreign key might already exist - {e}")
                    # Add index
                    try:
                        conn.execute(text(
                            "CREATE INDEX ix_daily_metrics_user_id ON daily_metrics(user_id)"
                        ))
                    except Exception as e:
                        print(f"  Note: Index might already exist - {e}")
                    
                    # Remove unique constraint from date column if it exists
                    try:
                        conn.execute(text(
                            "ALTER TABLE daily_metrics DROP CONSTRAINT IF EXISTS daily_metrics_date_key"
                        ))
                    except Exception as e:
                        print(f"  Note: Unique constraint might not exist - {e}")
                
                print(f"✓ Added user_id to daily_metrics table")
                print(f"  All existing metrics linked to user_id: {admin_id}")
            else:
                print("✓ Daily metrics table already has user_id column")
        else:
            print("✓ Daily metrics table doesn't exist yet (will be created automatically)")
        print()
        
        # Step 5: Add user_id to system_logs table
        print("Step 5: Migrating system_logs table...")
        if check_table_exists("system_logs"):
            if not check_column_exists("system_logs", "user_id"):
                with engine.begin() as conn:
                    conn.execute(text(
                        "ALTER TABLE system_logs ADD COLUMN user_id INTEGER"
                    ))
                    # Note: We leave this nullable as system logs can be user-independent
                    # Add foreign key
                    try:
                        conn.execute(text(
                            "ALTER TABLE system_logs ADD CONSTRAINT fk_system_logs_user "
                            "FOREIGN KEY (user_id) REFERENCES users(id)"
                        ))
                    except Exception as e:
                        print(f"  Note: Foreign key might already exist - {e}")
                    # Add index
                    try:
                        conn.execute(text(
                            "CREATE INDEX ix_system_logs_user_id ON system_logs(user_id)"
                        ))
                    except Exception as e:
                        print(f"  Note: Index might already exist - {e}")
                
                print("✓ Added user_id to system_logs table")
            else:
                print("✓ System logs table already has user_id column")
        else:
            print("✓ System logs table doesn't exist yet (will be created automatically)")
        print()
        
        # Step 6: Verify migration
        print("Step 6: Verifying migration...")
        user_count = session.query(User).count()
        trade_count = session.query(Trade).count()
        
        print(f"✓ Users in database: {user_count}")
        print(f"✓ Trades in database: {trade_count}")
        
        if trade_count > 0:
            trades_with_user = session.query(Trade).filter(Trade.user_id.isnot(None)).count()
            print(f"✓ Trades linked to users: {trades_with_user}/{trade_count}")
        
        print()
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Login with username: admin")
        print("2. Change the admin password immediately")
        print("3. Create individual user accounts as needed")
        print("4. Configure broker settings for each user")
        print()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    print()
    response = input("This will modify your database. Continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        migrate_database()
    else:
        print("Migration cancelled.")
