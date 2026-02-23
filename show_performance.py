"""Show today's trading performance"""
import sqlite3
from datetime import datetime

db = sqlite3.connect('autotrade.db')
cursor = db.cursor()

# Check table name (might be 'Trade' with capital T)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
trade_table = 'Trade' if 'Trade' in tables else 'trades'

print(f"Using table: {trade_table}")

# Get today's trades
cursor.execute(f'''
    SELECT symbol, entry_price, exit_price, quantity, 
           direction, status, entry_timestamp, exit_timestamp,
           target_price, stop_price, realized_pnl, net_pnl
    FROM {trade_table}
    WHERE DATE(entry_timestamp) = ?
    ORDER BY entry_timestamp
''', ('2026-02-18',))

trades = cursor.fetchall()

print('\n' + '='*80)
print('📊 TRADING PERFORMANCE - February 18, 2026')
print('='*80)

if not trades:
    print('\n❌ No trades found for today')
else:
    print(f'\n📈 Total Trades: {len(trades)}')
    print('\n' + '-'*80)
    
    total_pnl = 0
    open_trades = []
    closed_trades = []
    
    for trade in trades:
        symbol, entry, exit_p, qty, direction, status, entry_time, exit_time, target, stop, rpnl, net_pnl = trade
        
        if status == 'OPEN':
            open_trades.append(trade)
            print(f'\n🔵 {symbol} - {direction} POSITION (OPEN)')
            print(f'   Entry: Rs{entry:.2f} @ {entry_time}')
        else:
            closed_trades.append(trade)
            pnl = net_pnl if net_pnl else (rpnl if rpnl else 0)
            total_pnl += pnl
            
            if exit_p and entry:
                if direction == 'BUY':
                    pnl_pct = ((exit_p - entry) / entry * 100)
                else:
                    pnl_pct = ((entry - exit_p) / entry * 100)
            else:
                pnl_pct = 0
            
            status_icon = '✅' if pnl > 0 else '❌'
            print(f'\n{status_icon} {symbol} - {status}')
            print(f'   Entry: Rs{entry:.2f} @ {entry_time}')
            exit_time_str = exit_time if exit_time else 'N/A'
            exit_price_str = f'Rs{exit_p:.2f}' if exit_p else 'N/A'
            print(f'   Exit:  {exit_price_str} @ {exit_time_str}')
            print(f'   P&L:   Rs{pnl:.2f} ({pnl_pct:+.2f}%)')
        
        print(f'   Qty: {qty} | Target: Rs{target:.2f} | SL: Rs{stop:.2f}')
    
    if open_trades:
        print('\n' + '-'*80)
        print(f'\n🔵 OPEN POSITIONS ({len(open_trades)}):')
        print('   (Still holding - awaiting target or stop loss)')
        for trade in open_trades:
            symbol, entry, _, qty, direction, _, entry_time, _, target, stop, _, _ = trade
            unrealized = f'Target: Rs{target:.2f}, SL: Rs{stop:.2f}'
            print(f'   • {symbol}: {qty} shares @ Rs{entry:.2f} ({unrealized})')
    
    if closed_trades:
        print('\n' + '-'*80)
        print(f'\n💰 CLOSED TRADES P&L: Rs{total_pnl:.2f}')
        wins = sum(1 for t in closed_trades if ((t[10] or 0) + (t[11] or 0)) > 0)
        losses = len(closed_trades) - wins
        win_rate = (wins / len(closed_trades) * 100) if closed_trades else 0
        print(f'   Wins: {wins} | Losses: {losses} | Win Rate: {win_rate:.1f}%')
    else:
        print('\n' + '-'*80)
        print('\n💰 No closed trades today - All positions still OPEN')

print('\n' + '='*80 + '\n')

db.close()
