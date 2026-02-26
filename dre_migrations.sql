-- ═══════════════════════════════════════════════════════════════
--  TradiqAI — Dividend Radar Engine (DRE)
--  SQL: Tables, Indexes, Views
--  Run once against your Supabase / PostgreSQL database
-- ═══════════════════════════════════════════════════════════════


-- ──────────────────────────────────────────
--  TABLE 1: Raw dividend announcements
--  (written by DividendIngestionService)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS corporate_actions_dividends (
    id                      SERIAL PRIMARY KEY,
    symbol                  VARCHAR(20),
    bse_code                VARCHAR(10),
    name                    TEXT NOT NULL,
    series                  VARCHAR(5),
    exchange                VARCHAR(5) DEFAULT 'NSE',
    purpose                 TEXT,
    dividend_type           VARCHAR(20),          -- Final | Interim | Special
    dividend_amount         NUMERIC(10,2),
    face_value              NUMERIC(10,2),
    ex_date                 DATE NOT NULL,
    record_date             DATE,
    bc_start_date           DATE,
    bc_end_date             DATE,
    nd_start_date           DATE,                  -- BSE no-delivery start
    nd_end_date             DATE,                  -- BSE no-delivery end
    payment_date            DATE,                  -- BSE actual payment date
    announcement_date       DATE,
    source                  VARCHAR(5),            -- NSE | BSE | MC
    ingested_at             TIMESTAMPTZ DEFAULT NOW(),

    -- Computed columns for deduplication
    -- Strips non-alphanumeric: "ITC LTD" → "ITCLTD"
    symbol_dedup_key        TEXT GENERATED ALWAYS AS (
        UPPER(REGEXP_REPLACE(COALESCE(symbol, name), '[^A-Z0-9]', '', 'g'))
    ) STORED,

    -- Round to 1dp to handle ₹6.50 vs ₹6.5 from different sources
    dividend_amount_rounded NUMERIC(8,1) GENERATED ALWAYS AS (
        ROUND(COALESCE(dividend_amount, 0), 1)
    ) STORED,

    UNIQUE (symbol_dedup_key, ex_date, dividend_amount_rounded)
);

CREATE INDEX IF NOT EXISTS idx_div_ex_date   ON corporate_actions_dividends(ex_date);
CREATE INDEX IF NOT EXISTS idx_div_symbol    ON corporate_actions_dividends(symbol);
CREATE INDEX IF NOT EXISTS idx_div_source    ON corporate_actions_dividends(source);
CREATE INDEX IF NOT EXISTS idx_div_exchange  ON corporate_actions_dividends(exchange);


-- ──────────────────────────────────────────
--  TABLE 2: DRE Scores
--  (written by DividendScoringEngine)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dividend_scores (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(20) NOT NULL,
    ex_date             DATE        NOT NULL,

    -- Core DRE score
    dre_score           INT,
    category            VARCHAR(20),              -- Strong Buy | Watchlist | Moderate | Ignore
    is_trap             BOOLEAN DEFAULT FALSE,
    entry_signal        BOOLEAN DEFAULT FALSE,

    -- Score components
    score_yield         INT,                      -- 0–25
    score_consistency   INT,                      -- 0–20
    score_growth        INT,                      -- 0–15
    score_financial     INT,                      -- 0–20
    score_technical     INT,                      -- 0–20

    -- Price data
    price               NUMERIC(10,2),
    yield_pct           NUMERIC(6,2),
    trend               VARCHAR(20),
    above_20dma         BOOLEAN,
    above_50dma         BOOLEAN,
    above_200dma        BOOLEAN,

    -- Fundamentals
    roe                 NUMERIC(6,2),
    de                  NUMERIC(6,2),

    -- Entry / exit info
    days_to_ex          INT,
    entry_zone_low      NUMERIC(10,2),
    entry_zone_high     NUMERIC(10,2),

    scored_at           TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (symbol, ex_date)
);

CREATE INDEX IF NOT EXISTS idx_scores_ex_date  ON dividend_scores(ex_date);
CREATE INDEX IF NOT EXISTS idx_scores_signal   ON dividend_scores(entry_signal) WHERE entry_signal = TRUE;
CREATE INDEX IF NOT EXISTS idx_scores_score    ON dividend_scores(dre_score DESC);


