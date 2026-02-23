# System Architecture

**AutoTrade AI - Algorithmic Trading System for Indian Markets**

## 🏗️ High-Level Architecture

```mermaid
graph TB
    subgraph "External Services"
        NSE[NSE API<br/>Market Data]
        Broker[Broker API<br/>Groww/Zerodha]
        Telegram[Telegram Bot<br/>Alerts]
    end
    
    subgraph "Trading System Core"
        Main[Main Controller<br/>main.py]
        
        subgraph "Strategy Layer"
            StrategyEngine[Strategy Engine]
            LiveSimple[LiveSimple Strategy]
            Intraday[Intraday Strategy]
            Swing[Swing Strategy]
        end
        
        subgraph "Risk & Validation"
            CostCalc[Transaction Cost<br/>Calculator]
            RiskEngine[Risk Engine<br/>Multi-layer Validation]
            PreEntry[Pre-Entry<br/>Checklist]
        end
        
        subgraph "Execution Layer"
            OrderMgr[Order Manager<br/>Trade Execution]
            CapAlloc[Capital Allocator<br/>Dynamic Sizing]
            PerfTracker[Performance Tracker<br/>0-100 Scoring]
        end
        
        subgraph "News & Intelligence"
            NewsIngest[News Ingestion<br/>NSE Polling]
            NewsDetector[Impact Detector<br/>Scoring]
            NewsGov[News Governance<br/>Risk Rules]
        end
        
        subgraph "Monitoring"
            Monitor[Monitoring Service<br/>Health Checks]
            Dashboard[Web Dashboard<br/>Real-time UI]
        end
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL/SQLite<br/>Trade History)]
        Redis[(Redis<br/>Real-time State)]
    end
    
    NSE --> NewsIngest
    NSE --> StrategyEngine
    
    Broker --> StrategyEngine
    Broker --> OrderMgr
    
    Main --> StrategyEngine
    Main --> NewsIngest
    Main --> Monitor
    
    StrategyEngine --> LiveSimple
    StrategyEngine --> Intraday
    StrategyEngine --> Swing
    
    LiveSimple --> PreEntry
    Intraday --> PreEntry
    Swing --> PreEntry
    
    PreEntry --> CostCalc
    CostCalc --> RiskEngine
    RiskEngine --> OrderMgr
    
    OrderMgr --> CapAlloc
    OrderMgr --> Broker
    
    NewsIngest --> NewsDetector
    NewsDetector --> NewsGov
    NewsGov --> RiskEngine
    
    OrderMgr --> DB
    PerfTracker --> DB
    Monitor --> DB
    Dashboard --> DB
    
    RiskEngine --> Redis
    Monitor --> Redis
    
    Monitor --> Telegram
    Dashboard --> Telegram
    
    PerfTracker --> CapAlloc
    
    style CostCalc fill:#ff6b6b
    style RiskEngine fill:#ff6b6b
    style OrderMgr fill:#4ecdc4
    style DB fill:#95e1d3
    style Redis fill:#95e1d3
```

## 📊 Component Details

### 1. Strategy Layer
- **LiveSimple Strategy**: Professional intraday with pre-entry checklist
- **Intraday Strategy**: EMA-based pullback system
- **Swing Strategy**: Breakout trading system
- Multi-timeframe support (intraday/swing/mid/long)

### 2. Risk & Validation
- **Transaction Cost Calculator**: Validates profitability before execution
- **Risk Engine**: Multi-layer validation (capital, exposure, limits)
- **Pre-Entry Checklist**: 7-point quality filter

### 3. Execution Layer
- **Order Manager**: Broker integration and trade lifecycle
- **Capital Allocator**: Dynamic allocation with performance-based rebalancing
- **Performance Tracker**: Real-time scoring (0-100) across 5 dimensions

### 4. News & Intelligence
- **News Ingestion**: NSE announcements polling with burst mode
- **Impact Detector**: Sentiment scoring and action recommendation
- **News Governance**: Risk rules and blocking logic

### 5. Data Layer
- **PostgreSQL/SQLite**: Persistent storage for trades, news, metrics
- **Redis**: Real-time state, kill switch, governance

---

## 🔄 Trade Execution Flow

