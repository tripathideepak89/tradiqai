# News Impact Detection System - Integration Guide

## 🎯 Philosophy

**"News does not move price. Surprise + positioning + liquidity imbalance moves price."**

**70% of news moves fade intraday.**

**Trade only when: News Impact + Market Reaction + Tradability ALL confirm.**

---

## 📊 Scoring Model (0-100)

### Component Breakdown

| Component | Weight | Purpose |
|-----------|--------|---------|
| **A) Fundamental Shock** | 0-40 | How much changes long-term value? |
| **B) Novelty & Credibility** | 0-25 | Is it new and trustworthy? |
| **C) Time Sensitivity** | 0-10 | How quickly does it matter? |
| **D) Stock Context** | 0-10 | Is stock "primed" to react? |
| **E) Market Reaction** | 0-15 | **MANDATORY** - Price/volume confirms? |

---

## 🚫 Trade Gating Rules (G1-G4)

Even with high score, **block if**:

### G1) No-confirmation block
- Market Reaction Score < 7/15
- **Action: WATCH** (don't trade)

### G2) Chasing block
- Intraday: Moved > 1.5% already
- Swing: Moved > 4% same day without pullback
- **Action: Wait for pullback**

### G3) Liquidity block
- Spread too wide or volume too low
- **Action: Skip**

### G4) Event risk block
- RBI day, Budget day, Fed speech, etc.
- **Action: Reduce size or disable intraday**

---

## 📈 Action Thresholds

### Intraday

| Score | Action | Position Size |
|-------|--------|---------------|
| 0-39 | **IGNORE** | - |
| 40-59 | **WATCH** | Alerts only |
| 60-74 | **TRADE_MODE** | 70% of normal (reduced) |
| 75-100 | **TRADE_MODE** | 70% of normal (still news risk) |

### Swing/Positional

| Score | Action | Notes |
|-------|--------|-------|
| 0-39 | **IGNORE** | - |
| 40-54 | **WATCH** | Monitor |
| 55+ | **TRADE_MODE** | If A+B ≥ 55 (fundamental strong) |

---

## 🎯 Direction Inference

### Keyword-Based + VWAP Validation

**Bullish Keywords:**
- beat, exceeds, raises, upgrade, win, positive, strong, growth, buyback, dividend increase

**Bearish Keywords:**
- miss, cuts, downgrade, loss, penalty, ban, investigation, fraud, resign, weak, stake sale

**Validation:**
- Bullish news but price < VWAP → **Downgrade confidence**
- Bearish news but price > VWAP → **Downgrade confidence**

---

## 🔷 News Governance Rules

### Rule 1: No Trading 2 Minutes After Breaking News
**Let volatility settle.**

```python
if time_since_news < 120 seconds:
    WAIT
```

### Rule 2: Trade Only If Volume ≥ 2× Average
**News without volume = trap.**

```python
if volume_ratio < 2.0:
    REJECT
```

### Rule 3: Don't Chase > 2% Moves
**Most retail bots enter late.**

```python
if abs(move_pct) > 2.0:
    WAIT for pullback
```

### Rule 4: VWAP Anchor
**Institutional positioning guide.**

```python
if action == "BUY" and price < VWAP:
    REJECT
```

### Rule 5: Reduce Position Size 30% on News
**Volatility increases.**

```python
news_quantity = base_quantity × 0.7
```

---

## 🔥 News Strategy Mode

### Entry Process (High-Impact Positive News)

```
1. Wait first 5-min candle close
   ↓
2. Wait pullback toward VWAP
   ↓
3. Enter on continuation break (new high after pullback)
   ↓
4. Tight stop below VWAP (not % distance)
```

**DO NOT enter on first spike candle.**

---

## 📝 Example Scoring

### Example 1: Exchange Filing - Big Order Win

**News:** "TCS wins $500M deal with European bank"
**Source:** NSE Corporate Filing
**Time:** 10:30 AM

#### Component Scores:
- **A) Fundamental Shock:** 28 (material contract) × 1.0 materiality = **28**
- **B) Novelty & Credibility:** 15 (exchange) + 10 (new) = **25**
- **C) Time Sensitivity:** **8** (immediate)
- **D) Stock Context:** **6** (normal attention)
- **E) Market Reaction:**
  - Volume: 2.5× = 4 points
  - Range: 1.8× ATR = 2 points
  - Structure: Break & hold = 5 points
  - **Total: 11**

