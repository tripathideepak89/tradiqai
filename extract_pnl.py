#!/usr/bin/env python3
"""Extract realized P/L from logs."""
import re

# Read the log file
with open('logs/trading_2026-02-19.log', 'r', encoding='utf-8') as f:
    logs = f.read()

# Find all realised_pnl values
matches = re.findall(r'"realised_pnl":(-?\d+\.?\d*)', logs)

# Get unique non-zero P/L values  
unique_pnls = set([float(m) for m in matches if float(m) != 0])

print("=" * 80)
print("REALIZED P/L VALUES FROM BROKER API (Feb 19, 2026)")
print("=" * 80)

if unique_pnls:
    for pnl in sorted(unique_pnls):
        print(f"Rs{pnl:.2f}")
    print(f"\nTotal: Rs{sum(unique_pnls):.2f}")
else:
    print("No completed trades with realized P/L today")
    
# Also search for any trade completion messages
print("\n" + "=" * 80)
print("CHECKING FOR TRADE COMPLETION MESSAGES")
print("=" * 80)

# Search for any lines mentioning completed trades, profit, loss
completion_lines = []
for line in logs.split('\n'):
    if any(keyword in line.lower() for keyword in ['trade completed', 'profit', 'loss', 'pnl', 'exit']):
        if 'realised_pnl' not in line and 'profit' in line.lower() or 'loss' in line.lower():
            completion_lines.append(line.strip())

if completion_lines:
    for line in completion_lines[:20]:  # Show first 20
        print(line)
else:
    print("No trade completion messages found")
