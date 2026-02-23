# Trade Lifecycle & State Management

**TradiqAI - Complete Trade Flow Documentation**

## 📋 Trade State Machine

```mermaid
stateDiagram-v2
    [*] --> SignalGenerated: Strategy detects opportunity
    
    SignalGenerated --> PreEntryCheck: Quality validation
    
    PreEntryCheck --> PreEntryRejected: Failed checklist
    PreEntryCheck --> CostValidation: Passed checklist
    
    PreEntryRejected --> [*]: Trade blocked
    
    CostValidation --> CostRejected: Failed cost filter
    CostValidation --> RiskValidation: Passed cost filter
    
    CostRejected --> [*]: Trade blocked
    
    RiskValidation --> RiskRejected: Failed risk check
    RiskValidation --> PendingOrder: Passed risk check
    
    RiskRejected --> [*]: Trade blocked
    
    PendingOrder --> OrderPlaced: Submitted to broker
    
    OrderPlaced --> OrderRejected: Broker rejected
    OrderPlaced --> Open: Broker accepted
    
    OrderRejected --> [*]: Trade failed
    
    Open --> Monitoring: Position opened
    
    Monitoring --> ExitSignal: Target/Stop hit
    Monitoring --> ManualExit: User intervention
    Monitoring --> TimeBasedExit: End of day
    
    ExitSignal --> PendingExit: Exit order placed
    ManualExit --> PendingExit: Exit order placed
    TimeBasedExit --> PendingExit: Exit order placed
    
    PendingExit --> Closed: Exit executed
    
    Closed --> CalculatingPnL: Processing results
    
    CalculatingPnL --> Completed: P&L recorded
    
    Completed --> [*]: Trade finished
    
    note right of PreEntryCheck
        7-Point Quality Filter:
        - NIFTY regime
        - Breakout type
        - Volume confirmation
        - Extension level
        - Risk/Reward ratio
        - Resistance proximity
        - Day type
    end note
    
    note right of CostValidation
        Cost Filter Checks:
        - Expected move ≥ 2x cost
        - Cost ratio ≤ 25%
        - Net profit > 0
    end note
    
    note right of RiskValidation
        Risk Checks:
        - Daily loss < ₹1,500
        - Open positions < 2
        - Consecutive losses < 3
        - Per-trade risk ≤ ₹400
        - Total exposure < 80%
        - Kill switch OFF
        - News governance clear
    end note
```

---

## 🔄 Complete Trade Execution Timeline

```mermaid
gantt
    title Trade Execution Timeline (Typical Intraday Trade)
    dateFormat HH:mm:ss
    section Market Open
    Market opens           :milestone, 09:15:00, 0m
    
    section Signal Generation
    Fetch market data      :active, t1, 09:45:00, 5s
    Technical analysis     :active, t2, after t1, 10s
    Signal generated       :crit, t3, after t2, 1s
    
    section Validation Layer
    Pre-entry checklist    :active, v1, after t3, 3s
    Cost calculation       :active, v2, after v1, 2s
    Risk engine checks     :active, v3, after v2, 5s
    
    section Order Execution
    Calculate position size:active, e1, after v3, 2s
    Place order with broker:crit, e2, after e1, 500ms
    Broker processing      :e3, after e2, 2s
    Order confirmation     :milestone, after e3, 0m
    
    section Position Monitoring
    Monitor price          :mon1, after e3, 2h
    Check exit conditions  :mon2, after e3, 2h
    
    section Exit Execution
    Exit signal triggered  :crit, exit1, 12:00:00, 1s
    Place exit order       :exit2, after exit1, 500ms
    Exit confirmation      :milestone, after exit2, 2s
    
    section Post-Trade
    Calculate P&L          :post1, after exit2, 5s
    Update performance     :post2, after post1, 3s
    Save to database       :post3, after post2, 2s
    Send Telegram alert    :post4, after post3, 1s
```

---

## 🏭 System Startup Sequence

