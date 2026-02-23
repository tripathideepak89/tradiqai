# Integration Example - Multi-Timeframe System

## Quick Start

### 1. Test the System (Already Done ✅)

```bash
# Test all components
python test_multi_timeframe.py

# Run 3-year simulation
python portfolio_simulator.py 3 50000

# Check performance (once you have trade data)
python performance_monitor.py 30
```

### 2. Integrate into main.py

```python
from multi_timeframe_manager import MultiTimeframeManager
from trading_styles import TradingStyle

# In your main() function, after initializing broker and db:

# Initialize multi-timeframe manager
mtf_manager = MultiTimeframeManager(
    db_session=db,
    broker=broker,
    total_capital=50000.0  # Your starting capital
)

# In your main trading loop:

async def trading_loop():
    while True:
        # 1. Update market regimes
        await mtf_manager.update_regimes()
        
        # 2. Scan for signals across all active styles
        watchlist = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
        signals = await mtf_manager.scan_for_signals(watchlist)
        
        # 3. Execute signals
        for style, signal_list in signals.items():
            for signal in signal_list:
                # Validate and size position
                validated_signal = mtf_manager.validate_and_size_signal(signal, style)
                
                if validated_signal:
                    logger.info(f"[{style.value}] {signal.action} {signal.symbol} @ Rs{signal.entry_price}")
                    
                    # Execute via your existing order manager
                    await order_manager.execute_signal(validated_signal)
        
        # 4. Check exits for all open positions
        exits = await mtf_manager.check_exits()
        for trade in exits:
            logger.info(f"Exiting {trade.symbol} - {trade.exit_reason}")
            await order_manager.exit_position(trade)
            mtf_manager.record_trade_closed(trade)
        
        # 5. Print portfolio summary (optional)
        if datetime.now().minute % 30 == 0:  # Every 30 minutes
            mtf_manager.print_portfolio_summary()
        
        await asyncio.sleep(60)  # Wait 1 minute
```

### 3. Capital Allocation Breakdown

For Rs50,000 starting capital:

| Style | Allocation | Amount | Expected Return | Max Positions |
|-------|-----------|--------|----------------|---------------|
| Intraday | 20% | Rs10,000 | 15% | 1 |
| Swing | 30% | Rs15,000 | 25% | 3 |
| Mid-Term | 30% | Rs15,000 | 30% | 3 |
| Long-Term | 20% | Rs10,000 | 18% | 3 |
| **Total** | **100%** | **Rs50,000** | **~23%** | **10** |

### 4. What Happens Automatically

✅ **Capital is auto-allocated** - Each style gets its designated %
✅ **Positions are auto-sized** - Based on risk rules (0.7%-3% per trade)
✅ **Regime filtering** - Trades only in favorable market conditions
✅ **Monthly rebalancing** - Adjusts allocations based on performance
✅ **Drawdown protection** - Blocks styles hitting max drawdown
✅ **Performance tracking** - Monitors each style independently

### 5. Expected Behavior

**Month 1:**
- Intraday: 2-4 trades (quick scalps)
- Swing: 1-2 new positions (3-10 day holds)
- Mid-term: 0-1 new position (multi-month hold)
- Long-term: 0-1 new position (annual hold)

**Good Month:**
- Portfolio: +5% to +8%
- Intraday: Small consistent gains
- Swing: 1-2 winners hitting 2R
- Mid-term: Steady appreciation
- Long-term: Dividend + appreciation

**Bad Month:**
- Portfolio: -1% to -3%
- Stops get hit, exits taken
- System reduces exposure
- Capital preserved for recovery

**Year 1 Projection:**
- Starting: Rs50,000
- Expected ending: Rs61,550 (+23%)
- Best case: Rs65,000 (+30%)
- Worst case: Rs55,000 (+10%)

**Year 3 Projection:**
- Starting: Rs50,000
- Expected ending: Rs80,000-92,000 (+60-83%)
- Compounding at ~17-23% annually

### 6. Monitoring

```bash
# Check performance regularly
python performance_monitor.py 30

# Example output:
# ================================
# PORTFOLIO PERFORMANCE (30 days)
# ================================
# Total Capital: Rs51,234
# Total P&L: Rs1,234 (+2.5%)
# Total Trades: 12
# Overall Win Rate: 58.3%
# 
# [INTRADAY] (20%, Expected: 15%)
#   Trades: 6 | Wins: 3 | Losses: 3
#   P&L: Rs200 | Win Rate: 50%
#   Avg R: 0.8R
# 
# [SWING] (30%, Expected: 25%)
#   Trades: 4 | Wins: 3 | Losses: 1
#   P&L: Rs800 | Win Rate: 75%
#   Avg R: 1.5R
```

### 7. Important Rules

**DO:**
✅ Let the system run for 3+ months before judging
✅ Expect red months (normal variance)
✅ Trust the rebalancing logic
✅ Monitor performance monthly
✅ Maintain the watchlist actively

**DON'T:**
❌ Override signals based on emotions
❌ Panic during red weeks
❌ Change allocations arbitrarily
❌ Expect linear returns
❌ Compare single months to annual targets

### 8. Integration Checklist

- [ ] Run `test_multi_timeframe.py` - all tests pass
- [ ] Run `portfolio_simulator.py 3 50000` - see projections
- [ ] Add MultiTimeframeManager to main.py
- [ ] Replace single strategy with multi-style scanning
- [ ] Test with small capital first (Rs10K-20K)
- [ ] Monitor for 1 week to validate execution
- [ ] Scale up to full Rs50K allocation
- [ ] Check performance monthly with monitor script
- [ ] Review and adjust watchlist quarterly

### 9. Troubleshooting

**"No signals generated"**
- Check market regime (might be HIGH_VOLATILITY → reduced activity)
- Verify watchlist symbols are liquid
- Check if styles are blocked due to drawdown

**"All positions are intraday"**
- Swing/mid-term require specific setups (breakouts + volume)
- Long-term requires fundamental data
- Normal to have weeks with only intraday activity

**"Performance lower than expected"**
- Expected returns are ANNUAL, not monthly
- First 50 trades are "learning period"
- Rebalancing takes 3 months to optimize

**"Too many rejected signals"**
- Good! Governance is working
- System protects capital before opportunity
- Quality over quantity

### 10. Next Steps

1. **This Week:** Integrate into main.py, test with current system
2. **Week 2-4:** Monitor execution, validate all 4 styles
3. **Month 2:** First monthly rebalancing occurs
4. **Month 3:** Performance comparison vs expectations
5. **Month 6:** System fully optimized, results visible
6. **Year 1:** First full annual performance review

---

## System Philosophy

> "The goal is not to hit 100% win rate.  
> The goal is to survive, stay consistent, and compound wealth."

This system transforms trading from:
- ❌ High-stress intraday-only → ✅ Diversified multi-timeframe
- ❌ Fantasy 1% daily targets → ✅ Realistic 23% annual
- ❌ No structure → ✅ Professional framework
- ❌ All-or-nothing → ✅ Layered resilience

Let it work. Be patient. Compound.

---

**Ready to integrate? Start with Step 2 above. 🚀**
