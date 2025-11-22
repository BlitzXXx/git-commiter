-- SentimentEdge Database Initialization Script
-- This script runs when the PostgreSQL container starts for the first time

-- ============================================
-- Enable TimescaleDB Extension
-- ============================================
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================
-- Core Tables (PostgreSQL)
-- ============================================

-- Tickers: Stock symbols and company metadata
CREATE TABLE IF NOT EXISTS tickers (
    symbol TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    sector TEXT,
    aliases TEXT[],  -- Alternative names for ticker extraction
    is_active BOOLEAN DEFAULT TRUE,
    last_traded TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for company name lookups
CREATE INDEX IF NOT EXISTS idx_tickers_company_name ON tickers(company_name);

-- Trades: Executed trade history
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker TEXT NOT NULL REFERENCES tickers(symbol),
    action TEXT NOT NULL CHECK (action IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price NUMERIC(10, 2) NOT NULL CHECK (price > 0),
    total_value NUMERIC(12, 2) NOT NULL,
    commission NUMERIC(8, 2) DEFAULT 0,
    signal_reason TEXT,
    sentiment_score DOUBLE PRECISION,
    order_id TEXT UNIQUE,  -- Alpaca order ID
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for trades
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_ticker_timestamp ON trades(ticker, timestamp DESC);

-- Positions: Current open positions
CREATE TABLE IF NOT EXISTS positions (
    ticker TEXT PRIMARY KEY REFERENCES tickers(symbol),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    avg_entry_price NUMERIC(10, 2) NOT NULL CHECK (avg_entry_price > 0),
    current_price NUMERIC(10, 2),
    unrealized_pnl NUMERIC(12, 2),
    realized_pnl NUMERIC(12, 2) DEFAULT 0,
    entry_timestamp TIMESTAMPTZ NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Strategy Configuration
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default configuration
INSERT INTO config (key, value, description) VALUES
('sentiment_threshold', '0.7', 'Minimum sentiment score for BUY signal (0-1)'),
('min_mentions', '15', 'Minimum number of posts required in time window'),
('volume_multiplier', '1.5', 'Market volume vs average for confirmation'),
('take_profit_pct', '0.03', 'Take profit target (3%)'),
('stop_loss_pct', '0.02', 'Stop loss limit (2%)'),
('max_hold_seconds', '3600', 'Maximum holding time in seconds (1 hour)'),
('max_positions', '5', 'Maximum number of concurrent positions'),
('position_size_pct', '0.10', 'Percent of capital per position (10%)'),
('max_daily_loss_pct', '0.05', 'Daily loss limit kill switch (5%)'),
('max_sector_exposure_pct', '0.30', 'Maximum exposure to single sector (30%)')
ON CONFLICT (key) DO NOTHING;

-- ============================================
-- Time-Series Tables (TimescaleDB Hypertables)
-- ============================================

-- Sentiment data aggregated by ticker and time
CREATE TABLE IF NOT EXISTS sentiment_ticks (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    avg_sentiment DOUBLE PRECISION,
    weighted_sentiment DOUBLE PRECISION,
    mention_count INTEGER,
    sentiment_std DOUBLE PRECISION,
    source TEXT  -- 'reddit' or 'news'
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('sentiment_ticks', 'time', if_not_exists => TRUE);

-- Create index for fast ticker+time queries
CREATE INDEX IF NOT EXISTS idx_sentiment_ticker_time ON sentiment_ticks (ticker, time DESC);

-- Market data (OHLCV bars)
CREATE TABLE IF NOT EXISTS market_bars (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    open NUMERIC(10, 2),
    high NUMERIC(10, 2),
    low NUMERIC(10, 2),
    close NUMERIC(10, 2),
    volume BIGINT,
    vwap NUMERIC(10, 2),
    trade_count INTEGER
);

-- Convert to hypertable
SELECT create_hypertable('market_bars', 'time', if_not_exists => TRUE);

-- Create index
CREATE INDEX IF NOT EXISTS idx_market_ticker_time ON market_bars (ticker, time DESC);

-- Aggregated signals (for backtesting and analysis)
CREATE TABLE IF NOT EXISTS aggregated_signals (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    window_size TEXT,  -- '1min', '5min', '15min'
    avg_sentiment DOUBLE PRECISION,
    sentiment_momentum DOUBLE PRECISION,
    mention_volume INTEGER,
    price_change_pct DOUBLE PRECISION,
    volume_ratio DOUBLE PRECISION  -- current / avg volume
);

-- Convert to hypertable
SELECT create_hypertable('aggregated_signals', 'time', if_not_exists => TRUE);

-- Create index
CREATE INDEX IF NOT EXISTS idx_signals_ticker_time ON aggregated_signals (ticker, time DESC);

-- ============================================
-- Seed Data: Popular Tickers
-- ============================================

INSERT INTO tickers (symbol, company_name, sector, aliases) VALUES
-- FAANG + Big Tech
('AAPL', 'Apple Inc.', 'Technology', ARRAY['Apple', 'AAPL']),
('MSFT', 'Microsoft Corporation', 'Technology', ARRAY['Microsoft', 'MSFT']),
('GOOGL', 'Alphabet Inc.', 'Technology', ARRAY['Google', 'Alphabet', 'GOOGL', 'GOOG']),
('AMZN', 'Amazon.com Inc.', 'E-commerce', ARRAY['Amazon', 'AMZN']),
('META', 'Meta Platforms Inc.', 'Technology', ARRAY['Meta', 'Facebook', 'META']),
('NVDA', 'NVIDIA Corporation', 'Technology', ARRAY['NVIDIA', 'Nvidia', 'NVDA']),
('TSLA', 'Tesla Inc.', 'Automotive', ARRAY['Tesla', 'TSLA']),

-- Other Big Tech
('AMD', 'Advanced Micro Devices', 'Technology', ARRAY['AMD']),
('NFLX', 'Netflix Inc.', 'Entertainment', ARRAY['Netflix', 'NFLX']),
('INTC', 'Intel Corporation', 'Technology', ARRAY['Intel', 'INTC']),

-- Meme Stocks / WSB Favorites
('GME', 'GameStop Corp.', 'Retail', ARRAY['GameStop', 'GME']),
('AMC', 'AMC Entertainment Holdings', 'Entertainment', ARRAY['AMC']),
('BB', 'BlackBerry Limited', 'Technology', ARRAY['BlackBerry', 'BB']),
('PLTR', 'Palantir Technologies', 'Technology', ARRAY['Palantir', 'PLTR']),

-- Financial
('JPM', 'JPMorgan Chase & Co.', 'Finance', ARRAY['JPMorgan', 'JPM']),
('BAC', 'Bank of America Corp.', 'Finance', ARRAY['Bank of America', 'BofA', 'BAC']),
('GS', 'Goldman Sachs Group', 'Finance', ARRAY['Goldman Sachs', 'GS']),

-- Other Popular
('DIS', 'Walt Disney Company', 'Entertainment', ARRAY['Disney', 'DIS']),
('NKE', 'Nike Inc.', 'Consumer', ARRAY['Nike', 'NKE']),
('COIN', 'Coinbase Global Inc.', 'Finance', ARRAY['Coinbase', 'COIN']),
('PYPL', 'PayPal Holdings Inc.', 'Finance', ARRAY['PayPal', 'PYPL']),
('SQ', 'Block Inc.', 'Finance', ARRAY['Square', 'Block', 'SQ']),
('UBER', 'Uber Technologies', 'Technology', ARRAY['Uber', 'UBER']),
('RIVN', 'Rivian Automotive', 'Automotive', ARRAY['Rivian', 'RIVN']),
('F', 'Ford Motor Company', 'Automotive', ARRAY['Ford', 'F']),

-- SPY (S&P 500 ETF - often mentioned)
('SPY', 'SPDR S&P 500 ETF', 'ETF', ARRAY['SPY', 'S&P', 'S&P500'])

ON CONFLICT (symbol) DO NOTHING;

-- ============================================
-- Helpful Views
-- ============================================

-- View: Recent trades with P&L
CREATE OR REPLACE VIEW recent_trades AS
SELECT
    id,
    timestamp,
    ticker,
    action,
    quantity,
    price,
    total_value,
    signal_reason,
    sentiment_score
FROM trades
ORDER BY timestamp DESC
LIMIT 100;

-- View: Portfolio summary
CREATE OR REPLACE VIEW portfolio_summary AS
SELECT
    COUNT(*) as open_positions,
    SUM(quantity * current_price) as total_value,
    SUM(unrealized_pnl) as total_unrealized_pnl,
    SUM(realized_pnl) as total_realized_pnl
FROM positions;

-- ============================================
-- Functions
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for tickers table
CREATE TRIGGER update_tickers_updated_at
    BEFORE UPDATE ON tickers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for positions table
CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for config table
CREATE TRIGGER update_config_updated_at
    BEFORE UPDATE ON config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Completion Message
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '✅ SentimentEdge database initialized successfully!';
    RAISE NOTICE 'Tables created: %, Time-series tables: %',
        (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'),
        (SELECT COUNT(*) FROM timescaledb_information.hypertables);
    RAISE NOTICE 'Tickers seeded: %', (SELECT COUNT(*) FROM tickers);
END $$;
