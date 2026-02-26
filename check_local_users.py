"""Check users in local SQLite database"""
import sqlite3


conn = sqlite3.connect("autotrade.db")
cursor = conn.cursor()

# Check if users table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
table = cursor.fetchone()

if not table:
    print("❌ users table doesn't exist!")
else:
    # Get users
    cursor.execute("SELECT id, email, username, is_active FROM users ORDER BY id")
    users = cursor.fetchall()
    
    if users:
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  ID: {user[0]}, Email: {user[1]}, Username: {user[2]}, Active: {user[3]}")
    else:
        print("No users found in database!")
        print("\nCreating a default user...")
        
        # Create a default user
        cursor.execute("""
            INSERT INTO users (email, username, full_name, capital, paper_trading, max_daily_loss, 
                              max_position_risk, max_open_positions, is_active)
            VALUES ('trading@bot.local', 'tradingbot', 'Trading Bot', 50000, 0, 2000, 500, 5, 1)
        """)
        conn.commit()
        
        # Verify
        cursor.execute("SELECT id, email, username FROM users WHERE email = 'trading@bot.local'")
        new_user = cursor.fetchone()
        if new_user:
            print(f"✅ Created user: ID={new_user[0]}, Email={new_user[1]}, Username={new_user[2]}")

conn.close()
