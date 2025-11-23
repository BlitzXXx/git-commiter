-- Migration: Add realized_pnl and position_id to trades table
-- This fixes the schema to support P&L tracking per trade

-- Add realized_pnl column (NULL for BUY trades, populated for SELL trades)
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS realized_pnl NUMERIC(12, 2);

-- Add position_id to link trades to positions
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS position_id INTEGER;

-- Add comment for clarity
COMMENT ON COLUMN trades.realized_pnl IS 'Profit/loss realized on SELL trades (NULL for BUY)';
COMMENT ON COLUMN trades.position_id IS 'Links BUY and SELL trades to the same position';

-- Create index for position lookups
CREATE INDEX IF NOT EXISTS idx_trades_position_id ON trades(position_id);

RAISE NOTICE '✅ Migration 001 applied: Added realized_pnl and position_id to trades table';
