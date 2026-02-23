"""Complete P&L calculation including SHORT position closure"""

print("\n" + "="*80)
print("💰 COMPLETE P&L REPORT - ALL POSITIONS CLOSED")
print("="*80 + "\n")

print("PART 1: LONG POSITIONS (Entry → First Exit)")
print("-" * 80)

long_trades = [
    ("NESTLEIND", 1297.90, 1298.50, 5),
    ("DABUR", 509.75, 510.25, 5),
    ("JSWSTEEL", 1249.40, 1250.10, 5),
    ("POWERGRID", 300.20, 299.05, 5),
    ("NTPC", 371.10, 372.60, 5)
]

long_pnl = 0
for symbol, entry, exit1, qty in long_trades:
    pnl = (exit1 - entry) * qty
    long_pnl += pnl
    print(f"{symbol:12} | BUY @ Rs{entry:8.2f} → SELL @ Rs{exit1:8.2f} | P&L: Rs{pnl:+7.2f}")

print(f"\n{'LONG P&L Total:':<50} Rs{long_pnl:+.2f}")

print("\n\nPART 2: SHORT POSITIONS (Second Exit → Buy Back)")
print("-" * 80)

short_trades = [
    ("DABUR", 510.25, 510.30, 5),
    ("NESTLEIND", 1298.50, 1297.70, 5),
    ("JSWSTEEL", 1250.00, 1249.40, 5),
    ("POWERGRID", 299.10, 299.35, 5),
    ("NTPC", 372.60, 372.95, 5)
]

short_pnl = 0
for symbol, sell_price, buy_back, qty in short_trades:
    pnl = (sell_price - buy_back) * qty
    short_pnl += pnl
    print(f"{symbol:12} | SELL @ Rs{sell_price:8.2f} → BUY @ Rs{buy_back:8.2f} | P&L: Rs{pnl:+7.2f}")

print(f"\n{'SHORT P&L Total:':<50} Rs{short_pnl:+.2f}")

print("\n\n" + "="*80)
print("📊 FINAL SUMMARY")
print("="*80)

total_pnl = long_pnl + short_pnl
total_capital = sum([entry * qty for _, entry, _, qty in long_trades])

print(f"\n✅ LONG positions P&L:     Rs{long_pnl:+.2f}")
print(f"✅ SHORT positions P&L:    Rs{short_pnl:+.2f}")
print(f"{'─'*50}")
print(f"💰 TOTAL NET P&L:          Rs{total_pnl:+.2f}")
print(f"📊 Total capital deployed: Rs{total_capital:.2f}")
print(f"📈 Return on capital:      {(total_pnl/total_capital)*100:+.3f}%")

print("\n\n🎯 TRADE SEQUENCE:")
print("-" * 80)
print("1. 12:13-12:17 PM: Opened 5 LONG positions (BUY orders)")
print("2. 14:18 PM:       First exit - Closed LONG positions → +Rs10.75")
print("3. 14:19 PM:       Second exit (error) - Created SHORT positions")
print("4. 14:28 PM:       Closed SHORT positions (buy back) → +Rs3.75")
print("\n✅ All positions successfully closed")
print(f"💰 Final P&L: Rs{total_pnl:+.2f} ({(total_pnl/total_capital)*100:+.3f}%)")
print("="*80 + "\n")
