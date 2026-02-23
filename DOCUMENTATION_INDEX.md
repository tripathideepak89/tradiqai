# Documentation Index

**TradiqAI - Complete Documentation Guide**

---

## 📚 Quick Navigation

| Document | Purpose | Key Content |
|----------|---------|-------------|
| **[README.md](README.md)** | Getting started guide | Installation, quick start, features overview |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture | 15+ architecture diagrams and component details |
| **[TRADE_FLOWS.md](TRADE_FLOWS.md)** | Trade lifecycle | State machines, execution flows, algorithms |
| **[COST_AWARE_SYSTEM.md](COST_AWARE_SYSTEM.md)** | Cost filter documentation | Transaction cost analysis and validation |
| **[GROWW_SETUP.md](GROWW_SETUP.md)** | Broker integration | Groww API setup and configuration |
| **[DEPLOYMENT.md](DEPLOYMENT.md)** | Production deployment | Docker, VPS, systemd setup |

---

## 🎨 Architecture Diagrams Index

### System Architecture ([ARCHITECTURE.md](ARCHITECTURE.md))

#### 1. High-Level Architecture
**Diagram Type:** Component Graph  
**Shows:** Complete system with all major components, data stores, and external services  
**Use When:** Understanding overall system design  
**Lines:** 80+  

**Key Components:**
- External services (NSE, Broker, Telegram)
- Strategy layer (3 strategies)
- Risk & validation layer (3 components)
- Execution layer (3 components)
- News & intelligence (3 components)
- Monitoring (2 components)
- Data layer (PostgreSQL, Redis)

---

#### 2. Trade Execution Flow
**Diagram Type:** Sequence Diagram  
**Shows:** Complete trade execution from market data to database save  
**Use When:** Understanding trade approval pipeline  
**Lines:** 60+  

**Flow Steps:**
1. Market Data → Strategy → Technical Analysis
2. Strategy → Pre-Entry Checklist (7 validations)
3. Pre-Entry → Cost Calculator (3 checks)
4. Cost → Risk Engine (7 validations)
5. Risk → Order Manager → Broker
6. Broker → Database → Confirmation

---

#### 3. Cost-Aware Filtering System
**Diagram Type:** Flowchart  
**Shows:** Cost validation logic with 3-layer filtering  
**Use When:** Understanding why trades get rejected on cost  
**Lines:** 40+  

**Decision Points:**
- Has Target? → Calculate expected move
- Expected Move ≥ 2x Cost? → Reject if insufficient
- Cost Ratio ≤ 25%? → Reject if too high
- Net Profit > 0? → Reject if expected loss

**Cost Components:**
- Brokerage: ₹1 per side
- IGST: 18% of brokerage
- STT: 0.025% of turnover
- Exchange: ~0.00325%
- SEBI, Stamp, IPFT

---

#### 4. Risk Management Flow
**Diagram Type:** Flowchart  
**Shows:** Multi-layer risk validation with 7 checks  
**Use When:** Understanding risk control mechanisms  
**Lines:** 50+  

**Risk Checks:**
1. Daily Loss < ₹1,500 (3% limit)
2. Open Positions < 2
3. Consecutive Losses < 3
4. Trade Risk ≤ ₹400
5. Total Exposure < 80%
6. Kill Switch OFF
7. News Governance Clear

---

#### 5. Performance Tracking & Capital Allocation
**Diagram Type:** Flowchart  
**Shows:** 0-100 scoring system and monthly rebalancing  
**Use When:** Understanding performance-based capital allocation  
**Lines:** 60+  

**Scoring Components (0-100):**
- Returns: 30% weight (annualized return)
- Profit Factor: 20% weight (gross profit / loss)
- Drawdown: 20% weight (max peak-to-trough)
- Win Rate: 15% weight (% profitable trades)
- Trend: 15% weight (equity curve slope)

**Rebalancing Rules:**
- Score ≥ 70: +5% allocation (excellent)
- Score < 40: -5% allocation (poor)
- PF < 1.0: Auto-kill strategy (critical)

---