```mermaid
sequenceDiagram
    participant Market as Market Data
    participant Strategy as Strategy Engine
    participant PreCheck as Pre-Entry Checklist
    participant Cost as Cost Calculator
    participant Risk as Risk Engine
    participant Order as Order Manager
    participant Broker as Broker API
    participant DB as Database
    
    Market->>Strategy: Live Quote
    Strategy->>Strategy: Technical Analysis
    
    alt Signal Generated
        Strategy->>PreCheck: Validate Setup Quality
        
        PreCheck->>PreCheck: Check NIFTY Regime
        PreCheck->>PreCheck: Check Breakout Type
        PreCheck->>PreCheck: Validate Volume
        PreCheck->>PreCheck: Check Extension
        PreCheck->>PreCheck: Verify R:R ≥ 1.5
        PreCheck->>PreCheck: Check Resistance
        
        alt Quality Check Failed
            PreCheck-->>Strategy: ❌ REJECT - Quality Issue
        else Quality Check Passed
            PreCheck->>Cost: Validate Signal
            
            Cost->>Cost: Calculate Entry/Exit Costs
            Cost->>Cost: Expected Move ≥ 2x Cost?
            Cost->>Cost: Cost Ratio ≤ 25%?
            Cost->>Cost: Net Profit > 0?
            
            alt Cost Check Failed
                Cost-->>Strategy: ❌ REJECT - Cost Filter
            else Cost Check Passed
                Cost->>Risk: Approve Trade
                
                Risk->>Risk: Check Daily Loss Limit
                Risk->>Risk: Check Position Limits
                Risk->>Risk: Check Exposure
                Risk->>Risk: Validate with News Governance
                
                alt Risk Check Failed
                    Risk-->>Strategy: ❌ REJECT - Risk Limit
                else Risk Check Passed
                    Risk->>Order: Execute Signal
                    
                    Order->>Order: Calculate Position Size
                    Order->>Broker: Place Order
                    
                    Broker-->>Order: Order Confirmation
                    Order->>DB: Save Trade Record
                    
                    DB-->>Order: ✅ Trade Saved
                    Order-->>Strategy: ✅ TRADE EXECUTED
                end
            end
        end
    else No Signal
        Strategy-->>Market: Continue Monitoring
    end
```

---

## 💰 Cost-Aware Filtering System

```mermaid
flowchart TD
    Start([Signal Generated]) --> HasTarget{Target<br/>Provided?}
    
    HasTarget -->|Yes| CalcMove[Calculate Expected Move<br/>= |Target - Entry|]
    HasTarget -->|No| MinCost[Use Minimum Cost Check<br/>2x per-share cost]
    
    CalcMove --> GetCosts[Get Transaction Costs<br/>Brokerage + IGST + STT<br/>+ Exchange + SEBI + Stamp]
    
    GetCosts --> Check1{Expected Move<br/>≥ 2x Cost?}
    
    Check1 -->|No| Reject1[❌ REJECT<br/>Insufficient move<br/>to overcome costs]
    Check1 -->|Yes| Check2{Cost Ratio<br/>≤ 25%?}
    
    Check2 -->|No| Reject2[❌ REJECT<br/>Cost ratio too high<br/>Low profit margin]
    Check2 -->|Yes| Check3{Net Profit<br/>> 0?}
    
    Check3 -->|No| Reject3[❌ REJECT<br/>Expected loss<br/>after costs]
    Check3 -->|Yes| Approve[✅ APPROVED<br/>Cost filter passed]
    
    MinCost --> Warn[⚠️ WARNING<br/>No target - minimum<br/>move required]
    
    Approve --> RiskCheck[Proceed to<br/>Risk Engine]
    Reject1 --> End([Trade Blocked])
    Reject2 --> End
    Reject3 --> End
    Warn --> RiskCheck
    
    RiskCheck --> Done([Continue Execution])
    
    style Approve fill:#90EE90
    style Reject1 fill:#FFB6C1
    style Reject2 fill:#FFB6C1
    style Reject3 fill:#FFB6C1
    style Warn fill:#FFE4B5
```

### Cost Calculation Formula

```
Total Cost = Brokerage + IGST + STT + Exchange + SEBI + Stamp + IPFT

Where:
- Brokerage: ₹1 per side (entry + exit = ₹2)
- IGST: 18% of brokerage
- STT: 0.025% of (entry_value + exit_value) for intraday
- Exchange: ~0.00325% of turnover
- SEBI: ₹10 per crore
- Stamp Duty: 0.003% of buy value
- IPFT: Negligible

Validations:
1. Expected move ≥ 2x cost per share (safety buffer)
2. Cost ratio ≤ 25% of expected profit
3. Net profit = Gross profit - Total costs > 0
```