#### Result:
- **Total Score: 78/100**
- **Action: TRADE_MODE**
- **Mode: INTRADAY + SWING**
- **Direction: BULLISH**
- **Confidence: HIGH**

#### Gating Checks:
- ✅ G1: Market Reaction 11/15 > 7
- ✅ G2: Moved 1.2% < 1.5%
- ✅ G3: Liquidity OK
- ✅ G4: No event risk

**→ APPROVED FOR TRADING**

---

### Example 2: Random Media Rumor

**News:** "Sources say XYZ may consider expansion"
**Source:** Generic news site
**Time:** 2:15 PM

#### Component Scores:
- **A) Fundamental Shock:** 6 (rumor) × 0.3 materiality = **2**
- **B) Novelty & Credibility:** 6 (generic) + 6 (moderate novelty) = **12**
- **C) Time Sensitivity:** **6** (medium)
- **D) Stock Context:** **5** (normal)
- **E) Market Reaction:**
  - Volume: 1.1× = 0 points
  - Range: 0.9× ATR = 0 points
  - Structure: No break = 0 points
  - **Total: 0**

#### Result:
- **Total Score: 25/100**
- **Action: IGNORE**

#### Gating Checks:
- ❌ G1: Market Reaction 0/15 < 7

**→ BLOCKED - No market confirmation**

---

## 🧠 Institutional Approach

### What Institutions Do:

✅ **Do:**
- Watch liquidity
- Watch order book absorption
- Trade continuation after pullback
- Use VWAP as anchor

❌ **Don't:**
- React instantly
- Chase first spike
- Ignore volume
- Trade headlines blindly

### Your AI Must Mimic This.

---

## 💡 Integration With Existing System

### Pre-Entry Checklist Enhancement

**Old checklist (6 questions):**
1. Was NIFTY trending or flat?
2. Was this first breakout or late entry?
3. Was volume above average?
4. Was stock extended already?
5. Was reward at least 1.5R?
6. Where was nearest resistance?

**+ News Impact (NEW 7th question):**
7. **What is news impact score and market reaction?**
   - If score < 40 → Continue normal strategy
   - If score 40-59 → WATCH mode (alerts)
   - If score 60+ AND E ≥ 7 → Enable news strategy mode

---

## 🔷 Usage Example

```python
from news_impact_detector import NewsImpactDetector, NewsCategory
from news_governance import NewsGovernance

# Initialize
detector = NewsImpactDetector(broker=broker)
governance = NewsGovernance()

# Analyze news
score = await detector.analyze_news_impact(
    headline="TATASTEEL wins Rs5000cr renewable energy contract",
    source="NSE Corporate Filing",
    symbol="TATASTEEL",
    category=NewsCategory.ORDER_WIN,
    timestamp=datetime.now(),
    quote=current_quote
)

# Check governance
passed, violations = governance.check_all_news_governance(
    news_timestamp=score.timestamp,
    current_price=current_quote['ltp'],
    price_at_detection=score.price_at_detection,
    quote=current_quote,
    action="BUY"
)

# Log analysis
score.log_analysis()

# Decision
if score.action == NewsAction.TRADE_MODE and passed:
    # Adjust position size
    base_qty = 100
    news_qty, reason = governance.get_position_size_adjustment(
        base_qty, is_news_trade=True
    )
    
    logger.info(f"✅ News trade approved: {news_qty} shares ({reason})")
    
    # Execute trade with news strategy mode
    # ...
else:
    logger.info(f"❌ Trade blocked: {violations}")
```

---

## 📊 Logging Output Example