#### 6. News Impact Detection System
**Diagram Type:** Flowchart  
**Shows:** NSE news processing pipeline  
**Use When:** Understanding news-based trading decisions  
**Lines:** 55+  

**Processing Pipeline:**
1. NSE API → Fetch Announcements
2. Deduplication → Skip if seen
3. Normalize → Standard schema
4. Categorize → Earnings/Corporate/Legal
5. Score → 0-100 impact calculation
6. Governance → Block/Allow checks

**Governance Blocking:**
- Burst mode (too many news)
- Circuit limits (extreme volatility)
- Conflicting news (unclear direction)

---

#### 7. Pre-Entry Checklist Flow
**Diagram Type:** Flowchart  
**Shows:** 7-point quality filter for trade validation  
**Use When:** Understanding why setups get rejected  
**Lines:** 70+  

**7-Point Checklist:**
1. **NIFTY Regime:** Trending vs Flat
2. **Breakout Type:** First vs Second/Late
3. **Volume:** Above vs Below average
4. **Extension:** Normal vs Extended vs Highly Extended
5. **Risk/Reward:** ≥ 1.5:1 required
6. **Resistance:** Distance to nearest resistance
7. **Day Type:** Trending vs Choppy

**Decision Logic:**
- Any reject → Block trade
- 4+ pass, 0 reject → Accept (high quality)
- 2-3 pass, 0 reject → Accept with caution (reduce size)

---

#### 8. Data Flow Architecture
**Diagram Type:** Flow Diagram  
**Shows:** Data movement between all system components  
**Use When:** Understanding data dependencies  
**Lines:** 40+  

**Data Sources:**
- Market data (NSE/BSE)
- News feed (NSE announcements)
- User config (.env)

**Data Sinks:**
- Database (persistent storage)
- Redis (fast access cache)
- Dashboard (visualization)
- Telegram (alerts)
- Log files (audit trail)

---

#### 9. Component Interaction Matrix
**Diagram Type:** Table  
**Shows:** Which components read/write to which systems  
**Use When:** Debugging data flow issues  

| Component | Reads From | Writes To | Purpose |
|-----------|------------|-----------|---------|
| Strategy Engine | Market, Broker | DB, Order Mgr | Generate signals |
| Cost Calculator | Signal Data | Risk Engine | Validate profit |
| Risk Engine | Signals, News, Redis | DB, Redis | Multi-layer validation |
| Order Manager | Risk Engine, Broker | DB, Broker API | Execute trades |

---

#### 10. Database Schema
**Diagram Type:** Entity-Relationship Diagram  
**Shows:** Database tables and relationships  
**Use When:** Understanding data persistence  

**Tables:**
1. **Trades** - All trade records (entry, exit, P&L)
2. **DailyMetrics** - Daily aggregated performance
3. **NewsItems** - NSE announcements with impact scores

**Relationships:**
- Trades → DailyMetrics (one-to-many aggregation)
- Trades → NewsItems (many-to-many consideration)

---

#### 11. Deployment Architecture
**Diagram Type:** Infrastructure Diagram  
**Shows:** Docker containers and external services  
**Use When:** Understanding production deployment  
**Lines:** 30+  

**Production Environment:**
- App Container (Python trading system)
- PostgreSQL Container (database)
- Redis Container (cache)
- Dashboard Container (web UI)

**External Services:**
- Broker API (Groww/Zerodha)
- NSE API (market data)
- Telegram Bot API (alerts)

---

### Trade Lifecycle ([TRADE_FLOWS.md](TRADE_FLOWS.md))

#### 12. Trade State Machine
**Diagram Type:** State Diagram  
**Shows:** All 13 possible trade states and transitions  
**Use When:** Understanding trade lifecycle stages  
**Lines:** 70+  

**States:**
1. SignalGenerated
2. PreEntryCheck
3. PreEntryRejected
4. CostValidation
5. CostRejected
6. RiskValidation
7. RiskRejected
8. PendingOrder
9. OrderPlaced
10. OrderRejected
11. Open
12. Monitoring
13. Closed → Completed

