-- Migration: Add rejected_trades table to Supabase
-- Run this in Supabase SQL Editor if you already have the database set up
-- https://supabase.com/dashboard/project/YOUR_PROJECT/sql/editor

-- Create rejected_trades table for audit
CREATE TABLE IF NOT EXISTS public.rejected_trades (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(20) NOT NULL DEFAULT 'NSE',
    strategy_name VARCHAR(100) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL DEFAULT 'CNC',
    entry_price DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    target DOUBLE PRECISION,
    quantity_requested INTEGER NOT NULL DEFAULT 0,
    exposure_requested DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    reasons TEXT NOT NULL DEFAULT '[]',
    risk_snapshot TEXT,
    first_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latest_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    count INTEGER NOT NULL DEFAULT 1
);

-- Indexes for rejected_trades
CREATE INDEX IF NOT EXISTS idx_rejected_trades_user_id ON rejected_trades(user_id);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_symbol ON rejected_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_strategy ON rejected_trades(strategy_name);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_first_at ON rejected_trades(first_at);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_latest_at ON rejected_trades(latest_at);
CREATE INDEX IF NOT EXISTS idx_rejected_trades_dedup ON rejected_trades(user_id, symbol, strategy_name, side, latest_at);

-- Enable Row Level Security
ALTER TABLE rejected_trades ENABLE ROW LEVEL SECURITY;

-- RLS Policies - Users can view their own rejected trades + system-level rejections
CREATE POLICY "Users can view own rejected trades"
  ON rejected_trades FOR SELECT
  USING (user_id = auth.uid()::text OR user_id = 'system');

CREATE POLICY "Users can insert own rejected trades"
  ON rejected_trades FOR INSERT
  WITH CHECK (user_id = auth.uid()::text OR user_id = 'system');

-- Grant permissions
GRANT ALL ON rejected_trades TO authenticated;
GRANT SELECT ON rejected_trades TO anon;
GRANT USAGE, SELECT ON SEQUENCE rejected_trades_id_seq TO authenticated;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ rejected_trades table created successfully!';
    RAISE NOTICE '✅ RLS policies configured';
    RAISE NOTICE '';
    RAISE NOTICE 'You can now view rejected trades in the dashboard at /rejected-trades';
END $$;