---

## 🛡️ Risk Management Flow

```mermaid
flowchart TD
    Signal[Trade Signal<br/>with Cost Approval] --> Check1{Daily Loss<br/>< ₹1,500?}
    
    Check1 -->|No| Block1[❌ BLOCK<br/>Daily loss limit hit<br/>System halted]
    Check1 -->|Yes| Check2{Open Positions<br/>< 2?}
    
    Check2 -->|No| Block2[❌ BLOCK<br/>Max positions reached]
    Check2 -->|Yes| Check3{Consecutive<br/>Losses < 3?}
    
    Check3 -->|No| Block3[❌ BLOCK<br/>Pattern of losses<br/>System paused]
    Check3 -->|Yes| Check4{Trade Risk<br/>≤ ₹400?}
    
    Check4 -->|No| Reduce[Reduce Position Size<br/>to meet risk limit]
    Check4 -->|Yes| Check5{Total Exposure<br/>< 80%?}
    
    Reduce --> Check5
    
    Check5 -->|No| Block4[❌ BLOCK<br/>Exposure limit exceeded]
    Check5 -->|Yes| Check6{Kill Switch<br/>OFF?}
    
    Check6 -->|No| Block5[❌ BLOCK<br/>Manual kill switch<br/>activated]
    Check6 -->|Yes| NewsCheck{News<br/>Governance<br/>Clear?}
    
    NewsCheck -->|Blocked| Block6[❌ BLOCK<br/>News-based restriction]
    NewsCheck -->|Clear| Approved[✅ APPROVED<br/>All risk checks passed]
    
    Block1 --> Notify[Send Telegram Alert]
    Block2 --> Notify
    Block3 --> Notify
    Block4 --> Notify
    Block5 --> Notify
    Block6 --> Notify
    
    Approved --> Execute[Execute Trade]
    Notify --> Log[Log to Database]
    
    style Approved fill:#90EE90
    style Block1 fill:#FFB6C1
    style Block2 fill:#FFB6C1
    style Block3 fill:#FFB6C1
    style Block4 fill:#FFB6C1
    style Block5 fill:#FFB6C1
    style Block6 fill:#FFB6C1
```

---

## 📈 Performance Tracking & Capital Allocation

```mermaid
flowchart TD
    Trades[Completed Trades] --> Collect[Collect Metrics:<br/>Win Rate, Profit Factor<br/>Drawdown, Returns]
    
    Collect --> Score[Calculate Score<br/>0-100 Scale]
    
    Score --> Components{Score Components}
    
    Components --> Ret[Returns: 30%<br/>Annualized return vs target]
    Components --> PF[Profit Factor: 20%<br/>Gross profit / Gross loss]
    Components --> DD[Drawdown: 20%<br/>Max peak-to-trough]
    Components --> WR[Win Rate: 15%<br/>% profitable trades]
    Components --> Trend[Trend: 15%<br/>Equity curve slope]
    
    Ret --> Total[Total Score]
    PF --> Total
    DD --> Total
    WR --> Total
    Trend --> Total
    
    Total --> Grade{Score Grade}
    
    Grade -->|90-100| Excellent[🏆 EXCELLENT<br/>Increase allocation +5%]
    Grade -->|70-89| Good[✅ GOOD<br/>Maintain allocation]
    Grade -->|50-69| Fair[⚠️ FAIR<br/>Monitor closely]
    Grade -->|40-49| Poor[❌ POOR<br/>Decrease allocation -5%]
    Grade -->|0-39| Critical[🚨 CRITICAL<br/>Kill strategy]
    
    Excellent --> Rebalance[Monthly Rebalancing]
    Good --> Rebalance
    Fair --> Rebalance
    Poor --> Rebalance
    Critical --> Kill[Auto-disable Strategy]
    
    Rebalance --> Layers{Layer Allocations}
    
    Layers --> Intra[Intraday: Base 15%<br/>±5% adjustment]
    Layers --> SwingL[Swing: Base 35%<br/>±5% adjustment]
    Layers --> Mid[Mid-term: Base 35%<br/>±5% adjustment]
    Layers --> Long[Long-term: Base 15%<br/>±5% adjustment]
    
    Intra --> Apply[Apply to Next Month]
    SwingL --> Apply
    Mid --> Apply
    Long --> Apply
    
    Kill --> Alert[Telegram Alert:<br/>Strategy Disabled]
    
    style Excellent fill:#90EE90
    style Good fill:#B0E57C
    style Fair fill:#FFE4B5
    style Poor fill:#FFB6C1
    style Critical fill:#FF6B6B
```