**Exit Paths:**
- Target hit (profit)
- Stop loss hit (loss)
- Trailing stop (profit)
- End of day (force close)
- Manual exit (user intervention)

---

#### 13. Complete Trade Execution Timeline
**Diagram Type:** Gantt Chart  
**Shows:** Time breakdown of typical trade execution  
**Use When:** Understanding execution speed  
**Total Time:** ~2 hours (entry to exit)  

**Timeline Breakdown:**
- Signal generation: 16 seconds
- Validation layer: 10 seconds
- Order execution: 5 seconds
- Position monitoring: 2 hours
- Exit execution: 3.5 seconds
- Post-trade: 11 seconds

---

#### 14. System Startup Sequence
**Diagram Type:** Sequence Diagram  
**Shows:** Complete system initialization process  
**Use When:** Debugging startup issues  
**Lines:** 60+  

**Startup Steps:**
1. Initialize database
2. Connect to broker
3. Initialize risk engine (fetch capital)
4. Initialize order manager (sync positions)
5. Load strategies
6. Start news ingestion
7. Start monitoring service
8. Start dashboard (optional)
9. Send startup alert
10. Begin trading loop

---

#### 15. Position Monitoring Loop
**Diagram Type:** Flowchart  
**Shows:** Continuous monitoring logic (runs every 60s)  
**Use When:** Understanding how positions are managed  
**Lines:** 80+  

**Monitoring Checks:**
- Market open?
- Kill switch active?
- For each open position:
  - Price ≥ Target? → Exit at target
  - Price ≤ Stop? → Exit at stop
  - Trailing stop hit? → Exit trailing
  - End of day? → Force close
- Scan for new signals
- Sleep 60 seconds → Repeat

---

#### 16. Daily Performance Calculation Flow
**Diagram Type:** Flowchart  
**Shows:** End-of-day P&L and metrics calculation  
**Use When:** Understanding performance tracking  
**Lines:** 70+  

**Calculation Steps:**
1. Collect all trades for today
2. Classify: Completed vs Carried positions
3. Calculate realized P&L (completed trades)
4. Calculate unrealized P&L (open positions)
5. Calculate metrics (win rate, PF, avg win/loss)
6. Save DailyMetrics record
7. Check daily loss limit (₹1,500)
8. Check consecutive losses (3)
9. Send daily summary alert
10. Update performance scores

---

#### 17. Authentication & Session Management
**Diagram Type:** Sequence Diagram  
**Shows:** Broker authentication flow  
**Use When:** Debugging connection issues  

**Groww Flow:**
1. Load JWT token from storage
2. Authenticate with JWT
3. Session active (no expiry management needed)

**Zerodha Flow:**
1. Load API key/secret
2. Generate login URL
3. User logs in manually
4. Request access token (valid 24 hours)
5. Save token for reuse
6. Token expires → Alert user → Halt trading

---

#### 18. Real-time Data Flow
**Diagram Type:** Flow Diagram  
**Shows:** Data movement from sources to execution  
**Use When:** Understanding latency sources  

**Flow:**
1. Market sources → Quote cache (30s TTL)
2. Cache → Strategy engine (technical analysis)
3. Strategy → Cost filter
4. Cost → Risk engine
5. Risk → Order manager
6. Order → Broker
7. Execution → Performance tracker
8. Performance → Capital allocator
9. Allocator → Adjust position sizing (feedback loop)

---

#### 19. Signal Generation Process
**Diagram Type:** Flowchart  
**Shows:** Technical analysis and signal creation  
**Use When:** Understanding entry logic  
**Lines:** 50+  

**Steps:**
1. Parse market quote (LTP, OHLC, Volume)
2. Update quote cache
3. Calculate indicators (EMA, RSI, VWAP, ATR)
4. Pattern recognition
5. Check setup validity
6. Determine direction (long/short)
7. Calculate levels (entry, stop, target)
8. Create signal object
9. Submit to validation pipeline

**Long Setup Criteria:**
- Price > EMA20 > EMA50
- RSI 40-70
- Volume > 1.5x average

**Short Setup Criteria:**
- Price < EMA20 < EMA50
- RSI 30-60
- Volume > 1.5x average

