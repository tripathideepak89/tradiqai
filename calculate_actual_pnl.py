"""Calculate actual P&L from executed orders"""

print("\n" + "="*80)
print("💰 ACTUAL P&L CALCULATION FROM BROKER DATA")
print("="*80 + "\n")

# Entry trades (12:13-12:17 PM)
entries = {
    "NESTLEIND": {"qty": 5, "price": 1297.90},
    "DABUR": {"qty": 5, "price": 509.75},
    "JSWSTEEL": {"qty": 5, "price": 1249.40},
    "POWERGRID": {"qty": 5, "price": 300.20},
    "NTPC": {"qty": 5, "price": 371.10}
}

# First exit (14:18 PM) - Closed LONG positions
first_exits = {
    "DABUR": {"qty": 5, "price": 510.25},
    "NESTLEIND": {"qty": 5, "price": 1298.50},
    "JSWSTEEL": {"qty": 5, "price": 1250.10},
    "POWERGRID": {"qty": 5, "price": 299.05},
    "NTPC": {"qty": 5, "price": 372.60}
}

# Second exit (14:19 PM) - Created SHORT positions!
second_exits = {
    "DABUR": {"qty": 5, "price": 510.25},
    "NESTLEIND": {"qty": 5, "price": 1298.50},
    "JSWSTEEL": {"qty": 5, "price": 1250.00},
    "POWERGRID": {"qty": 5, "price": 299.10},
    "NTPC": {"qty": 5, "price": 372.60}
}

print("📊 LONG POSITION P&L (Entry → First Exit):")
print("-" * 80)

total_entry_value = 0
total_first_exit_value = 0
long_pnl = 0

for symbol in entries:
    entry = entries[symbol]
    exit1 = first_exits[symbol]
    
    entry_value = entry["qty"] * entry["price"]
    exit_value = exit1["qty"] * exit1["price"]
    pnl = exit_value - entry_value
    
    total_entry_value += entry_value
    total_first_exit_value += exit_value
    long_pnl += pnl
    
    print(f"{symbol:12} | Entry: Rs{entry['price']:.2f} → Exit: Rs{exit1['price']:.2f} | P&L: Rs{pnl:+.2f}")

print(f"\n{'Total LONG P&L:':<12} Rs{long_pnl:+.2f}")
print(f"{'Return:':<12} {(long_pnl/total_entry_value)*100:+.2f}%")

print("\n\n⚠️  SHORT POSITION EXPOSURE (Second Exit - Need to Buy Back!):")
print("-" * 80)

total_short_value = 0

for symbol in second_exits:
    exit2 = second_exits[symbol]
    short_value = exit2["qty"] * exit2["price"]
    total_short_value += short_value
    
    print(f"{symbol:12} | Sold @ Rs{exit2['price']:.2f} | Short {exit2['qty']} shares | Value: Rs{short_value:.2f}")

print(f"\n{'Total SHORT exposure:':<12} Rs{total_short_value:.2f}")

print("\n\n📈 SUMMARY:")
print("-" * 80)
print(f"✅ LONG positions closed    : +Rs{long_pnl:+.2f}")
print(f"⚠️  SHORT positions open     : -5 shares each (need to buy back)")
print(f"💸 Short exposure           : Rs{total_short_value:.2f}")
print("\n⚠️  ACTION REQUIRED: Close SHORT positions by buying back 5 shares each!")
print("="*80 + "\n")
