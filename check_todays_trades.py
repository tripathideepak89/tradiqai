#!/usr/bin/env python3
"""Check today's trades from database."""
import sqlite3
from datetime import datetime

def check_trades():
    conn = sqlite3.connect('autotrade.db')
    cursor = conn.cursor()
    
    # Get all trades from today
    cursor.execute('''
        SELECT symbol, direction, entry_price, exit_price, quantity, net_pnl, status, 
               entry_timestamp, exit_timestamp, stop_price, target_price
        FROM trades 
        WHERE date(entry_timestamp) = "2026-02-19"
        ORDER BY entry_timestamp
    ''')
    
    trades = cursor.fetchall()
    
    print("=" * 80)
    print("TRADES FOR Feb 19, 2026")
    print("=" * 80)
    
    if not trades:
        print("No trades found for today")
    else:
        total_pnl = 0
        completed_count = 0
        
        for trade in trades:
            symbol, direction, entry, exit_price, qty, pnl, status, entry_time, exit_time, sl, target = trade
            
            print(f"\n{symbol:10} {direction:6}")
            print(f"  Entry: Rs{entry:8.2f} @ {entry_time[:19] if entry_time else 'N/A'}")
            
            if exit_price:
                print(f"  Exit:  Rs{exit_price:8.2f} @ {exit_time[:19] if exit_time else 'N/A'}")
            else:
                print(f"  Exit:  PENDING")
                
            print(f"  Qty:   {qty:3} shares")
            if sl:
                print(f"  SL:    Rs{sl:8.2f}, Target: Rs{target:8.2f}")
            print(f"  Status: {status}")
            
            if pnl is not None:
                print(f"  P/L:   Rs{pnl:8.2f}")
                total_pnl += pnl
                if status in ['COMPLETED', 'CLOSED']:
                    completed_count += 1
            else:
                print(f"  P/L:   PENDING")
                
        print("\n" + "=" * 80)
        print(f"SUMMARY:")
        print(f"  Total Trades: {len(trades)}")
        print(f"  Completed: {completed_count}")
        print(f"  Pending: {len(trades) - completed_count}")
        print(f"  Total Realized P/L: Rs{total_pnl:.2f}")
        print("=" * 80)
    
    # Get all pending orders
    cursor.execute('''
        SELECT symbol, direction, entry_price, quantity, stop_price, target_price, status
        FROM trades 
        WHERE status = 'PENDING'
        ORDER BY entry_timestamp
    ''')
    
    pending = cursor.fetchall()
    
    if pending:
        print(f"\n\nPENDING ORDERS (Not Contributing to P/L):")
        print("-" * 80)
        for p in pending:
            symbol, direction, entry, qty, sl, target, status = p
            print(f"{symbol:10} {direction:6} Entry: Rs{entry:8.2f} Qty: {qty:3} SL: Rs{sl:8.2f} Target: Rs{target:8.2f}")
    
    conn.close()

if __name__ == '__main__':
    check_trades()