---

#### 20. Position Sizing Algorithm
**Diagram Type:** Flowchart  
**Shows:** Dynamic position sizing calculation  
**Use When:** Understanding quantity determination  
**Lines:** 60+  

**Algorithm:**
1. Calculate risk per share = |Entry - Stop|
2. Get strategy layer (Intraday/Swing/Mid/Long)
3. Get performance score for layer
4. Base allocation (Intraday 15%, Swing 35%, etc.)
5. Score adjustment:
   - Score ≥ 70: +5%
   - Score < 40: -5%
   - Score 40-69: No change
6. Calculate layer capital = Total × Allocation %
7. Max risk = Min(₹400, Layer Capital × 2%)
8. Quantity = Max Risk / Risk per Share
9. Round down to integer
10. Check quantity ≥ 1
11. Check capital required ≤ ₹12,500
12. Check total exposure < 80%
13. Final quantity approved

---

#### 21. Error Recovery Flows
**Diagram Type:** Flowchart  
**Shows:** Error handling for different failure types  
**Use When:** Debugging system errors  
**Lines:** 70+  

**Error Types:**
1. **Network Error:** Retry 3x with backoff (5s, 15s, 30s)
2. **Auth Error:** Critical alert → Halt trading
3. **Data Error:** Log and skip data point
4. **Database Error:** Retry 3x → Alert if failed
5. **Business Error:** Log rejection → Continue safely

**Recovery Actions:**
- Exponential backoff for retries
- Telegram alerts for critical errors
- Kill switch activation for fatal errors
- State preservation in Redis
- Cleanup and graceful shutdown

---

#### 22. Monthly Rebalancing Workflow
**Diagram Type:** Flowchart  
**Shows:** First-day-of-month capital reallocation  
**Use When:** Understanding dynamic allocation  
**Lines:** 75+  

**Workflow:**
1. First day of month → Trigger rebalancing
2. Fetch last month's trades by layer
3. For each layer:
   - Calculate metrics (returns, PF, DD, WR, trend)
   - Calculate score (0-100)
   - Grade: Excellent/Good/Fair/Poor/Critical
   - Adjust allocation: +5%, 0%, or -5%
4. Normalize all allocations to sum to 100%
5. Validate: Each layer 10-40%, total 100%
6. Save new allocations
7. Generate rebalancing report
8. Send report via Telegram
9. Apply new allocations for current month

---

## 📊 Diagram Statistics

| Document | Diagrams | Total Lines | Diagram Types |
|----------|----------|-------------|---------------|
| ARCHITECTURE.md | 11 | 700+ | Graph, Flowchart, Sequence, Table, ER, Infrastructure |
| TRADE_FLOWS.md | 11 | 900+ | State, Gantt, Sequence, Flowchart |
| **Total** | **22** | **1600+** | **8 types** |

---

## 🎯 Use Case Mapping

### "I want to understand..."

| Question | Relevant Diagram(s) | Document |
|----------|---------------------|----------|
| How the overall system works | #1 High-Level Architecture | ARCHITECTURE.md |
| Why my trade was rejected | #3 Cost Filter, #4 Risk Flow, #7 Pre-Entry | ARCHITECTURE.md |
| How trades flow through the system | #2 Trade Execution Flow, #12 State Machine | ARCHITECTURE.md, TRADE_FLOWS.md |
| How costs are calculated | #3 Cost-Aware Filtering | ARCHITECTURE.md |
| Why position sizes vary | #20 Position Sizing Algorithm | TRADE_FLOWS.md |
| How performance affects allocation | #5 Performance & Allocation, #22 Rebalancing | ARCHITECTURE.md, TRADE_FLOWS.md |
| News-based trading decisions | #6 News Impact Detection | ARCHITECTURE.md |
| Quality of trade setups | #7 Pre-Entry Checklist | ARCHITECTURE.md |
| Data flow and dependencies | #8 Data Flow, #9 Interaction Matrix | ARCHITECTURE.md |
| Database structure | #10 Database Schema | ARCHITECTURE.md |
| Production deployment | #11 Deployment Architecture | ARCHITECTURE.md |
| Trade lifecycle stages | #12 Trade State Machine | TRADE_FLOWS.md |
| Execution speed | #13 Execution Timeline | TRADE_FLOWS.md |
| System startup process | #14 Startup Sequence | TRADE_FLOWS.md |
| Position management | #15 Position Monitoring Loop | TRADE_FLOWS.md |
| Daily P&L calculation | #16 Daily Performance Flow | TRADE_FLOWS.md |
| Broker authentication | #17 Auth & Session | TRADE_FLOWS.md |
| Real-time data latency | #18 Real-time Data Flow | TRADE_FLOWS.md |
| Signal generation logic | #19 Signal Generation | TRADE_FLOWS.md |
| Error handling | #21 Error Recovery | TRADE_FLOWS.md |
| Monthly capital adjustments | #22 Rebalancing Workflow | TRADE_FLOWS.md |

