-- Migration: add_rejected_trades
-- Adds the rejected_trades audit table for tracking signals blocked by the
-- approval pipeline (cost filter, CME, risk engine, time filter, etc.).
--
-- Retention:  configurable (default 30 days), cleaned up by daily job.
-- Dedup:      same (user_id, symbol, strategy_name, side) within 10 min
--             updates count + latest_at instead of inserting a new row.

CREATE TABLE IF NOT EXISTS rejected_trades (
    id                  SERIAL PRIMARY KEY,
    user_id             VARCHAR(100)    NOT NULL,
    symbol              VARCHAR(50)     NOT NULL,
    exchange            VARCHAR(20)     NOT NULL DEFAULT 'NSE',
    strategy_name       VARCHAR(100)    NOT NULL,
    side                VARCHAR(10)     NOT NULL,      -- BUY / SELL
    order_type          VARCHAR(20)     NOT NULL DEFAULT 'CNC',

    -- Intended trade details (may be NULL if not yet computed)
    entry_price         DOUBLE PRECISION,
    stop_loss           DOUBLE PRECISION,
    target              DOUBLE PRECISION,
    quantity_requested  INTEGER         NOT NULL DEFAULT 0,
    exposure_requested  DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- Rejection detail (JSON)
    reasons             TEXT            NOT NULL DEFAULT '[]',
    risk_snapshot       TEXT,

    -- Timestamps + dedup counter
    first_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    latest_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    count               INTEGER         NOT NULL DEFAULT 1
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_rejected_trades_user_id     ON rejected_trades (user_id);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_symbol      ON rejected_trades (symbol);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_strategy    ON rejected_trades (strategy_name);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_first_at    ON rejected_trades (first_at);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_latest_at   ON rejected_trades (latest_at);

-- Composite index used by the dedup look-up
CREATE INDEX IF NOT EXISTS idx_rejected_trades_dedup
    ON rejected_trades (user_id, symbol, strategy_name, side, latest_at);
