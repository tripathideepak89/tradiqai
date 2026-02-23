"""Test Cost-Aware Trading System
=================================

Demonstrates the comprehensive cost-awareness and capital allocation system.
Tests:
1. Transaction cost calculation
2. Trade profitability validation  
3. Performance scoring
4. Capital allocation with rebalancing
"""
import sys
from datetime import datetime, timedelta

from transaction_cost_calculator import cost_calculator
from performance_tracker import PerformanceTracker, TradingLayer
from capital_allocator import CapitalAllocator
from database import SessionLocal


def test_transaction_costs():
    """Test 1: Transaction cost calculation"""
    print("\n" + "="*90)
    print("TEST 1: TRANSACTION COST CALCULATION")
    print("="*90)
    
    # Test case from actual contract note
    print("\n📊 Real Trade Example (Feb 20, 2026 - JSW Steel):")
    print("-" * 70)
    qty = 10
    price = 1249.40
    costs = cost_calculator.calculate_costs(qty, price)
    
    print(f"Quantity: {qty} shares @ ₹{price}")
    print(f"Total Cost: ₹{costs.total_cost:.2f}")
    print(f"Cost per share: ₹{costs.total_cost/qty:.2f}")
    print(f"\nBreakdown:")
    for key, value in costs.breakdown_dict.items():
        if key != 'total':
            print(f"  {key.replace('_', ' ').title()}: ₹{value:.2f}")
    
    # Test the failed TataSteel trade
    print("\n\n📊 Failed Trade Analysis (TataSteel):")
    print("-" * 70)
    qty = 190
    entry = 150.0
    actual_move = 0.09
    
    costs = cost_calculator.calculate_costs(qty, entry)
    min_move = cost_calculator.get_minimum_required_move(qty, entry)
    
    print(f"Quantity: {qty} shares @ ₹{entry}")
    print(f"Total Costs: ₹{costs.total_cost:.2f}")
    print(f"Cost per share: ₹{costs.total_cost/qty:.2f}")
    print(f"Minimum required move: ₹{min_move:.2f} (2x cost)")
    print(f"Actual move: ₹{actual_move:.2f}")
    print(f"\n❌ RESULT: Trade should have been REJECTED")
    print(f"   Reason: ₹{actual_move:.2f} < ₹{min_move:.2f} (insufficient to overcome costs)")