### Performance Scoring Formula

```
Total Score = (Returns × 0.30) + (PF × 0.20) + (DD × 0.20) + (WR × 0.15) + (Trend × 0.15)

Component Scoring:
1. Returns (0-30):    Scale annualized return against 6-15% target
2. Profit Factor (0-20): PF > 2.0 = 20, PF 1.5-2.0 = 15, PF 1.0-1.5 = 10
3. Drawdown (0-20):   < 5% = 20, 5-10% = 15, 10-15% = 10, > 15% = 0
4. Win Rate (0-15):   Scale 30-70% to score
5. Trend (0-15):     Positive slope = 15, Flat = 7, Negative = 0

Rebalancing Rules:
- Score ≥ 70: Increase allocation by +5%
- Score < 40: Decrease allocation by -5%
- PF < 1.0:   Auto-kill strategy regardless of score
- Monthly execution
```

---

## 📡 News Impact Detection System

```mermaid
flowchart TD
    NSE[NSE API] -->|Poll Every 30-60s| Fetch[Fetch Announcements]
    
    Fetch --> Dedupe{Duplicate?}
    
    Dedupe -->|Yes| Skip[Skip - Already Processed]
    Dedupe -->|No| Normalize[Normalize to<br/>Standard Schema]
    
    Normalize --> Categorize[Categorize:<br/>Earnings, Corporate,<br/>Legal, Regulatory]
    
    Categorize --> Score[Calculate Impact Score<br/>0-100]
    
    Score --> Keywords[Keyword Analysis:<br/>Positive vs Negative]
    Keywords --> Context[Context Scoring:<br/>Past announcements]
    
    Context --> Impact{Impact Level}
    
    Impact -->|High 70-100| HighAction[Action: TRADE<br/>Direction: BULLISH/BEARISH]
    Impact -->|Medium 40-69| MedAction[Action: WATCH<br/>Monitor closely]
    Impact -->|Low 0-39| LowAction[Action: IGNORE<br/>No impact]
    
    HighAction --> Govern{Governance<br/>Check}
    MedAction --> Govern
    LowAction --> Store[Store in Database]
    
    Govern --> G1{Burst Mode?<br/>Too many news}
    
    G1 -->|Yes| Block1[Block: News overload<br/>Wait for clarity]
    G1 -->|No| G2{Circuit Limit?<br/>Price movement}
    
    G2 -->|Yes| Block2[Block: Extreme volatility<br/>Unsafe to trade]
    G2 -->|No| G3{Conflicting News?<br/>Mixed signals}
    
    G3 -->|Yes| Block3[Block: Unclear direction<br/>Wait for resolution]
    G3 -->|No| Allow[✅ Allow Trading<br/>Adjust position size]
    
    Block1 --> Store
    Block2 --> Store
    Block3 --> Store
    Allow --> Store
    
    Store --> Dashboard[Display in<br/>Dashboard Feed]
    Store --> RiskEngine[Send to<br/>Risk Engine]
    
    style HighAction fill:#FFB6C1
    style MedAction fill:#FFE4B5
    style LowAction fill:#E0E0E0
    style Allow fill:#90EE90
    style Block1 fill:#FFB6C1
    style Block2 fill:#FFB6C1
    style Block3 fill:#FFB6C1
```

---

## 🎯 Pre-Entry Checklist Flow

