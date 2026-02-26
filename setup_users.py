"""Create database tables and default user"""
import sqlite3

conn = sqlite3.connect("autotrade.db")
cursor = conn.cursor()

# Create users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT,
    capital REAL DEFAULT 50000,
    paper_trading INTEGER DEFAULT 0,
    max_daily_loss REAL DEFAULT 2000,
    max_position_risk REAL DEFAULT 500,
    max_open_positions INTEGER DEFAULT 5,
    broker_name TEXT,
    broker_config TEXT,
    is_active INTEGER DEFAULT 1,
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
)
""")

# Create default user
cursor.execute("""
INSERT OR IGNORE INTO users (email, username, full_name, capital, paper_trading, max_daily_loss, 
                            max_position_risk, max_open_positions, is_active)
VALUES ('trading@bot.local', 'tradingbot', 'Trading Bot', 50000, 0, 2000, 500, 5, 1)
""")

conn.commit()

# Verify
cursor.execute("SELECT id, email, username, is_active FROM users")
users = cursor.fetchall()

if users:
    print(f"✅ Users table created with {len(users)} users:")
    for user in users:
        print(f"  ID: {user[0]}, Email: {user[1]}, Username: {user[2]}, Active: {user[3]}")
else:
    print("❌ No users found!")

conn.close()
