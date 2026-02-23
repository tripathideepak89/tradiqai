"""Analyze last 2 days of trading activity"""
from database import get_db
from models import Trade, TradeStatus, TradeDirection
from datetime import datetime

db = next(get_db())
trades = db.query(Trade).filter(Trade.entry_timestamp >= '2026-02-18').order_by(Trade.entry_timestamp).all()

print('\n' + '='*70)
print('  TRADING ANALYSIS: FEBRUARY 18-19, 2026')
print('='*70 + '\n')

print(f'Total Trades: {len(trades)}\n')

# Group by status
status_counts = {}
for t in trades:
    status = t.status.value
    status_counts[status] = status_counts.get(status, 0) + 1

print('Trade Status Breakdown:')
for status, count in sorted(status_counts.items()):
    print(f'  {status}: {count}')
print()

# Detailed trade list
print('='*70)
print('DETAILED TRADE LIST')
print('='*70 + '\n')

total_pnl = 0
wins = 0
losses = 0
open_positions = 0

for i, t in enumerate(trades, 1):
    pnl = t.realized_pnl if t.realized_pnl else 0
    total_pnl += pnl
    
    if t.status == TradeStatus.CLOSED:
        if pnl > 0:
            wins += 1
            result = f'WIN (+Rs{pnl:.2f})'
        elif pnl < 0:
            losses += 1
            result = f'LOSS (Rs{pnl:.2f})'
        else:
            result = 'BREAKEVEN'
    elif t.status == TradeStatus.OPEN:
        open_positions += 1
        result = 'OPEN'
    else:
        result = t.status.value
    
    print(f'{i}. {t.symbol} ({t.direction.value}) - {result}')
    print(f'   Status: {t.status.value}')
    print(f'   Entry: Rs{t.entry_price:.2f} x {t.quantity} shares')
    entry_time = str(t.entry_timestamp)[:19] if t.entry_timestamp else 'N/A'
    print(f'   Time: {entry_time}')
    print(f'   Stop Loss: Rs{t.stop_price:.2f} | Target: Rs{t.target_price:.2f}')
    
    if t.exit_price:
        print(f'   Exit: Rs{t.exit_price:.2f}')
        exit_time = str(t.exit_timestamp)[:19] if t.exit_timestamp else 'N/A'
        print(f'   Exit Time: {exit_time}')
        pnl_pct = ((t.exit_price - t.entry_price) / t.entry_price * 100)
        if t.direction == TradeDirection.SHORT:
            pnl_pct = -pnl_pct
        print(f'   P&L: Rs{pnl:.2f} ({pnl_pct:+.2f}%)')
    
    print(f'   Strategy: {t.strategy_name}')
    if t.broker_order_id:
        print(f'   Order ID: {t.broker_order_id}')
    if t.notes:
        print(f'   Notes: {t.notes}')
    print()

# Summary
print('='*70)
print('PERFORMANCE SUMMARY')
print('='*70 + '\n')

closed_trades = wins + losses
print(f'Total P&L: Rs{total_pnl:.2f}')
print(f'Closed Trades: {closed_trades} (Wins: {wins}, Losses: {losses})')
print(f'Open Positions: {open_positions}')

if closed_trades > 0:
    win_rate = (wins / closed_trades * 100)
    print(f'Win Rate: {win_rate:.1f}%')
    avg_pnl = total_pnl / closed_trades
    print(f'Average P&L per trade: Rs{avg_pnl:.2f}')

# Breakdown by symbol
print('\nBreakdown by Symbol:')
symbol_stats = {}
for t in trades:
    sym = t.symbol
    if sym not in symbol_stats:
        symbol_stats[sym] = {'count': 0, 'pnl': 0, 'status': []}
    symbol_stats[sym]['count'] += 1
    symbol_stats[sym]['pnl'] += (t.realized_pnl if t.realized_pnl else 0)
    symbol_stats[sym]['status'].append(t.status.value)

for sym, stats in sorted(symbol_stats.items()):
    print(f'  {sym}: {stats["count"]} trades, P&L: Rs{stats["pnl"]:.2f}')
    print(f'    Status: {", ".join(stats["status"])}')

print('\n' + '='*70 + '\n')
