-- Idim Ikang v1.9.6 Truth Ladder Migration
-- Adds fields to distinguish between simulated and exchange-verified outcomes

-- 1. Execution Tracking
ALTER TABLE signals ADD COLUMN IF NOT EXISTS execution_id TEXT; -- Exchange Order ID
ALTER TABLE signals ADD COLUMN IF NOT EXISTS execution_source TEXT DEFAULT 'simulated' CHECK (execution_source IN ('simulated', 'live'));
ALTER TABLE signals ADD COLUMN IF NOT EXISTS fill_price NUMERIC;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS exchange_status TEXT; -- 'open', 'closed', 'canceled', 'expired'

-- 2. Audit Trail
ALTER TABLE signals ADD COLUMN IF NOT EXISTS execution_logs JSONB DEFAULT '[]'::jsonb;

-- 3. Update outcome check for more granular states
ALTER TABLE signals DROP CONSTRAINT IF EXISTS signals_outcome_check;
ALTER TABLE signals ADD CONSTRAINT signals_outcome_check CHECK (outcome IN ('WIN', 'LOSS', 'EXPIRED', 'PARTIAL_WIN', 'ARCHIVED_V1', 'LIVE_WIN', 'LIVE_LOSS', 'LIVE_PARTIAL'));