```mermaid
sequenceDiagram
    participant User
    participant Main
    participant DB as Database
    participant Broker
    participant Risk as Risk Engine
    participant Order as Order Manager
    participant Strategy
    participant News as News System
    participant Monitor as Monitoring
    participant Dash as Dashboard
    
    User->>Main: python main.py
    
    activate Main
    Main->>DB: Initialize database
    DB-->>Main: ✅ Connected
    
    Main->>Broker: Connect to broker
    Broker-->>Main: ✅ Authenticated
    
    Main->>Risk: Initialize risk engine
    Risk->>Broker: Fetch account balance
    Broker-->>Risk: Current capital
    Risk->>Risk: Set daily limits
    Risk-->>Main: ✅ Ready (Capital: ₹50,000)
    
    Main->>Order: Initialize order manager
    Order->>DB: Sync broker positions
    DB-->>Order: Position data
    Order-->>Main: ✅ Ready
    
    Main->>Strategy: Load strategies
    Strategy-->>Main: ✅ LiveSimple loaded
    
    Main->>News: Start news ingestion
    News->>News: Initialize NSE poller
    News-->>Main: ✅ Polling started
    
    Main->>Monitor: Start monitoring service
    Monitor->>Monitor: Check market hours
    Monitor-->>Main: ✅ Monitoring active
    
    Main->>Dash: Start dashboard (optional)
    Dash->>DB: Connect to database
    DB-->>Dash: ✅ Connected
    Dash-->>Main: ✅ Dashboard on :8000
    
    Main->>Monitor: Send startup alert
    Monitor->>User: 📱 System started
    
    Main->>Main: Start trading loop
    deactivate Main
    
    Note over Main, User: System now running and monitoring market
```

---

## 🔍 Position Monitoring Loop

```mermaid
flowchart TD
    Start([Trading Loop Running]) --> MarketCheck{Market<br/>Open?}
    
    MarketCheck -->|No| Sleep1[Sleep 60s]
    MarketCheck -->|Yes| KillSwitch{Kill Switch<br/>Active?}
    
    KillSwitch -->|Yes| Sleep2[Sleep 60s<br/>System paused]
    KillSwitch -->|No| CheckPositions[Get Open Positions<br/>from Database]
    
    CheckPositions --> HasPositions{Any Open<br/>Positions?}
    
    HasPositions -->|No| ScanSignals[Scan for New Signals]
    HasPositions -->|Yes| LoopPositions[For Each Position]
    
    LoopPositions --> GetPrice[Get Current Price<br/>from Broker]
    
    GetPrice --> CheckTarget{Price ≥<br/>Target?}
    
    CheckTarget -->|Yes| ExitTarget[Exit at Target<br/>✅ Profit]
    CheckTarget -->|No| CheckStop{Price ≤<br/>Stop Loss?}
    
    CheckStop -->|Yes| ExitStop[Exit at Stop<br/>❌ Loss]
    CheckStop -->|No| CheckTrailing{Trailing Stop<br/>Hit?}
    
    CheckTrailing -->|Yes| ExitTrailing[Exit Trailing<br/>✅ Profit]
    CheckTrailing -->|No| CheckTime{End of Day?<br/>3:15 PM}
    
    CheckTime -->|Yes| ExitEOD[Exit EOD<br/>Close position]
    CheckTime -->|No| NextPosition{More<br/>Positions?}
    
    NextPosition -->|Yes| LoopPositions
    NextPosition -->|No| ScanSignals
    
    ExitTarget --> UpdateDB1[Update Trade in DB]
    ExitStop --> UpdateDB1
    ExitTrailing --> UpdateDB1
    ExitEOD --> UpdateDB1
    
    UpdateDB1 --> SendAlert1[Send Telegram Alert]
    SendAlert1 --> UpdateMetrics[Update Performance<br/>Metrics]
    UpdateMetrics --> NextPosition
    
    ScanSignals --> NewSignal{Signal<br/>Found?}
    
    NewSignal -->|Yes| ValidateSignal[Run Validation Pipeline:<br/>PreCheck → Cost → Risk]
    NewSignal -->|No| Sleep3[Sleep 60s]
    
    ValidateSignal --> Approved{All Checks<br/>Passed?}
    
    Approved -->|Yes| ExecuteTrade[Execute Trade]
    Approved -->|No| LogRejection[Log Rejection Reason]
    
    ExecuteTrade --> SaveTrade[Save Trade to DB]
    SaveTrade --> SendAlert2[Send Entry Alert]
    SendAlert2 --> Sleep4[Sleep 60s]
    
    LogRejection --> Sleep4
    
    Sleep1 --> Start
    Sleep2 --> Start
    Sleep3 --> Start
    Sleep4 --> Start
    
    style ExitTarget fill:#90EE90
    style ExitTrailing fill:#90EE90
    style ExitStop fill:#FFB6C1
    style ExitEOD fill:#FFE4B5
```