-- ──────────────────────────────────────────
--  TABLE 3: Backtest results
--  (written by DividendBacktester.export_to_db)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dividend_backtest_trades (
    id              SERIAL PRIMARY KEY,
    run_id          UUID DEFAULT gen_random_uuid(),
    strategy        VARCHAR(5),                    -- S1 | S2 | S3
    entry_n         INT,
    exit_offset     INT,
    symbol          VARCHAR(20),
    ex_date         DATE,
    entry_date      DATE,
    exit_date       DATE,
    entry_price     NUMERIC(10,2),
    exit_price      NUMERIC(10,2),
    dividend_amount NUMERIC(10,2),
    yield_pct       NUMERIC(6,2),
    gross_return    NUMERIC(8,3),
    net_return      NUMERIC(8,3),
    costs           NUMERIC(8,3),
    ran_at          TIMESTAMPTZ DEFAULT NOW()
);


-- ──────────────────────────────────────────
--  VIEW: Upcoming dividend radar
--  Powers the Radar dashboard
-- ──────────────────────────────────────────
CREATE OR REPLACE VIEW vw_dividend_radar AS
SELECT
    d.symbol,
    d.name,
    d.exchange,
    d.source,
    d.purpose,
    d.dividend_type,
    d.dividend_amount,
    d.face_value,
    d.ex_date,
    d.record_date,
    d.payment_date,
    (d.ex_date - CURRENT_DATE)           AS days_to_ex,

    -- Scores
    COALESCE(s.dre_score, 0)             AS dre_score,
    COALESCE(s.yield_pct, 0)             AS yield_pct,
    s.category,
    s.is_trap,
    s.entry_signal,
    s.trend,
    s.price,
    s.above_20dma,
    s.above_50dma,
    s.above_200dma,
    s.roe,
    s.de,
    s.score_yield,
    s.score_consistency,
    s.score_growth,
    s.score_financial,
    s.score_technical,
    s.entry_zone_low,
    s.entry_zone_high,
    s.scored_at

FROM   corporate_actions_dividends d
LEFT JOIN dividend_scores s
    ON s.symbol  = d.symbol
   AND s.ex_date = d.ex_date

WHERE  d.ex_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
ORDER  BY COALESCE(s.dre_score, 0) DESC, d.ex_date ASC;


-- ──────────────────────────────────────────
--  VIEW: Entry signals only
-- ──────────────────────────────────────────
CREATE OR REPLACE VIEW vw_dre_entry_signals AS
SELECT *
FROM   vw_dividend_radar
WHERE  entry_signal = TRUE
  AND  is_trap      = FALSE
ORDER  BY dre_score DESC;


-- ──────────────────────────────────────────
--  VIEW: Backtest summary by strategy+params
-- ──────────────────────────────────────────
CREATE OR REPLACE VIEW vw_backtest_summary AS
SELECT
    strategy,
    entry_n,
    exit_offset,
    COUNT(*)                                AS n_trades,
    ROUND(AVG(net_return)::NUMERIC, 3)      AS avg_net_return,
    ROUND(STDDEV(net_return)::NUMERIC, 3)   AS std_return,
    ROUND(
        100.0 * SUM(CASE WHEN net_return > 0 THEN 1 ELSE 0 END) / COUNT(*),
        1
    )                                       AS win_rate_pct,
    ROUND(
        ABS(
            SUM(CASE WHEN net_return > 0 THEN net_return ELSE 0 END) /
            NULLIF(ABS(SUM(CASE WHEN net_return < 0 THEN net_return ELSE 0 END)), 0)
        )::NUMERIC,
        2
    )                                       AS profit_factor,
    MIN(ran_at)                             AS first_run,
    MAX(ran_at)                             AS last_run
FROM   dividend_backtest_trades
GROUP  BY strategy, entry_n, exit_offset
ORDER  BY profit_factor DESC NULLS LAST;


-- ──────────────────────────────────────────
--  USEFUL QUERIES
-- ──────────────────────────────────────────

-- Get all upcoming dividends with scores
-- SELECT * FROM vw_dividend_radar;

-- Get active entry signals
-- SELECT * FROM vw_dre_entry_signals;

-- Get dividend traps to avoid
-- SELECT symbol, name, yield_pct, trend, ex_date
-- FROM   vw_dividend_radar
-- WHERE  is_trap = TRUE;

-- Get backtest performance by strategy
-- SELECT * FROM vw_backtest_summary;

-- Count records by source
-- SELECT source, COUNT(*) FROM corporate_actions_dividends GROUP BY source;

-- Historical dividend events for a symbol
-- SELECT * FROM corporate_actions_dividends
-- WHERE symbol = 'ITC'
-- ORDER BY ex_date DESC;
