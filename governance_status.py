"""Governance Status Monitor - View AI Investor Policy Status"""
import asyncio
from database import get_db
from risk_engine import RiskEngine

async def main():
    """Show governance status"""
    db = next(get_db())
    
    # Initialize risk engine (which includes governance)
    risk_engine = RiskEngine(db_session=db)
    
    # Update capital from initial value
    await risk_engine.update_available_capital()
    
    # Show governance summary
    print("\n" + "="*60)
    print(risk_engine.governance.get_governance_summary())
    print("="*60)
    print()
    
    # Show key metrics
    print("KEY GOVERNANCE METRICS:")
    print(f"  Daily Loss: Rs{risk_engine.governance.state.daily_loss:,.2f}")
    print(f"  Position Multiplier: {risk_engine.governance.get_position_size_multiplier():.0%}")
    print()
    
    # Show layer details
    print("LAYER ALLOCATIONS:")
    for layer, alloc in risk_engine.governance.layers.items():
        status_icon = "✓" if alloc.is_active else "✗"
        print(f"  {status_icon} {layer.value}:")
        print(f"      Allocation: Rs{alloc.allocation_amount:,.2f} ({alloc.allocation_percent}%)")
        print(f"      Risk/Trade: {alloc.risk_per_trade_percent}%")
        print(f"      Max DD: {alloc.max_layer_drawdown_percent}%")
        print(f"      Current DD: {alloc.current_drawdown_percent:.2f}%")
    print()

if __name__ == "__main__":
    asyncio.run(main())