```mermaid
flowchart TD
    Signal[Technical Signal<br/>Generated] --> Q1{NIFTY Regime:<br/>Trending or Flat?}
    
    Q1 -->|FLAT| Flag1[⚠️ Low Win Rate<br/>Reduce confidence]
    Q1 -->|TRENDING| Pass1[✅ Favorable<br/>High win rate]
    Q1 -->|UNKNOWN| Neutral1[⚠️ Unknown<br/>Proceed with caution]
    
    Flag1 --> Q2
    Pass1 --> Q2
    Neutral1 --> Q2
    
    Q2{Breakout Type:<br/>First or Second?}
    
    Q2 -->|FIRST| Pass2[✅ Fresh Setup<br/>Higher success]
    Q2 -->|SECOND/LATE| Flag2[⚠️ Late Entry<br/>Lower success rate]
    
    Pass2 --> Q3
    Flag2 --> Q3
    
    Q3{Volume:<br/>Above Average?}
    
    Q3 -->|YES| Pass3[✅ Strong Participation<br/>Confirms move]
    Q3 -->|NO| Flag3[⚠️ Weak Volume<br/>Low conviction]
    
    Pass3 --> Q4
    Flag3 --> Q4
    
    Q4{Extension Level:<br/>Already Moved?}
    
    Q4 -->|NORMAL| Pass4[✅ Room to Run<br/>Good entry]
    Q4 -->|EXTENDED| Reject1[❌ REJECT<br/>Already overextended<br/>Risk of pullback]
    Q4 -->|HIGHLY_EXTENDED| Reject1
    
    Pass4 --> Q5
    
    Q5{Risk/Reward:<br/>≥ 1.5:1?}
    
    Q5 -->|YES| Pass5[✅ Good R:R<br/>Worth the risk]
    Q5 -->|NO| Reject2[❌ REJECT<br/>Insufficient reward<br/>for risk taken]
    
    Pass5 --> Q6
    
    Q6{Resistance Level:<br/>Clear Path?}
    
    Q6 -->|FAR >2%| Pass6[✅ Clear Path<br/>Good runway]
    Q6 -->|NEAR 0.5-2%| Flag6[⚠️ Resistance Nearby<br/>May stall]
    Q6 -->|VERY_NEAR <0.5%| Reject3[❌ REJECT<br/>Too close to resistance<br/>Limited upside]
    
    Pass6 --> Q7
    Flag6 --> Q7
    
    Q7{Day Type:<br/>Trending or Choppy?}
    
    Q7 -->|TRENDING| Pass7[✅ Trending Day<br/>Favorable conditions]
    Q7 -->|CHOPPY| Flag7[⚠️ Choppy Market<br/>Lower confidence]
    Q7 -->|UNKNOWN| Neutral7[⚠️ Unknown Day Type<br/>Proceed carefully]
    
    Pass7 --> Evaluate
    Flag7 --> Evaluate
    Neutral7 --> Evaluate
    
    Evaluate[Evaluate All Factors] --> Decision{Decision}
    
    Decision -->|4+ Pass, 0 Reject| Accept[✅ ACCEPT<br/>High Quality Setup]
    Decision -->|2-3 Pass, 0 Reject| Caution[⚠️ ACCEPT WITH CAUTION<br/>Reduce position size]
    Decision -->|Any Reject| Reject[❌ REJECT<br/>Failed quality check]
    
    Reject1 --> Reject
    Reject2 --> Reject
    Reject3 --> Reject
    
    Accept --> CostFilter[Proceed to<br/>Cost Filter]
    Caution --> CostFilter
    Reject --> End([Trade Blocked])
    
    style Accept fill:#90EE90
    style Caution fill:#FFE4B5
    style Reject fill:#FFB6C1
    style Reject1 fill:#FFB6C1
    style Reject2 fill:#FFB6C1
    style Reject3 fill:#FFB6C1
```

---

## 🔄 Data Flow Architecture

```mermaid
flowchart LR
    subgraph "Input Sources"
        Market[Market Data<br/>NSE/BSE]
        News[News Feed<br/>NSE Announcements]
        User[User Config<br/>.env file]
    end
    
    subgraph "Processing Layer"
        Strategy[Strategy Engine<br/>Signal Generation]
        Cost[Cost Calculator<br/>Profitability]
        Risk[Risk Engine<br/>Validation]
        NewsProc[News Processor<br/>Impact Scoring]
    end
    
    subgraph "Execution Layer"
        Order[Order Manager<br/>Trade Execution]
        Broker[Broker API<br/>Orders/Positions]
    end
    
    subgraph "Storage Layer"
        DB[(Database<br/>Persistent)]
        Cache[(Redis<br/>Fast Access)]
    end
    
    subgraph "Output Layer"
        Dashboard[Web Dashboard<br/>Visualization]
        Alerts[Telegram Alerts<br/>Notifications]
        Logs[Log Files<br/>Audit Trail]
    end
    
    Market --> Strategy
    News --> NewsProc
    User --> Strategy
    User --> Risk
    
    Strategy --> Cost
    Cost --> Risk
    NewsProc --> Risk
    
    Risk --> Order
    Order --> Broker
    
    Broker --> DB
    Order --> DB
    Strategy --> DB
    NewsProc --> DB
    
    Risk --> Cache
    Order --> Cache
    
    DB --> Dashboard
    Cache --> Dashboard
    DB --> Alerts
    
    Order --> Logs
    Strategy --> Logs
    Risk --> Logs
    
    style DB fill:#95e1d3
    style Cache fill:#95e1d3
    style Dashboard fill:#4ecdc4
    style Alerts fill:#feca57
```

