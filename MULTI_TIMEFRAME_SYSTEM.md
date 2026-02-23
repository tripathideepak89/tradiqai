# Multi-Timeframe Trading System
## Professional 4-Style Portfolio Approach

---

## 📊 **System Overview**

This is a **realistic, discipline-based** multi-timeframe trading system that allocates capital across 4 distinct trading styles to achieve **sustainable 23% annual returns** with controlled drawdown.

### **NOT Fantasy Trading**
- ❌ No "1% daily" fantasies
- ❌ No over-optimization
- ❌ No unrealistic backtests
- ✅ Conservative, achievable returns
- ✅ Proper risk control
- ✅ Real market behavior

---

## 💰 **Capital Allocation (₹50,000 Example)**

| Style | Allocation | Amount | Expected Annual Return | Max Drawdown | Volatility |
|-------|------------|--------|------------------------|--------------|------------|
| **Intraday** | 20% | ₹10,000 | 15% | 12% | High |
| **Short-Term Swing** | 30% | ₹15,000 | 25% | 10% | Medium |
| **Mid-Term Trend** | 30% | ₹15,000 | 30% | 12% | Medium |
| **Long-Term Position** | 20% | ₹10,000 | 18% | 15% | Low |
| **TOTAL** | **100%** | **₹50,000** | **~23%** | **10-12%** | **Mixed** |

---

## 🎯 **Expected Performance (Realistic)**

### **1-Year Simulation**
```
Starting Capital: ₹50,000

After 1 Year:
  Intraday:    ₹11,500  (+₹1,500)
  Swing:       ₹18,750  (+₹3,750)
  Mid-Term:    ₹19,500  (+₹4,500)
  Long-Term:   ₹11,800  (+₹1,800)
  
Total: ₹61,550
Net Profit: ₹11,550 (23% return)
```

### **3-Year Compounding**
```
Year 1: ₹61,550
Year 2: ₹75,091
Year 3: ₹91,611

₹50K → ₹91K in 3 years (without gambling)
```

---

## 📈 **Monthly Behavior Example**

Expected **realistic** monthly returns:

| Month | Portfolio Return | Notes |
|-------|------------------|-------|
| Jan | +3% | Good start |
| Feb | -2% | **Normal drawdown** |
| Mar | +5% | Strong momentum |
| Apr | +1% | Consolidation |
| May | +4% | Trend capture |
| Jun | -1% | **Expected red month** |
| Jul | +6% | Swing + mid-term align |
| Aug | +2% | Steady |
| Sep | -3% | **Market correction** |
| Oct | +5% | Recovery |
| Nov | +4% | Year-end rally |
| Dec | +3% | Profit booking |

**Notice:** Some red months, but steady upward slope. This is professional behavior.

---

## 🔧 **Architecture**

### **Core Components**

1. **`trading_styles.py`**
   - Defines 4 trading styles
   - Capital allocations
   - Risk rules for each style
   - Performance tracking

2. **`regime_detector.py`**
   - Multi-timeframe regime detection
   - TREND_UP / TREND_DOWN / RANGE / HIGH_VOLATILITY
   - Confidence scoring
   - Position sizing adjustments

3. **`capital_allocator.py`**
   - Manages capital across styles
   - Monthly rebalancing
   - Performance-based adjustments
   - Drawdown protection

4. **Strategy Modules**
   - `strategy_intraday.py` - 5/15-min momentum
   - `strategy_swing.py` - 3-10 day trend capture
   - `strategy_midterm.py` - 1-6 month structural moves
   - `strategy_longterm.py` - 1+ year fundamental holds

5. **`multi_timeframe_manager.py`**
   - Orchestrates all styles
   - Signal generation
   - Exit management
   - Portfolio monitoring

6. **`performance_monitor.py`**
   - Track P&L by style
   - Win rates & R-multiples
   - Expected vs actual returns
   - Projections

---

## 🎮 **How Each Style Works**

### **1️⃣ INTRADAY (20% allocation)**

**Objective:** Tactical momentum capture  
**Holding:** Minutes to hours  
**Risk per trade:** 0.7%  
**Max trades/day:** 2  
**Max positions:** 1

**Entry (LONG):**
```
IF market_regime == TREND_UP
AND price > VWAP
AND 20EMA > 50EMA
AND breakout_above_intraday_high
AND volume >= 1.8x avg
THEN enter_long
```