---

## 📊 Daily Performance Calculation Flow

```mermaid
flowchart TD
    EOD[End of Trading Day<br/>3:30 PM] --> Collect[Collect All Trades<br/>for Today]
    
    Collect --> Classify{Classify Trades}
    
    Classify --> Completed[Completed Trades<br/>Entry + Exit today]
    Classify --> Carried[Carried Positions<br/>Open overnight]
    
    Completed --> CalcRealized[Calculate Realized P&L]
    
    CalcRealized --> SumPnL[Sum all net_pnl:<br/>Gross P&L - Costs]
    
    SumPnL --> CountTrades[Count:<br/>Wins vs Losses]
    
    CountTrades --> CalcMetrics[Calculate Metrics]
    
    CalcMetrics --> WinRate[Win Rate = Wins / Total]
    CalcMetrics --> AvgWin[Avg Win]
    CalcMetrics --> AvgLoss[Avg Loss]
    CalcMetrics --> ProfitFactor[Profit Factor =<br/>Gross Profit / Gross Loss]
    CalcMetrics --> LargestWin[Largest Win]
    CalcMetrics --> LargestLoss[Largest Loss]
    
    WinRate --> CreateMetrics[Create DailyMetrics Record]
    AvgWin --> CreateMetrics
    AvgLoss --> CreateMetrics
    ProfitFactor --> CreateMetrics
    LargestWin --> CreateMetrics
    LargestLoss --> CreateMetrics
    
    Carried --> CalcUnrealized[Calculate Unrealized P&L]
    
    CalcUnrealized --> OpenPositions[For each open position:<br/>Current Price - Entry Price]
    
    OpenPositions --> CreateMetrics
    
    CreateMetrics --> SaveDB[(Save to Database)]
    
    SaveDB --> CheckLoss{Daily<br/>Loss > ₹1,500?}
    
    CheckLoss -->|Yes| ActivateKill[🚨 ACTIVATE KILL SWITCH<br/>Halt trading tomorrow]
    CheckLoss -->|No| CheckConsec{3 Consecutive<br/>Losses?}
    
    ActivateKill --> SendCritical[Send Critical Alert]
    
    CheckConsec -->|Yes| SendWarning[Send Warning Alert]
    CheckConsec -->|No| SendSummary[Send Daily Summary]
    
    SendCritical --> TelegramAlert[📱 Telegram Alert]
    SendWarning --> TelegramAlert
    SendSummary --> TelegramAlert
    
    TelegramAlert --> UpdateScores[Update Strategy<br/>Performance Scores]
    
    UpdateScores --> CheckMonth{End of<br/>Month?}
    
    CheckMonth -->|Yes| Rebalance[Run Monthly Rebalancing<br/>Adjust capital allocations]
    CheckMonth -->|No| Done[✅ Daily Close Complete]
    
    Rebalance --> Done
    
    style ActivateKill fill:#FF6B6B
    style SendWarning fill:#FFE4B5
    style SendSummary fill:#90EE90
```

---

## 🔐 Authentication & Session Management

