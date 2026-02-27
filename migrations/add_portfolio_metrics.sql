-- ============================================================
-- Migration: Add portfolio_metrics table
-- Part of: Capital Management Engine (CME) feature
-- Applies to: PostgreSQL (production) and SQLite (local dev)
-- ============================================================

-- Create portfolio_metrics table if it does not already exist.
-- Stores CME snapshots written after every trade gate check.

CREATE TABLE IF NOT EXISTS portfolio_metrics (
    id               SERIAL PRIMARY KEY,          -- PostgreSQL; SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    total_capital    DOUBLE PRECISION NOT NULL,
    cash_available   DOUBLE PRECISION NOT NULL,
    total_exposure   DOUBLE PRECISION DEFAULT 0,
    peak_equity      DOUBLE PRECISION NOT NULL,
    current_equity   DOUBLE PRECISION NOT NULL,
    drawdown_pct     DOUBLE PRECISION DEFAULT 0,
    risk_mode        VARCHAR(20)       DEFAULT 'NORMAL',
    strategy_exposure TEXT,                       -- JSON: {"SWING":25000,"INTRADAY":0,...}
    sector_exposure   TEXT,                       -- JSON: {"Banking":30000,"IT":5000,...}
    updated_at       TIMESTAMPTZ       DEFAULT NOW()
);

-- Index for fast time-series queries
CREATE INDEX IF NOT EXISTS idx_portfolio_metrics_updated_at
    ON portfolio_metrics (updated_at DESC);

-- ============================================================
-- CME config additions to environment / .env
-- ============================================================
-- Add the following line to your .env file (or environment):
--
--   CME_TOTAL_CAPITAL=100000
--
-- This sets the portfolio capital for the Capital Management Engine.
-- Default is ₹1,00,000 if not set.
-- ============================================================

-- SQLite note:
-- If running locally with SQLite, replace SERIAL with INTEGER and
-- TIMESTAMPTZ with DATETIME.  SQLAlchemy's init_db() will auto-create
-- the table via models.py so you normally don't need to run this SQL
-- directly against SQLite.
