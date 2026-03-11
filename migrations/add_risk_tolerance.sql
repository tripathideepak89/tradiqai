-- Migration: Add risk_tolerance column to users table
-- Run this in Supabase SQL Editor if you have an existing database

-- Add the risk_tolerance column
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS risk_tolerance INTEGER DEFAULT 50 
CHECK (risk_tolerance >= 0 AND risk_tolerance <= 100);

-- Add comment for documentation
COMMENT ON COLUMN public.users.risk_tolerance IS 'User risk tolerance level: 0=Ultra Safe, 50=Balanced, 100=Aggressive';

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ risk_tolerance column added to users table';
    RAISE NOTICE '   Default value: 50 (Balanced)';
    RAISE NOTICE '   Valid range: 0-100';
END $$;