```mermaid
sequenceDiagram
    participant System
    participant BrokerAPI
    participant TokenStore
    
    Note over System: System Startup
    
    System->>TokenStore: Load saved credentials
    
    alt Using Groww
        TokenStore-->>System: JWT Token + API Secret
        System->>BrokerAPI: Authenticate with JWT
        BrokerAPI-->>System: ✅ Session active
        
    else Using Zerodha
        TokenStore-->>System: API Key + Secret
        System->>BrokerAPI: Generate login URL
        BrokerAPI-->>System: Login URL
        
        Note over System, BrokerAPI: User manually logs in via browser
        
        System->>BrokerAPI: Request access token
        BrokerAPI-->>System: Access token (valid 1 day)
        System->>TokenStore: Save access token
    end
    
    loop Every API Call
        System->>BrokerAPI: API Request + Token
        
        alt Token Valid
            BrokerAPI-->>System: ✅ Response data
        else Token Expired
            BrokerAPI-->>System: ❌ 401 Unauthorized
            System->>System: Log error
            System->>System: Send alert to user
            Note over System: System halts trading
        end
    end
```

---

## 📡 Real-time Data Flow

```mermaid
flowchart LR
    subgraph "Market Data Sources"
        NSE[NSE Feed]
        BSE[BSE Feed]
        Broker[Broker Quotes]
    end
    
    subgraph "Data Collection Layer"
        Cache[Quote Cache<br/>30s TTL]
        News[News Buffer<br/>Deduplicated]
    end
    
    subgraph "Processing Engines"
        Strategy[Strategy Engine<br/>Technical Analysis]
        NewsProc[News Processor<br/>Impact Detection]
    end
    
    subgraph "Decision Layer"
        Cost[Cost Filter]
        Risk[Risk Engine]
    end
    
    subgraph "Execution Layer"
        Order[Order Manager]
    end
    
    subgraph "Feedback Loop"
        Perf[Performance Tracker]
        Alloc[Capital Allocator]
    end
    
    NSE --> Cache
    BSE --> Cache
    Broker --> Cache
    
    NSE --> News
    
    Cache --> Strategy
    News --> NewsProc
    
    Strategy --> Cost
    NewsProc --> Risk
    
    Cost --> Risk
    Risk --> Order
    
    Order --> Perf
    Perf --> Alloc
    
    Alloc -.->|Adjust Size| Order
    
    Order -.->|Market Impact| NSE
    Order -.->|Market Impact| BSE
    
    style Cache fill:#95e1d3
    style News fill:#95e1d3
    style Cost fill:#ff6b6b
    style Risk fill:#ff6b6b
```

---

## 🎯 Signal Generation Process

```mermaid
flowchart TD
    Market[Market Quote Received] --> Parse[Parse Quote Data:<br/>LTP, OHLC, Volume]
    
    Parse --> Cache[Update Quote Cache]
    
    Cache --> TechAnalysis[Technical Analysis]
    
    TechAnalysis --> Indicators{Calculate Indicators}
    
    Indicators --> EMA[EMA 20, 50]
    Indicators --> RSI[RSI 14]
    Indicators --> VWAP[VWAP]
    Indicators --> ATR[ATR for stops]
    
    EMA --> Pattern[Pattern Recognition]
    RSI --> Pattern
    VWAP --> Pattern
    
    Pattern --> Setup{Valid Setup<br/>Detected?}
    
    Setup -->|No| End1[Continue Monitoring]
    Setup -->|Yes| Direction{Direction?}
    
    Direction -->|Long| LongSetup[Long Entry Criteria:<br/>Price > EMA20 > EMA50<br/>RSI 40-70<br/>Volume > 1.5x avg]
    Direction -->|Short| ShortSetup[Short Entry Criteria:<br/>Price < EMA20 < EMA50<br/>RSI 30-60<br/>Volume > 1.5x avg]
    
    LongSetup --> CalculateLevels[Calculate Levels]
    ShortSetup --> CalculateLevels
    
    CalculateLevels --> Entry[Entry Price = Current LTP]
    CalculateLevels --> Stop[Stop Loss = Entry - (2 * ATR)]
    CalculateLevels --> Target[Target = Entry + (1.5 * |Entry - Stop|)]
    
    Entry --> CreateSignal[Create Signal Object]
    Stop --> CreateSignal
    Target --> CreateSignal
    
    CreateSignal --> Signal[Signal:<br/>Symbol, Action, Entry,<br/>Stop, Target, Quantity]
    
    Signal --> Pipeline[Submit to<br/>Validation Pipeline]
    
    style Signal fill:#4ecdc4
    style Pipeline fill:#feca57
```

