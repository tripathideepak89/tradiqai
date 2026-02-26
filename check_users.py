"""Check if users exist in Railway database"""
import os
from sqlalchemy import create_engine, text

# Railway database URL from the bot's settings
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:aPWksCwTTdRyhxADxGMKRqqGPfvuoOWd@ballast.proxy.rlwy.net:36332/railway")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, email, username, is_active FROM users ORDER BY id"))
    users = result.fetchall()
    
    if users:
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  ID: {user[0]}, Email: {user[1]}, Username: {user[2]}, Active: {user[3]}")
    else:
        print("No users found in database!")
        print("\nCreating a default user...")
        
        # Create a default user
        conn.execute(text("""
            INSERT INTO users (email, username, full_name, capital, paper_trading, max_daily_loss, 
                              max_position_risk, max_open_positions, is_active)
            VALUES ('trading@bot.local', 'tradingbot', 'Trading Bot', 50000, FALSE, 2000, 500, 5, TRUE)
            RETURNING id, email
        """))
        conn.commit()
        
        # Verify
        result = conn.execute(text("SELECT id, email, username FROM users WHERE email = 'trading@bot.local'"))
        new_user = result.fetchone()
        if new_user:
            print(f"✅ Created user: ID={new_user[0]}, Email={new_user[1]}, Username={new_user[2]}")