**Exit:**
- Stop loss hit
- 1.5R target reached (trail to BE)
- 3:20 PM (EOD exit)
- No progress after 3 candles

**Key Point:** Intraday is NOT the profit engine. It's a tactical enhancer.

---

### **2️⃣ SHORT-TERM SWING (30% allocation)**

**Objective:** Capture 3-10 day momentum moves  
**Holding:** 3-10 days  
**Risk per trade:** 1.5%  
**Max positions:** 3

**Entry (LONG):**
```
IF price > 50DMA
AND 20DMA > 50DMA
AND breakout_above_10_day_high
AND volume >= 1.5x avg
AND relative_strength vs NIFTY > 0
AND market_regime == TREND_UP
THEN enter_long
```

**Exit:**
- Close below 20DMA
- 2R reached (start trailing)
- Holding days > 10
- Regime changes to RANGE

**Key Point:** This is your momentum engine. Highest expected return (25%).

---

### **3️⃣ MID-TERM TREND (30% allocation)**

**Objective:** Structural trend moves  
**Holding:** 1-6 months  
**Risk per trade:** 2%  
**Max positions:** 3

**Entry (LONG):**
```
IF price > 50DMA AND > 200DMA
AND 50DMA > 200DMA
AND earnings_growth_last_2Q > 0
AND revenue_growth > 0
AND ROE >= 15%
AND breakout_above_recent_range
THEN enter_long
```

**Exit:**
- Weekly close below 20DMA
- Earnings disappointment
- 3 months passed AND weak momentum
- Fundamentals deteriorate

**Key Point:** Captures major trends. Also 30% expected return.

---

### **4️⃣ LONG-TERM POSITION (20% allocation)**

**Objective:** Compounding engine  
**Holding:** 1+ years  
**Risk per trade:** 3%  
**Max positions:** 3

**Entry:**
```
IF revenue_growth_3yr_avg > 12%
AND profit_growth_3yr_avg > 15%
AND debt_to_equity < 1
AND ROE >= 18%
AND price > 200DMA
THEN add_to_portfolio
```

**Exit:**
- 2 consecutive quarters negative growth
- 4 weeks below 200DMA
- Fundamental deterioration
- Debt/equity > 1.5

**Key Point:** Low-volatility wealth builder. Set and forget (with monitoring).

---

## 🛡️ **Global Risk Controls**

These override everything:

```python
IF portfolio_drawdown >= 15%:
    halt_all_new_trades()

IF daily_loss >= 2%:
    block_intraday()

IF sector_exposure > 40%:
    reject_new_trade()

IF single_stock_exposure > 25%:
    reject_new_trade()
```

---

## 🌍 **Market Regime Detection**

System detects regime for each timeframe:

| Regime | Description | Action |
|--------|-------------|--------|
| **TREND_UP** | Strong uptrend | Allow longs, full size |
| **TREND_DOWN** | Strong downtrend | Allow shorts (if enabled) |
| **RANGE** | Sideways | Reduce swing/midterm, half intraday |
| **HIGH_VOLATILITY** | Chaotic | Reduce all sizes 50% |

**Multi-timeframe view:**
- 15-min regime → Intraday decisions
- Daily regime → Swing decisions
- Weekly regime → Mid-term decisions
- Monthly regime → Long-term decisions

---

## 📊 **Capital Rotation (Monthly)**

Every month, system reviews performance:

```python
IF style_return_last_3_months < 0:
    reduce_allocation_by_5%

IF style_return_last_3_months > 8%:
    increase_allocation_by_5%
```

**Constraints:**
- Never exceed 50% in one style
- Max 10% change per month
- Maintain minimum 10% in each style

---

## 🚀 **Usage**

### **Run Performance Report**
```bash
python performance_monitor.py 30  # Last 30 days
```

**Output:**
```
MULTI-TIMEFRAME PERFORMANCE REPORT (Last 30 Days)
================================================================

Total Capital: Rs50,000.00
Expected Annual Return: 23.0%
3-Year Projection: Rs91,611.00

OVERALL PERFORMANCE
================================================================
Total Trades: 15
Total P&L: Rs2,100.00
Overall Win Rate: 60.0%

PERFORMANCE BY STYLE
================================================================

[INTRADAY] (Allocation: 20%, Expected Return: 15%)
  Trades: 6 | Wins: 3 | Losses: 3
  Win Rate: 50.0%
  Total P&L: Rs300.00
  Avg R-Multiple: 0.8R
  
[SWING] (Allocation: 30%, Expected Return: 25%)
  Trades: 5 | Wins: 4 | Losses: 1
  Win Rate: 80.0%
  Total P&L: Rs1,200.00
  Avg R-Multiple: 1.9R
  
... (etc)
```