---

## 🧮 Position Sizing Algorithm

```mermaid
flowchart TD
    Signal[Signal with<br/>Entry & Stop] --> CalcRisk[Calculate Risk per Share]
    
    CalcRisk --> RiskPer[Risk per Share =<br/>|Entry - Stop|]
    
    RiskPer --> GetBudget{Get Risk Budget}
    
    GetBudget --> Strategy[From Strategy Layer:<br/>Intraday/Swing/Mid/Long]
    
    Strategy --> GetScore[Get Performance Score<br/>for this layer]
    
    GetScore --> BaseAlloc[Base Allocation:<br/>Intraday 15%, Swing 35%<br/>Mid 35%, Long 15%]
    
    BaseAlloc --> Adjust{Score-based<br/>Adjustment}
    
    Adjust -->|Score ≥ 70| Increase[+5% allocation]
    Adjust -->|Score < 40| Decrease[-5% allocation]
    Adjust -->|Score 40-69| Maintain[No adjustment]
    
    Increase --> Available[Calculate Available Capital]
    Decrease --> Available
    Maintain --> Available
    
    Available --> Multiply[Layer Capital =<br/>Total Capital × Allocation %]
    
    Multiply --> MaxRisk[Max Risk for Trade =<br/>Min(₹400, Layer Capital × 2%)]
    
    MaxRisk --> CalcQty[Calculate Quantity:<br/>Quantity = Max Risk / Risk per Share]
    
    CalcQty --> Round[Round down to<br/>nearest integer]
    
    Round --> CheckMin{Quantity<br/>≥ 1?}
    
    CheckMin -->|No| Reject[❌ REJECT<br/>Risk too high for 1 share]
    CheckMin -->|Yes| CheckMax{Capital Required<br/>≤ ₹12,500?}
    
    CheckMax -->|No| Reduce[Reduce Quantity<br/>to fit ₹12,500 limit]
    CheckMax -->|Yes| CheckExposure{Total Exposure<br/>< 80%?}
    
    Reduce --> CheckExposure
    
    CheckExposure -->|No| Reject2[❌ REJECT<br/>Exposure limit exceeded]
    CheckExposure -->|Yes| Final[✅ Final Quantity<br/>Position Size Approved]
    
    style Final fill:#90EE90
    style Reject fill:#FFB6C1
    style Reject2 fill:#FFB6C1
```

---

## 🔄 Error Recovery Flows

```mermaid
flowchart TD
    Error[Error Detected] --> Type{Error Type}
    
    Type -->|Network| NetworkError[Network Error:<br/>Broker API unreachable]
    Type -->|Auth| AuthError[Authentication Error:<br/>Invalid token/credentials]
    Type -->|Data| DataError[Data Error:<br/>Invalid response format]
    Type -->|Database| DBError[Database Error:<br/>Connection/Query failed]
    Type -->|Business| BusinessError[Business Logic Error:<br/>Validation failed]
    
    NetworkError --> Retry1{Retry Count<br/>< 3?}
    
    Retry1 -->|Yes| BackoffWait[Exponential Backoff:<br/>5s, 15s, 30s]
    Retry1 -->|No| Alert1[🚨 Alert: Network Issue<br/>Manual intervention needed]
    
    BackoffWait --> RetryRequest[Retry API Request]
    
    RetryRequest --> Success1{Success?}
    
    Success1 -->|Yes| Resume[Resume Normal Operation]
    Success1 -->|No| Retry1
    
    AuthError --> Alert2[🚨 Critical Alert:<br/>Authentication Failed]
    Alert2 --> Halt1[Halt Trading<br/>Activate Kill Switch]
    
    DataError --> Log1[Log Error Details]
    Log1 --> Skip[Skip This Data Point<br/>Continue with next]
    
    DBError --> Retry2{Retry Count<br/>< 3?}
    
    Retry2 -->|Yes| ReconnectDB[Reconnect to Database]
    Retry2 -->|No| Alert3[🚨 Alert: DB Issue<br/>System unstable]
    
    ReconnectDB --> Success2{Success?}
    
    Success2 -->|Yes| Resume
    Success2 -->|No| Retry2
    
    Alert3 --> Halt2[Halt Trading<br/>Preserve state in Redis]
    
    BusinessError --> Log2[Log Rejection Reason]
    Log2 --> Continue[Continue Monitoring<br/>Trade rejected safely]
    
    Alert1 --> TelegramUsers[Send Telegram Alert]
    Alert2 --> TelegramUsers
    Alert3 --> TelegramUsers
    
    Halt1 --> Cleanup[Cleanup Resources]
    Halt2 --> Cleanup
    
    style Alert1 fill:#FFB6C1
    style Alert2 fill:#FF6B6B
    style Alert3 fill:#FFB6C1
    style Resume fill:#90EE90
```

