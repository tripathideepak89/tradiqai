"""Quick strategy parameter adjuster"""
import sys

print("\n=== STRATEGY PARAMETER ADJUSTER ===\n")
print("Current LiveSimple Strategy Parameters:")
print("  - min_price_change_pct: 1.0%  (Minimum momentum to enter)")
print("  - max_price_change_pct: 5.0%  (Maximum to avoid chasing)")
print("  - stop_loss_pct: 2.0%         (Stop loss below entry)")
print("  - risk_reward_ratio: 2.0      (Target = Entry + 2x Risk)")
print("  - min_confidence: 0.6         (Minimum confidence score)")
print()

print("To make the strategy MORE AGGRESSIVE (more signals):")
print("  1. Lower min_price_change_pct to 0.5% or 0.3%")
print("  2. Lower min_confidence to 0.5")
print()

print("To test with current market conditions:")
print("  Based on live quotes, INFY is at +1.55% momentum")
print("  Current requirement is +1.0% minimum")
print("  BUT INFY is only at 38.1% of day's range (need 70%+)")
print()

print("Suggested adjustments to see action NOW:")
print("  Option 1 (Slightly more aggressive):")
print("    min_price_change_pct = 0.5")
print("    position_near_high = 60%")
print()

print("  Option 2 (Test mode - very aggressive):")
print("    min_price_change_pct = 0.3")
print("    position_near_high = 50%")
print("    min_confidence = 0.5")
print()

print("Edit strategies/live_simple.py lines 23-29 to adjust parameters.")
print("Then restart main.py to apply changes.")
print()

response = input("Would you like to see the exact code to change? (y/n): ")

if response.lower() == 'y':
    print("\n" + "="*60)
    print("COPY THIS CODE to strategies/live_simple.py (lines 23-29):")
    print("="*60)
    print("""
    def __init__(self, parameters: Dict = None):
        default_params = {
            "min_price_change_pct": 0.5,  # ← CHANGED from 1.0
            "max_price_change_pct": 5.0,
            "stop_loss_pct": 2.0,
            "risk_reward_ratio": 2.0,
            "min_price": 50,
            "max_price": 5000,
            "min_confidence": 0.5,  # ← CHANGED from 0.6
        }
""")
    print("="*60)
    print("\nAfter editing, restart main.py:")
    print("  1. Stop main.py (if running)")
    print("  2. Run: python main.py")
    print("  3. Watch live_monitor.py for signals!")
    print()