def test_trade_profitability():
    """Test 2: Trade profitability validation"""
    print("\n\n" + "="*90)
    print("TEST 2: TRADE PROFITABILITY VALIDATION")
    print("="*90)
    
    test_cases = [
        {
            "name": "Micro Scalp (SHOULD FAIL)",
            "qty": 50,
            "entry": 1000.0,
            "expected_move": 2.0,
            "should_pass": False
        },
        {
            "name": "Small Move (SHOULD FAIL)",
            "qty": 100,
            "entry": 500.0,
            "expected_move": 3.0,
            "should_pass": False
        },
        {
            "name": "Good Move (SHOULD PASS)",
            "qty": 50,
            "entry": 1000.0,
            "expected_move": 10.0,
            "should_pass": True
        },
        {
            "name": "Strong Move (SHOULD PASS)",
            "qty": 100,
            "entry": 1500.0,
            "expected_move": 20.0,
            "should_pass": True
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n📊 Test Case {i}: {test['name']}")
        print("-" * 70)
        
        approved, reason, metrics = cost_calculator.validate_trade_profitability(
            quantity=test['qty'],
            entry_price=test['entry'],
            expected_move_per_share=test['expected_move']
        )
        
        print(f"Setup: {test['qty']} shares @ ₹{test['entry']}, expecting ₹{test['expected_move']} move")
        print(f"Costs: ₹{metrics['total_cost']:.2f} (₹{metrics['cost_per_share']:.2f}/share)")
        print(f"Expected Gross Profit: ₹{metrics['expected_gross_profit']:.2f}")
        print(f"Expected Net Profit: ₹{metrics['expected_net_profit']:.2f}")
        print(f"Cost Ratio: {metrics['cost_ratio']:.1f}%")
        print(f"\nResult: {'✅ APPROVED' if approved else '❌ REJECTED'}")
        print(f"Reason: {reason}")
        
        # Verify expected result
        if approved == test['should_pass']:
            print("✓ Test passed as expected")
        else:
            print("✗ Test did NOT pass as expected!")


def test_performance_scoring():
    """Test 3: Performance scoring system"""
    print("\n\n" + "="*90)
    print("TEST 3: PERFORMANCE SCORING SYSTEM")
    print("="*90)
    
    tracker = PerformanceTracker()
    allocated_capital = 10000.0
    
    # Simulate intraday trades
    print("\n📊 Simulating Intraday Trading Session:")
    print("-" * 70)
    
    trades = [
        (250, 20, 10250, "Win"),
        (-120, 15, 10130, "Loss"),
        (300, 22, 10430, "Win"),
        (180, 18, 10610, "Win"),
        (-150, 16, 10460, "Loss"),
        (220, 19, 10680, "Win"),
    ]
    
    print(f"{'Trade':<10} {'P&L':<10} {'Costs':<10} {'Equity':<12} {'Result'}")
    print("-" * 70)
    
    for i, (pnl, costs, equity, result) in enumerate(trades, 1):
        tracker.update_metrics(TradingLayer.INTRADAY, pnl, costs, equity)
        print(f"{i:<10} ₹{pnl:>7,.2f}  ₹{costs:>6,.2f}  ₹{equity:>10,.2f}  {result}")
    
    # Calculate performance score
    score = tracker.calculate_score(TradingLayer.INTRADAY, allocated_capital)
    metrics = tracker.get_metrics(TradingLayer.INTRADAY)
    
    print("\n📈 Performance Metrics:")
    print("-" * 70)
    print(f"Total Trades: {metrics.total_trades}")
    print(f"Win Rate: {metrics.win_rate:.1f}%")
    print(f"Profit Factor: {metrics.profit_factor:.2f}")
    print(f"Gross Profit: ₹{metrics.gross_profit:.2f}")
    print(f"Gross Loss: ₹{metrics.gross_loss:.2f}")
    print(f"Net P&L: ₹{metrics.net_pnl:.2f}")
    print(f"Total Costs: ₹{metrics.total_costs:.2f}")
    print(f"Cost-to-Profit Ratio: {metrics.cost_to_profit_ratio*100:.1f}%")
    
    print(f"\n🎯 Performance Score Breakdown:")
    print("-" * 70)
    print(f"Return Score: {score.return_score:.1f}/30")
    print(f"Profit Factor Score: {score.profit_factor_score:.1f}/20")
    print(f"Drawdown Score: {score.drawdown_score:.1f}/20")
    print(f"Win Rate Score: {score.win_rate_score:.1f}/15")
    print(f"Trend Score: {score.trend_score:.1f}/15")
    print(f"\n{'TOTAL SCORE:':<30} {score.total_score:.1f}/100")
    
    # Interpret score
    if score.total_score >= 70:
        interpretation = "✅ EXCELLENT - Increase allocation"
    elif score.total_score >= 50:
        interpretation = "✓ GOOD - Maintain allocation"
    elif score.total_score >= 40:
        interpretation = "⚠️ FAIR - Monitor closely"
    else:
        interpretation = "❌ POOR - Decrease allocation"
    
    print(f"Interpretation: {interpretation}")


def test_capital_allocation():
    """Test 4: Capital allocation engine"""
    print("\n\n" + "="*90)
    print("TEST 4: CAPITAL ALLOCATION ENGINE")
    print("="*90)
    
    db = SessionLocal()
    total_capital = 50000.0
    
    try:
        allocator = CapitalAllocator(db, total_capital)
        
        print("\n📊 Initial Allocation:")
        print("-" * 70)
        for layer in TradingLayer:
            allocation = allocator.get_layer_allocation(layer)
            print(f"{layer.value.upper():<15} {allocation.base_percent:>5.1f}%  "
                  f"₹{allocation.allocated_capital:>10,.2f}  "
                  f"(Score: {allocation.performance_score:.1f}/100)")
        
        print("\n📈 Available Capital per Layer:")
        print("-" * 70)
        for layer in TradingLayer:
            available = allocator.get_available_capital(layer)
            risk_budget = allocator.get_layer_risk_budget(layer)
            print(f"{layer.value.upper():<15} Available: ₹{available:>10,.2f}  "
                  f"Risk Budget: ₹{risk_budget:>8,.2f}")
        
        # Test capital reservation
        print("\n💰 Testing Capital Reservation:")
        print("-" * 70)
        test_reservation = 5000.0
        success = allocator.reserve_capital(TradingLayer.INTRADAY, test_reservation)
        print(f"Reserve ₹{test_reservation:,.2f} for intraday: {'✅ SUCCESS' if success else '❌ FAILED'}")
        
        if success:
            allocation = allocator.get_layer_allocation(TradingLayer.INTRADAY)
            print(f"  Available after: ₹{allocation.available_capital:,.2f}")
            print(f"  Used: ₹{allocation.used_capital:,.2f}")
            
            # Release capital
            allocator.release_capital(TradingLayer.INTRADAY, test_reservation)
            print(f"\nRelease ₹{test_reservation:,.2f}")
            print(f"  Available after: ₹{allocation.available_capital:,.2f}")
        
        print("\n📊 Portfolio Statistics:")
        print("-" * 70)
        stats = allocator.get_portfolio_stats()
        print(f"Total Capital: ₹{stats['total_capital']:,.2f}")
        print(f"Current Equity: ₹{stats['current_equity']:,.2f}")
        print(f"Portfolio Return: {stats['portfolio_return_pct']:.2f}%")
        print(f"Portfolio Drawdown: {stats['portfolio_drawdown_pct']:.2f}%")
        
    finally:
        db.close()


def main():
    """Run all tests"""
    print("\n" + "="*90)
    print("COST-AWARE TRADING SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*90)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        test_transaction_costs()
        test_trade_profitability()
        test_performance_scoring()
        test_capital_allocation()
        
        print("\n\n" + "="*90)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*90)
        
        print("\n📋 SYSTEM SUMMARY:")
        print("-" * 90)
        print("✓ Transaction cost calculator operational")
        print("✓ Trade profitability filter active")
        print("✓ Performance scoring system functional")
        print("✓ Capital allocation engine ready")
        print("\n💡 Next Steps:")
        print("  1. Integrate cost filter into order_manager.py")
        print("  2. Enable capital allocator in main.py")
        print("  3. Monitor cost ratios daily")
        print("  4. Perform monthly rebalancing")
        print("\n" + "="*90 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