---

## 📅 Monthly Rebalancing Workflow

```mermaid
flowchart TD
    StartMonth[First Day of New Month] --> Trigger[Trigger Rebalancing]
    
    Trigger --> FetchData[Fetch Last Month's Data:<br/>All trades by strategy layer]
    
    FetchData --> Group[Group by Layer:<br/>Intraday, Swing, Mid, Long]
    
    Group --> LoopLayers[For Each Layer]
    
    LoopLayers --> CalcMetrics[Calculate Metrics:<br/>Returns, PF, DD, WR, Trend]
    
    CalcMetrics --> CalcScore[Calculate Performance Score<br/>0-100 scale]
    
    CalcScore --> GradeLayer{Score Grade}
    
    GradeLayer -->|90-100| Excellent[🏆 EXCELLENT<br/>Increase +5%]
    GradeLayer -->|70-89| Good[✅ GOOD<br/>Maintain allocation]
    GradeLayer -->|50-69| Fair[⚠️ FAIR<br/>Monitor closely]
    GradeLayer -->|40-49| Poor[❌ POOR<br/>Decrease -5%]
    GradeLayer -->|0-39| Critical[🚨 CRITICAL<br/>Kill layer]
    
    Excellent --> Adjust1[New Allocation = Base + 5%]
    Good --> Adjust2[New Allocation = Base]
    Fair --> Adjust3[New Allocation = Base]
    Poor --> Adjust4[New Allocation = Base - 5%]
    Critical --> Disable[Disable Layer<br/>Allocation = 0%]
    
    Adjust1 --> Bounds1{Within<br/>10-40%?}
    Adjust2 --> Bounds1
    Adjust3 --> Bounds1
    Adjust4 --> Bounds1
    
    Bounds1 -->|No| Clamp[Clamp to bounds:<br/>Min 10%, Max 40%]
    Bounds1 -->|Yes| NextLayer{More<br/>Layers?}
    
    Clamp --> NextLayer
    Disable --> NextLayer
    
    NextLayer -->|Yes| LoopLayers
    NextLayer -->|No| Normalize[Normalize Allocations<br/>to sum to 100%]
    
    Normalize --> Validate[Validate:<br/>All layers 10-40%<br/>Total = 100%]
    
    Validate --> SaveAlloc[Save New Allocations<br/>to Database]
    
    SaveAlloc --> Report[Generate Rebalancing Report]
    
    Report --> Summary[Summary:<br/>- Old vs New allocations<br/>- Performance scores<br/>- Disabled layers<br/>- Expected impact]
    
    Summary --> SendReport[📱 Send Report via Telegram]
    
    SendReport --> Apply[Apply New Allocations<br/>for This Month]
    
    Apply --> Done[✅ Rebalancing Complete]
    
    style Excellent fill:#90EE90
    style Good fill:#B0E57C
    style Fair fill:#FFE4B5
    style Poor fill:#FFB6C1
    style Critical fill:#FF6B6B
    style Done fill:#4ecdc4
```

---

**Built with ❤️ for algorithmic trading in Indian markets**
