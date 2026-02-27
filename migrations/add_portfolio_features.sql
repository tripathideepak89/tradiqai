-- ============================================================
-- Migration: Add portfolio analytics tables
-- Part of: Five Portfolio Analytics Features
-- Applies to: PostgreSQL (production) and SQLite (local dev)
-- ============================================================

-- ── Table: rebalance_runs ─────────────────────────────────────────────────
-- Stores each monthly rebalancer execution (recommendations only, no auto-trades).

CREATE TABLE IF NOT EXISTS rebalance_runs (
    id                      SERIAL PRIMARY KEY,
    run_date                TIMESTAMPTZ     DEFAULT NOW(),
    lookback_days           INTEGER         DEFAULT 30,
    bucket_scores           TEXT,           -- JSON: {bucket: {score, trade_count}}
    current_allocations     TEXT,           -- JSON: {bucket: pct}
    recommended_allocations TEXT,           -- JSON: {bucket: pct}
    changes                 TEXT,           -- JSON: [{bucket, old_pct, new_pct, delta_pct, reason}]
    notes                   TEXT,
    created_at              TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rebalance_runs_run_date
    ON rebalance_runs (run_date DESC);


-- ── Table: allocation_targets ──────────────────────────────────────────────
-- Stores AAE weekly allocation targets.  Latest row = currently active targets.

CREATE TABLE IF NOT EXISTS allocation_targets (
    id                  SERIAL PRIMARY KEY,
    computed_at         TIMESTAMPTZ     DEFAULT NOW(),
    regime              VARCHAR(20)     DEFAULT 'NEUTRAL',
    lookback_days       INTEGER         DEFAULT 30,
    targets             TEXT            NOT NULL,   -- JSON: {bucket: target_pct}
    deltas              TEXT,                       -- JSON: {bucket: delta_pct}
    total_allocated_pct DOUBLE PRECISION DEFAULT 100.0,
    created_at          TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_allocation_targets_computed_at
    ON allocation_targets (computed_at DESC);


-- ============================================================
-- SQLite note:
--   Replace SERIAL → INTEGER, TIMESTAMPTZ → DATETIME.
--   SQLAlchemy's init_db() will auto-create these tables via
--   models.py, so you normally don't need to run this SQL
--   against SQLite directly.
-- ============================================================