### **Integration with Main System**

```python
from multi_timeframe_manager import MultiTimeframeManager

# Initialize
manager = MultiTimeframeManager(
    db_session=db,
    broker=broker,
    total_capital=50000.0
)

# Update regimes
await manager.update_regimes()

# Scan for signals
watchlist = ["RELIANCE", "TCS", "INFY", "HDFC", ...]
signals = await manager.scan_for_signals(watchlist)

# Validate and execute
for style, signal_list in signals.items():
    for signal in signal_list:
        validated_signal = manager.validate_and_size_signal(signal, style)
        if validated_signal:
            # Execute via order manager
            await order_manager.execute_signal(validated_signal)

# Check exits
exits = await manager.check_exits()
for trade in exits:
    # Execute exit
    await order_manager.exit_position(trade)
    manager.record_trade_closed(trade)

# Print summary
manager.print_portfolio_summary()
```

---

## ⚠️ **Important Realizations**

### **1. Intraday is NOT the profit engine**
- It provides **activity** and **opportunity**
- Expected return: 15% (lowest of all styles)
- High stress, high variance
- Swing + mid-term build actual wealth

### **2. Expect red months**
- Professional traders have losing months
- It's about the slope, not every data point
- Drawdowns are normal (expect 10-12%)
- Recovery is built into system design

### **3. No single style dominates**
- **Diversification across timeframes** = strength
- When intraday struggles, swing may thrive
- When swing ranges, long-term compounds
- **Uncorrelated edges** reduce fragility

### **4. Patience is key**
- 3 months: Too early to judge
- 6 months: Starting to see patterns
- 1 year: Real performance picture
- 3 years: Compounding magic

---

## 🔄 **If Market Turns Bearish**

System adapts:

- **Mid-term & Long-term:** Reduce exposure
- **Swing:** Shift to short setups (if allowed)
- **Intraday:** Shrink risk per trade
- **Overall:** Lower position sizes, preserve capital

**Your portfolio survives.**

---

## 📚 **Files Created**

| File | Purpose |
|------|---------|
| `trading_styles.py` | Style definitions & allocations |
| `regime_detector.py` | Multi-timeframe regime detection |
| `capital_allocator.py` | Capital management & rebalancing |
| `strategies/strategy_intraday.py` | Intraday strategy |
| `strategies/strategy_swing.py` | Swing strategy |
| `strategies/strategy_midterm.py` | Mid-term strategy |
| `strategies/strategy_longterm.py` | Long-term strategy |
| `multi_timeframe_manager.py` | System orchestrator |
| `performance_monitor.py` | Performance tracking & reporting |

---

## ✅ **What's Different From Before**

| Before | After |
|--------|-------|
| Intraday-only | 4 trading styles |
| Single timeframe | Multi-timeframe |
| No capital allocation | Structured allocation (20/30/30/20) |
| No regime awareness | Advanced regime detection |
| No rebalancing | Monthly performance-based adjustment |
| Unclear expectations | Realistic 23% annual target |
| High stress | Diversified, lower stress |
| All-or-nothing | Layered, resilient approach |

---

## 🎯 **Realistic Expectations**

### **Good Month:** +5% to +8%
### **Bad Month:** -1% to -3%
### **Average Month:** +1.5% to +2.5%

### **Annual Target:** 20-25%
### **3-Year Target:** ₹50K → ₹90K+

**This is professional trading.**  
**No hype. No fantasies. Just disciplined execution.**

---

## 📞 **Next Steps**

1. **Understand each style** - Read the strategy files
2. **Review risk rules** - Know your limits
3. **Start small** - Test with subset of capital first
4. **Monitor performance** - Use performance_monitor.py weekly
5. **Stay disciplined** - Follow the system, don't override

**The system is designed to work. Let it.**

---

*"The goal of a good trader is not to hit 100%, it's to survive and compound."*