```
================================================================================
📰 NEWS IMPACT ANALYSIS
================================================================================
Symbol: TATASTEEL
Headline: TATASTEEL wins Rs5000cr renewable energy contract
Source: NSE Corporate Filing | Time: 10:32:45

📊 IMPACT SCORE BREAKDOWN:
  A) Fundamental Shock:       28.0 / 40
  B) Novelty & Credibility:   25.0 / 25
  C) Time Sensitivity:         8.0 / 10
  D) Stock Context:            6.0 / 10
  E) Market Reaction:         11.0 / 15 ✅
  ─────────────────────────────────
  TOTAL IMPACT SCORE:         78.0 / 100

🎯 ACTION: TRADE_MODE
📈 DIRECTION: BULLISH
⏰ MODE: INTRADAY
🎲 CONFIDENCE: HIGH

💰 PRICE MOVEMENT:
  Detection: Rs208.50
  Current:   Rs210.20 (+0.82%)

================================================================================
```

---

## ⚠️ Important Warnings

### 1. News Fade Reality
**70% of news moves fade intraday.**

Only surprise earnings + large structural change sustain momentum.

### 2. Liquidity Trap Recognition
Example:
```
News: "TATASTEEL announces major export order"

If:
✅ Volume spikes
✅ Breaks intraday high
✅ NIFTY supportive
→ Valid news trade

If:
❌ Price spikes 3%
❌ Immediately reverses
❌ Volume fades
→ Liquidity trap
```

AI must detect this.

### 3. Event Risk Days
**Disable intraday on:**
- RBI policy day
- Budget day
- Fed speech
- Major global shock

---

## 🎯 Success Criteria

### System should LOG before every news trade:

```
📰 News Headline: [headline]
📍 Source: [source]
⏰ Timestamp: [time]
💯 Impact Score: [score breakdown A/B/C/D/E]
🎯 Action: [IGNORE/WATCH/TRADE_MODE]
📈 Direction: [BULLISH/BEARISH/NEUTRAL]
🎲 Confidence: [LOW/MEDIUM/HIGH]
🚦 Gating Checks: [PASSED / violations]
💰 Price: Detection vs Current
🔧 Size Adjustment: [if news trade]
⚙️ Mode: [INTRADAY/SWING/POSITIONAL]
📝 Reason: [why traded / why blocked]
```

**Without logging → no trade allowed.**

---

## 🔥 The Upgrade

### From → To

| Old | New |
|-----|-----|
| Blind execution | News + Order Flow Confluence |
| Ignores context | Reads market reaction |
| Fixed rules | Adaptive to news impact |
| No volatility awareness | Reduces size on news |
| Chases moves | Waits for pullback setup |

---

## 📚 Files Created

1. **`news_impact_detector.py`** (930 lines)
   - Complete scoring model (A+B+C+D+E)
   - Direction inference
   - Gating rules (G1-G4)
   - Detailed logging

2. **`news_governance.py`** (360 lines)
   - 5 governance rules
   - Event risk calendar
   - News strategy mode
   - Position size adjustment

3. **`NEWS_IMPACT_SYSTEM.md`** (This file)
   - Complete documentation
   - Examples and thresholds
   - Integration guide

---

## 🚀 Next Steps

### Phase 1: Detection (Current)
- ✅ Scoring model implemented
- ✅ Gating rules implemented
- ✅ Governance rules implemented

### Phase 2: Integration (Next)
- [ ] Connect to news feed API
- [ ] Integrate with pre_entry_checks.py
- [ ] Add to main trading loop
- [ ] Test with historical news events

### Phase 3: Enhancement (Future)
- [ ] NLP sentiment analysis
- [ ] Pattern recognition (news + price patterns)
- [ ] Machine learning impact prediction
- [ ] Real-time order flow analysis

---

## 💡 Key Insight

**Price confirmation > headline.**

Your system now:
1. Scores news fundamentally (A+B+C+D)
2. **Requires market confirmation (E)** ✅
3. Applies professional gating rules
4. Adjusts risk appropriately

This is how **institutions** trade news.

Not headlines.  
Not rumors.  
**Confirmed reactions.**