---

## 🎛️ Component Interaction Matrix

| Component | Reads From | Writes To | Purpose |
|-----------|------------|-----------|---------|
| **Strategy Engine** | Market Data, Broker | Database, Order Manager | Generate trading signals |
| **Cost Calculator** | Signal Data | Risk Engine | Validate profitability |
| **Risk Engine** | Signals, News, Redis | Database, Redis | Multi-layer validation |
| **Order Manager** | Risk Engine, Broker | Database, Broker API | Execute trades |
| **News Ingestion** | NSE API | Database | Fetch announcements |
| **News Detector** | Database | Database | Score impact |
| **Capital Allocator** | Performance Tracker | Order Manager | Dynamic sizing |
| **Performance Tracker** | Database | Database, Capital Allocator | Calculate scores |
| **Dashboard** | Database, Redis | None | Visualize data |
| **Monitoring** | Database, Redis | Telegram | Health checks |

---

## 📊 Database Schema

```mermaid
erDiagram
    TRADES ||--o{ DAILY_METRICS : aggregates
    TRADES {
        int id PK
        string symbol
        string strategy_name
        string direction
        float entry_price
        float exit_price
        int quantity
        float stop_price
        float target_price
        float net_pnl
        string status
        datetime entry_timestamp
        datetime exit_timestamp
    }
    
    DAILY_METRICS {
        int id PK
        date trading_date
        int total_trades
        decimal total_pnl
        decimal realized_pnl
        decimal unrealized_pnl
        float win_rate
        int wins
        int losses
        decimal largest_win
        decimal largest_loss
    }
    
    NEWS_ITEMS {
        int id PK
        string news_id UK
        string source
        string exchange
        string symbol
        text headline
        text description
        string category
        int impact_score
        string direction
        string action
        string blocked_by
        datetime timestamp
        datetime detected_at
    }
    
    TRADES ||--o{ NEWS_ITEMS : considers
```

---

## 🚀 Deployment Architecture

```mermaid
flowchart TB
    subgraph "Production Environment"
        subgraph "Docker Containers"
            App[App Container<br/>Python Trading System]
            PG[(PostgreSQL<br/>Database)]
            Redis[(Redis<br/>Cache)]
            Dashboard[Dashboard Container<br/>Web UI]
        end
        
        subgraph "External Services"
            Broker[Broker API<br/>Groww/Zerodha]
            NSE[NSE API<br/>Market Data]
            Telegram[Telegram Bot API<br/>Alerts]
        end
    end
    
    subgraph "Local Development"
        Dev[Development<br/>VS Code]
        LocalDB[(SQLite<br/>Local DB)]
    end
    
    App --> PG
    App --> Redis
    App --> Broker
    App --> NSE
    App --> Telegram
    
    Dashboard --> PG
    Dashboard --> Redis
    
    Dev --> LocalDB
    Dev -.->|Deploy| App
    
    style App fill:#4ecdc4
    style Dashboard fill:#4ecdc4
    style PG fill:#95e1d3
    style Redis fill:#95e1d3
```

---

## 📝 Key Design Principles

1. **Fail-Safe Design**: Multiple validation layers prevent bad trades
2. **Cost-First Approach**: Transaction costs validated before risk checks
3. **Observable System**: Comprehensive logging and monitoring
4. **Modular Architecture**: Each component has single responsibility
5. **Data-Driven**: Performance metrics drive capital allocation
6. **Real-time State**: Redis for fast access, PostgreSQL for persistence
7. **Defensive Trading**: Quality over quantity with pre-entry checklist

---

**Built with ❤️ for algorithmic trading in Indian markets**