---

## 🔍 Troubleshooting Guide

### Trade was rejected - which diagram to check?

1. **Check logs for rejection reason**
2. **Map to relevant diagram:**
   - "Cost filter rejected" → #3 Cost-Aware Filtering
   - "Failed pre-entry check" → #7 Pre-Entry Checklist
   - "Risk limit exceeded" → #4 Risk Management Flow
   - "Daily loss limit" → #4 Risk Management Flow
   - "News governance blocked" → #6 News Impact Detection

### Performance score is low - how to improve?

1. **Check current score breakdown** → #5 Performance Tracking
2. **Understand scoring formula** → #5 Performance Tracking
3. **Review impact on allocation** → #22 Monthly Rebalancing
4. **Analyze which component is weak:**
   - Returns < 6% annually → Review strategy parameters
   - Profit Factor < 1.5 → Reduce # of trades, improve quality
   - Max Drawdown > 10% → Tighten stops, reduce position size
   - Win Rate < 50% → Use pre-entry checklist more strictly
   - Negative trend → System adaptation needed

### System is not trading - what to check?

1. **Market hours?** → Check market timing
2. **Kill switch active?** → Check Redis/monitoring
3. **Daily loss limit hit?** → Check #16 Daily Performance
4. **All signals failing validation?** → Check #2, #3, #4, #7
5. **Broker connection issue?** → Check #17 Auth & Session
6. **Position limit reached?** → Check #4 Risk Management

---

## 📚 Additional Documentation

| File | Purpose |
|------|---------|
| README.md | Getting started, installation, quick start |
| COST_AWARE_SYSTEM.md | Detailed cost analysis with real examples |
| GROWW_SETUP.md | Broker API integration guide |
| DEPLOYMENT.md | Production deployment (Docker, VPS, systemd) |
| PROFESSIONAL_DISCIPLINE.md | Trading discipline and best practices |
| NEWS_IMPACT_SYSTEM.md | News system implementation details |
| MULTI_TIMEFRAME_SYSTEM.md | Multi-timeframe strategy architecture |

---

## 🎓 Learning Path

**For New Users:**
1. Start with [README.md](README.md) - Understand features and setup
2. Read [ARCHITECTURE.md](ARCHITECTURE.md) #1 - See the big picture
3. Review [TRADE_FLOWS.md](TRADE_FLOWS.md) #12 - Understand trade lifecycle
4. Study #3 Cost Filter and #4 Risk Management - Key safety mechanisms

**For Developers:**
1. Review all diagrams in ARCHITECTURE.md - System design
2. Study #2 Trade Execution Flow - Core pipeline
3. Examine #8 Data Flow and #9 Interaction Matrix - Dependencies
4. Review #10 Database Schema - Data model
5. Study TRADE_FLOWS.md #19-22 - Core algorithms

**For Traders:**
1. Focus on #7 Pre-Entry Checklist - Quality filters
2. Understand #3 Cost-Aware Filtering - Why trades are blocked
3. Review #5 Performance Tracking - How you're measured
4. Study #20 Position Sizing - Why quantities vary

---

**Built with ❤️ for algorithmic trading in Indian markets**
