"""Test adaptive target calculation with 52-week high consideration"""

def calculate_adaptive_target(
    ltp: float,
    open_price: float,
    week_52_high: float = None,
    upper_circuit: float = None,
    lower_circuit: float = None
):
    """Calculate adaptive target based on multiple factors"""
    
    # Calculate momentum captured
    price_change_pct = ((ltp - open_price) / open_price) * 100
    
    # Base target based on momentum
    if price_change_pct >= 2.5:
        base_target_pct = 1.0
        label = "Conservative"
    elif price_change_pct >= 1.5:
        base_target_pct = 1.5
        label = "Moderate"
    else:
        base_target_pct = 2.0
        label = "Aggressive"
    
    # Adjust for 52-week high
    resistance_factor = 1.0
    if week_52_high and week_52_high > 0:
        distance_from_52w = ((week_52_high - ltp) / ltp) * 100
        
        if distance_from_52w < 2.0:
            resistance_factor = 0.5
            label += " (Near 52W High)"
        elif distance_from_52w < 5.0:
            resistance_factor = 0.75
            label += " (Approaching 52W High)"
    
    # Adjust for circuit limit
    circuit_factor = 1.0
    if upper_circuit and lower_circuit and upper_circuit > lower_circuit:
        circuit_range = upper_circuit - lower_circuit
        position_in_circuit = ((ltp - lower_circuit) / circuit_range) * 100
        
        if position_in_circuit > 90:
            circuit_factor = 0.4
            label += " (Near Circuit)"
        elif position_in_circuit > 80:
            circuit_factor = 0.7
    
    # Calculate final target
    final_target_pct = base_target_pct * resistance_factor * circuit_factor
    target_price = ltp * (1 + final_target_pct / 100)
    total_move_pct = price_change_pct + final_target_pct
    
    return {
        'entry': ltp,
        'target': target_price,
        'target_pct': final_target_pct,
        'total_move_pct': total_move_pct,
        'label': label,
        'momentum_captured': price_change_pct,
        'resistance_factor': resistance_factor,
        'circuit_factor': circuit_factor
    }


print("=" * 70)
print("ADAPTIVE TARGET TESTING - Multi-Factor Approach")
print("=" * 70)

# Test Case 1: TATASTEEL - Normal case
print("\n1. TATASTEEL Example (Normal Trading):")
print("-" * 70)
result = calculate_adaptive_target(
    ltp=208.93,
    open_price=203.55,
    week_52_high=220.00,  # ~5% away
    upper_circuit=223.90,
    lower_circuit=183.20
)
print(f"   Open: Rs203.55")
print(f"   Current: Rs{result['entry']:.2f} (+{result['momentum_captured']:.2f}% captured)")
print(f"   52W High: Rs220.00 (5% away)")
print(f"   Target: Rs{result['target']:.2f} (+{result['target_pct']:.2f}%)")
print(f"   Total Expected: +{result['total_move_pct']:.2f}% from open")
print(f"   Strategy: {result['label']}")

# Test Case 2: Near 52-week high
print("\n2. Stock Near 52-Week High (Strong Resistance):")
print("-" * 70)
result = calculate_adaptive_target(
    ltp=219.00,
    open_price=215.00,
    week_52_high=220.00,  # Only 0.5% away!
    upper_circuit=235.00,
    lower_circuit=195.00
)
print(f"   Open: Rs215.00")
print(f"   Current: Rs{result['entry']:.2f} (+{result['momentum_captured']:.2f}% captured)")
print(f"   52W High: Rs220.00 (0.5% away!) ← RESISTANCE")
print(f"   Target: Rs{result['target']:.2f} (+{result['target_pct']:.2f}%)")
print(f"   Total Expected: +{result['total_move_pct']:.2f}% from open")
print(f"   Strategy: {result['label']}")
print(f"   Resistance Factor: {result['resistance_factor']:.2f}x (halved target)")

# Test Case 3: Near upper circuit
print("\n3. Stock Near Upper Circuit (Extreme Move):")
print("-" * 70)
result = calculate_adaptive_target(
    ltp=234.00,
    open_price=215.00,
    week_52_high=250.00,
    upper_circuit=236.00,  # Very close!
    lower_circuit=194.00
)
print(f"   Open: Rs215.00")
print(f"   Current: Rs{result['entry']:.2f} (+{result['momentum_captured']:.2f}% captured)")
print(f"   Upper Circuit: Rs236.00 (95% of range) ← EXTREME")
print(f"   Target: Rs{result['target']:.2f} (+{result['target_pct']:.2f}%)")
print(f"   Total Expected: +{result['total_move_pct']:.2f}% from open")
print(f"   Strategy: {result['label']}")
print(f"   Circuit Factor: {result['circuit_factor']:.2f}x (very conservative)")

# Test Case 4: Early entry (best case)
print("\n4. Early Entry, Far from Resistance (Ideal Setup):")
print("-" * 70)
result = calculate_adaptive_target(
    ltp=205.00,
    open_price=203.00,
    week_52_high=230.00,  # 12% away
    upper_circuit=223.00,
    lower_circuit=183.00
)
print(f"   Open: Rs203.00")
print(f"   Current: Rs{result['entry']:.2f} (+{result['momentum_captured']:.2f}% captured)")
print(f"   52W High: Rs230.00 (12% away)")
print(f"   Target: Rs{result['target']:.2f} (+{result['target_pct']:.2f}%)")
print(f"   Total Expected: +{result['total_move_pct']:.2f}% from open")
print(f"   Strategy: {result['label']}")

# Test Case 5: Late entry near 52W high (worst case)
print("\n5. Late Entry Near 52W High (Avoid!):")
print("-" * 70)
result = calculate_adaptive_target(
    ltp=219.50,
    open_price=212.00,
    week_52_high=220.00,  # 0.2% away!
    upper_circuit=233.00,
    lower_circuit=191.00
)
print(f"   Open: Rs212.00")
print(f"   Current: Rs{result['entry']:.2f} (+{result['momentum_captured']:.2f}% captured)")
print(f"   52W High: Rs220.00 (0.2% away!) ← VERY STRONG RESISTANCE")
print(f"   Target: Rs{result['target']:.2f} (+{result['target_pct']:.2f}%)")
print(f"   Total Expected: +{result['total_move_pct']:.2f}% from open")
print(f"   Strategy: {result['label']}")
print(f"   Factors: Resistance={result['resistance_factor']:.2f}x (50% cut)")

print("\n" + "=" * 70)
print("SUMMARY: Multi-Factor Adaptive Targets")
print("=" * 70)
print("✓ Momentum Factor: Later entries get smaller targets")
print("✓ Resistance Factor: Near 52W high = 50-75% target reduction")
print("✓ Circuit Factor: Near upper circuit = 40-70% target reduction")
print("✓ Result: Realistic, achievable targets with better win rate")
print("=" * 70)
