"""Check today's trades in database"""
import sqlite3
from datetime import datetime

db = sqlite3.connect('autotrade.db')
cursor = db.cursor()

# Get all tables first
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print(f"Tables: {tables}\n")

# Check trades (lowercase)
print("="*100)
print("CHECKING 'trades' TABLE:")
print("="*100)
try:
    cursor.execute('SELECT COUNT(*) FROM trades')
    count = cursor.fetchone()[0]
    print(f"Total trades in 'trades': {count}")
    
    if count > 0:
        cursor.execute('''
            SELECT id, symbol, direction, entry_price, exit_price, quantity, 
                   realized_pnl, net_pnl, status, entry_timestamp, exit_timestamp
            FROM trades 
            ORDER BY id DESC LIMIT 10
        ''')
        
        trades = cursor.fetchall()
        print("\nRecent trades:")
        for t in trades:
            print(f"\nID: {t[0]}")
            print(f"  Symbol: {t[1]} | Direction: {t[2]} | Qty: {t[5]}")
            print(f"  Entry: Rs{t[3]:.2f} @ {t[9]}")
            print(f"  Exit: Rs{t[4] or 0:.2f} @ {t[10] or 'N/A'}")
            print(f"  PnL: Rs{t[6] or 0:.2f} (realized) | Rs{t[7] or 0:.2f} (net)")
            print(f"  Status: {t[8]}")
except Exception as e:
    print(f"Error with 'trades': {e}")

# Check Trade (capitalized)
print("\n" + "="*100)
print("CHECKING 'Trade' TABLE:")
print("="*100)
try:
    cursor.execute('SELECT COUNT(*) FROM Trade')
    count = cursor.fetchone()[0]
    print(f"Total trades in 'Trade': {count}")
    
    if count > 0:
        cursor.execute('''
            SELECT id, symbol, direction, entry_price, exit_price, quantity, 
                   realized_pnl, net_pnl, status, entry_timestamp, exit_timestamp
            FROM Trade 
            ORDER BY id DESC LIMIT 10
        ''')
        
        trades = cursor.fetchall()
        print("\nRecent trades:")
        for t in trades:
            print(f"\nID: {t[0]}")
            print(f"  Symbol: {t[1]} | Direction: {t[2]} | Qty: {t[5]}")
            print(f"  Entry: Rs{t[3]:.2f} @ {t[9]}")
            print(f"  Exit: Rs{t[4] or 0:.2f} @ {t[10] or 'N/A'}")
            print(f"  PnL: Rs{t[6] or 0:.2f} (realized) | Rs{t[7] or 0:.2f} (net)")
            print(f"  Status: {t[8]}")
except Exception as e:
    print(f"Error with 'Trade': {e}")

# Check for GRASIM specifically
print("\n" + "="*100)
print("SEARCHING FOR GRASIM:")
print("="*100)
for table in ['trades', 'Trade']:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE symbol = 'GRASIM'")
        count = cursor.fetchone()[0]
        print(f"GRASIM trades in '{table}': {count}")
        
        if count > 0:
            cursor.execute(f'''
                SELECT id, symbol, direction, entry_price, exit_price, quantity, 
                       realized_pnl, net_pnl, status, entry_timestamp, exit_timestamp
                FROM {table}
                WHERE symbol = 'GRASIM'
                ORDER BY id DESC
            ''')
            
            trades = cursor.fetchall()
            print(f"\nGRASIM trades found:")
            for t in trades:
                print(f"\nID: {t[0]}")
                print(f"  Symbol: {t[1]} | Direction: {t[2]} | Qty: {t[5]}")
                print(f"  Entry: Rs{t[3]:.2f} @ {t[9]}")
                print(f"  Exit: Rs{t[4] or 0:.2f} @ {t[10] or 'N/A'}")
                print(f"  PnL: Rs{t[6] or 0:.2f} (realized) | Rs{t[7] or 0:.2f} (net)")
                print(f"  Status: {t[8]}")
    except Exception as e:
        print(f"Error checking {table}: {e}")

db.close()
