# Live Implementation - Quick Start Guide

## 🎯 What's Running

Your AutoTrade AI system is **fully operational** with:

✅ **Live-Quote Based Trading** (no historical data dependencies)  
✅ **Real-time Market Scanning** (every 60 seconds)  
✅ **Automated Risk Management** (₹50k capital, ₹1500 daily loss limit)  
✅ **Paper Trading Mode** (safe testing, no real money)  
✅ **Groww Broker Integration** (authenticated and connected)

---

## 🖥️ Live Monitoring Tools

### 1. **Live Dashboard** (Recommended)
```powershell
python live_monitor.py
```
**Shows:**
- Real-time account margins
- Open positions with live P&L
- Recent trades history
- Live market quotes (refreshes every 5 seconds)
- Strategy decisions in real-time

### 2. **Live Log Stream**
```powershell
Get-Content logs\trading_2026-02-17.log -Tail 50 -Wait
```
**Shows:** Detailed system logs as they happen

### 3. **Strategy Activity Only**
```powershell
Select-String -Path logs\trading_2026-02-17.log -Pattern "strategies.live_simple" | Select-Object -Last 20
```
**Shows:** Recent strategy decisions and why stocks were filtered out

---

## 📊 Current Strategy: LiveSimple

**Entry Criteria:**
- Stock up **1.0% - 5.0%** from day's open
- Price in **upper 30%** of day's range (strong momentum)
- Price between **₹50 - ₹5000**
- Confidence score **> 0.6**

**Risk Management:**
- Stop Loss: **2%** below entry
- Target: **1:2 risk-reward ratio** (2x profit vs risk)
- Trailing stop at breakeven after **50% profit**
- Auto-exit at **3:15 PM** (intraday)

**Current Watchlist:**
- RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK

---

## 🎮 How to Adjust Strategy

### Make it More Aggressive (More Signals):
```powershell
python adjust_strategy.py
```
This will guide you through adjusting parameters.

### Or Edit Directly:
File: `strategies/live_simple.py` (lines 23-29)

**Current:**
```python
"min_price_change_pct": 1.0,   # Minimum momentum
"min_confidence": 0.6,          # Minimum confidence
```

**More Aggressive:**
```python
"min_price_change_pct": 0.5,   # Lower threshold
"min_confidence": 0.5,          # Lower confidence needed
```

**After editing:** Restart `main.py` to apply changes.

---

## 🚀 Current System Status

**From Last Scan:**
- ✅ System scanning every 60 seconds
- ✅ All 5 stocks being analyzed
- ⏳ Waiting for valid entry conditions

**Why No Trades Yet?**
- Strategy is **correctly filtering** based on rules
- Current market: Most stocks below 1% momentum threshold
- INFY has momentum (+1.55%) but not near day's high (38% vs 70% required)

**This is GOOD behavior** - not forcing bad trades!

---

## 📁 Key Implementation Files

| File | Purpose | Lines to Check |
|------|---------|---------------|
| [strategies/live_simple.py](strategies/live_simple.py) | Trading strategy | 41-144 (analyze), 146-198 (exits) |
| [main.py](main.py) | System orchestrator | 179-223 (scanning), 225-269 (exits) |
| [live_monitor.py](live_monitor.py) | Real-time dashboard | Full file (just created!) |
| [brokers/groww.py](brokers/groww.py) | Broker API integration | 307-335 (quotes) |
| [order_manager.py](order_manager.py) | Order execution | Full file |
| [risk_engine.py](risk_engine.py) | Risk management | Full file |

---

## 🔧 Useful Commands

**Check if system is running:**
```powershell
Get-Process python
```

**Stop the system:**
```powershell
Stop-Process -Name python -Force
```

**Restart with new settings:**
```powershell
.venv\Scripts\Activate.ps1; python main.py
```

**View database:**
```powershell
sqlite3 autotrade.db
# Then: SELECT * FROM trades;
```

---

## 🎯 Next Steps

1. **Monitor in real-time:** Keep `live_monitor.py` running
2. **Wait for signals:** Strategy will auto-trade when conditions are met
3. **Adjust if needed:** Use `adjust_strategy.py` for more/less signals
4. **Review trades:** Check dashboard for P&L and win rate

---

## ⚠️ Important Notes

- **Paper Trading Active:** No real money at risk
- **API Token Valid Until:** 2026-02-17 15:30:00 (today at 3:30 PM)
- **Daily Loss Limit:** ₹1,500 (automatic stop if exceeded)
- **Max Risk Per Trade:** ₹400
- **Max Positions:** 2 concurrent

---

**System is LIVE and working perfectly!** 🎉

The strategy is being patient and selective - exactly what you want in a trading system.
