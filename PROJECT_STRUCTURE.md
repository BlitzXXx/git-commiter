# Project Structure - SentimentEdge

Complete file tree with descriptions of every file in the project.

---

## 📁 Root Directory

```
sentiment-trader/
├── .env                          # Environment variables (NOT committed)
├── .env.example                  # Template for environment variables
├── .gitignore                    # Git ignore rules
├── docker-compose.yml            # Docker orchestration for all services
├── README.md                     # Quick start guide and overview
├── BLUEPRINT.md                  # Complete architecture documentation
├── PHASES.md                     # Step-by-step development guide
├── PROJECT_STRUCTURE.md          # This file - complete file tree
├── LICENSE                       # MIT License
│
├── services/                     # Backend microservices
├── frontend/                     # React dashboard
├── database/                     # Database schemas and migrations
├── monitoring/                   # Prometheus & Grafana configs
├── tests/                        # Test suites
└── docs/                         # Additional documentation
```

---

## 🔧 Services Directory

### `/services/ingestion/` - Data Ingestion Service

```
services/ingestion/
├── Dockerfile                    # Container build instructions
├── requirements.txt              # Python dependencies
├── main.py                       # Service entry point (orchestrates all fetchers)
├── reddit_fetcher.py             # Fetches posts from Reddit using PRAW
├── news_fetcher.py               # Fetches news from NewsAPI
├── market_fetcher.py             # Fetches market data from Alpaca WebSocket
├── config.py                     # Configuration and settings
└── utils/
    ├── deduplicator.py           # Content hash deduplication logic
    └── rate_limiter.py           # Rate limiting helper
```

**Key Files:**

- **main.py**: Runs all three fetchers (Reddit, News, Market) concurrently using asyncio
- **reddit_fetcher.py**:
  - Uses PRAW library to fetch from r/wallstreetbets and r/stocks
  - Polls every 30 seconds for new posts
  - Extracts: title, selftext, author, score, upvotes, comments
  - Pushes to Redis stream `raw:social`
  - Deduplicates using post ID and content hash
- **news_fetcher.py**:
  - Uses NewsAPI to fetch business/finance articles
  - Polls every 15 minutes (free tier: 100 req/day)
  - Searches for keywords: stock, market, earnings, trading
  - Pushes to Redis stream `raw:social`
- **market_fetcher.py**:
  - WebSocket connection to Alpaca data feed
  - Streams 1-minute bars (OHLCV) for tracked tickers
  - Pushes to Redis stream `raw:market`
  - Auto-reconnects on disconnect

---

### `/services/sentiment/` - Sentiment Analysis Service

```
services/sentiment/
├── Dockerfile
├── requirements.txt              # transformers, torch, spacy, redis
├── main.py                       # Service entry point
├── analyzer.py                   # FinBERT sentiment analysis
├── preprocessor.py               # Text cleaning and normalization
├── ticker_mapper.py              # Extract tickers from text (NER + regex)
├── config.py
└── models/                       # Downloaded models stored here
    └── finbert/                  # HuggingFace FinBERT cache
```

**Key Files:**

- **main.py**:
  - Consumes from Redis stream `raw:social`
  - Processes in batches (10-50 texts)
  - Pipeline: preprocess → extract tickers → sentiment analysis
  - Pushes to Redis stream `processed:sentiment`
- **analyzer.py**:
  - Loads ProsusAI/finbert model from HuggingFace
  - Batch inference for efficiency
  - Returns: {positive, negative, neutral} probabilities
  - Converts to score (-1 to +1): positive - negative
  - Target latency: <100ms per text (CPU), <20ms (GPU)
- **preprocessor.py**:
  - Removes URLs, @mentions, hashtags
  - Lowercases text
  - Removes extra whitespace
  - Keeps emojis (sentiment indicators)
- **ticker_mapper.py**:
  - Extracts cashtags: $AAPL, $TSLA using regex
  - Uses spaCy NER to find company names (ORG entities)
  - Queries PostgreSQL tickers table for name→symbol mapping
  - Fuzzy matching for partial names ("Apple" → AAPL)
  - Returns list of unique tickers per post

---

### `/services/trader/` - Trading Service (Signals + Execution)

```
services/trader/
├── Dockerfile
├── requirements.txt              # alpaca-py, sqlalchemy, redis, pydantic
├── main.py                       # Service orchestrator
├── config.yaml                   # Strategy parameters (editable without code changes)
├── aggregator.py                 # Time-window sentiment aggregation
├── signal_generator.py           # Trading logic (BUY/SELL signals)
├── risk_manager.py               # Risk validation and position sizing
├── executor.py                   # Order execution via Alpaca API
├── portfolio.py                  # Portfolio state management
└── models/
    ├── signal.py                 # Signal dataclass
    └── position.py               # Position dataclass
```

**Key Files:**

- **main.py**:
  - Runs three concurrent tasks:
    1. Aggregator (consumes sentiment, calculates windows)
    2. Signal generator (generates BUY/SELL signals)
    3. Executor (executes approved signals)
  - Coordinates all components
- **config.yaml**:
  ```yaml
  strategy:
    sentiment_threshold: 0.7      # Min sentiment for BUY
    min_mentions: 15              # Min posts in window
    volume_multiplier: 1.5        # Market volume vs average
    take_profit_pct: 0.03         # +3% profit target
    stop_loss_pct: 0.02           # -2% stop loss
    max_hold_seconds: 3600        # 1 hour max
  risk:
    max_positions: 5
    position_size_pct: 0.10       # 10% of capital per position
    max_daily_loss_pct: 0.05      # 5% daily loss = halt
    max_sector_exposure_pct: 0.30
  ```
- **aggregator.py**:
  - Consumes `processed:sentiment` stream
  - Groups by ticker and time window (1min, 5min, 15min)
  - Calculates:
    - avg_sentiment (mean score)
    - weighted_sentiment (weighted by upvotes/karma)
    - mention_count (number of posts)
    - sentiment_std (standard deviation)
    - sentiment_momentum (change from previous window)
  - Stores in TimescaleDB `sentiment_ticks` table
  - Also caches in Redis for fast access
- **signal_generator.py**:
  - Main trading logic
  - `_should_buy()`: Check if conditions met for BUY signal
  - `_should_sell()`: Check exit conditions for open positions
  - Generates Signal objects with reason and metadata
  - Validates with RiskManager before emitting
  - Pushes signals to Redis stream `signals`
- **risk_manager.py**:
  - `validate_trade()`: Check all risk rules before execution
  - `calculate_position_size()`: Size based on available capital
  - `should_halt_trading()`: Kill switch for daily loss limit
  - `get_sector_exposure()`: Check sector concentration
- **executor.py**:
  - Consumes from `signals` stream
  - Submits orders to Alpaca paper trading API
  - Monitors order fills
  - Places bracket orders (stop-loss + take-profit)
  - Retries on errors (exponential backoff)
  - Stores executed trades in database
- **portfolio.py**:
  - Syncs with Alpaca account
  - Tracks open positions
  - Calculates P&L (realized and unrealized)
  - Provides current state to risk manager

---

### `/services/api/` - API Gateway

```
services/api/
├── Dockerfile
├── requirements.txt              # fastapi, uvicorn, sqlalchemy, redis
├── main.py                       # FastAPI application
├── database.py                   # Database connection pool
├── redis_client.py               # Redis connection
├── websocket.py                  # WebSocket handler for real-time updates
├── routes/
│   ├── __init__.py
│   ├── positions.py              # GET /api/positions
│   ├── trades.py                 # GET /api/trades
│   ├── sentiment.py              # GET /api/sentiment/:ticker
│   ├── performance.py            # GET /api/performance
│   └── config.py                 # POST /api/config (update strategy)
├── models/
│   ├── position.py               # Pydantic models
│   ├── trade.py
│   └── sentiment.py
└── middleware/
    ├── cors.py                   # CORS configuration
    └── metrics.py                # Prometheus metrics
```

**Key Files:**

- **main.py**:
  - FastAPI app initialization
  - Includes all route modules
  - CORS middleware (allow frontend origin)
  - Exception handlers
  - Startup/shutdown events (connect/disconnect DB)
- **websocket.py**:
  - WebSocket endpoint `/ws/live`
  - Subscribes to Redis pub/sub channels
  - Emits updates to connected clients:
    - New positions opened/closed
    - Trades executed
    - Signals generated
    - P&L changes
  - Format: `{type: "position|trade|signal", data: {...}}`
  - Handles client disconnects gracefully
- **routes/positions.py**:
  - `GET /api/positions` - Returns current open positions
  - Queries PostgreSQL `positions` table
  - Includes unrealized P&L
- **routes/trades.py**:
  - `GET /api/trades?limit=50&ticker=AAPL` - Trade history
  - Queries PostgreSQL `trades` table
  - Supports filtering by ticker and date range
- **routes/sentiment.py**:
  - `GET /api/sentiment/:ticker?window=5min&limit=100`
  - Queries TimescaleDB `sentiment_ticks` table
  - Returns time-series sentiment data
- **routes/performance.py**:
  - `GET /api/performance` - Overall statistics
  - Calculates: total P&L, daily P&L, win rate, Sharpe ratio, max drawdown
  - Aggregates from trades and positions tables
- **routes/config.py**:
  - `POST /api/config` - Update strategy parameters
  - Updates config in database
  - Signals trader service to reload config

---

## 🎨 Frontend Directory

### `/frontend/` - React Dashboard

```
frontend/
├── Dockerfile
├── package.json                  # Dependencies (React, Recharts, TanStack Query)
├── tsconfig.json                 # TypeScript config
├── tailwind.config.js            # Tailwind CSS config
├── vite.config.ts                # Vite bundler config
├── index.html
├── public/
│   └── favicon.ico
└── src/
    ├── main.tsx                  # App entry point
    ├── App.tsx                   # Main layout and routing
    ├── styles/
    │   └── index.css             # Global styles + Tailwind imports
    ├── components/
    │   ├── Layout/
    │   │   ├── Header.tsx        # Top navigation bar
    │   │   ├── Sidebar.tsx       # Side navigation (optional)
    │   │   └── Footer.tsx
    │   ├── Dashboard/
    │   │   ├── PnLChart.tsx      # Equity curve line chart (Recharts)
    │   │   ├── PositionsTable.tsx # Current holdings table
    │   │   ├── TradesTable.tsx   # Recent trades table
    │   │   ├── SentimentChart.tsx # Per-ticker sentiment chart
    │   │   ├── SignalsFeed.tsx   # Live signal feed
    │   │   └── PerformanceStats.tsx # Metrics cards (P&L, win rate, etc.)
    │   └── Common/
    │       ├── Card.tsx          # Reusable card component
    │       ├── Badge.tsx         # Status badges (BUY/SELL)
    │       ├── Spinner.tsx       # Loading spinner
    │       └── ErrorBoundary.tsx # Error handling
    ├── hooks/
    │   ├── useWebSocket.ts       # WebSocket connection hook
    │   ├── useAPI.ts             # REST API hook (wraps TanStack Query)
    │   ├── usePositions.ts       # Fetch positions data
    │   ├── useTrades.ts          # Fetch trades data
    │   └── useSentiment.ts       # Fetch sentiment data
    ├── utils/
    │   ├── formatters.ts         # Number/date formatting
    │   ├── colors.ts             # Color helpers (green/red for P&L)
    │   └── api.ts                # API client (axios/fetch wrapper)
    ├── types/
    │   ├── position.ts           # TypeScript types
    │   ├── trade.ts
    │   ├── signal.ts
    │   └── sentiment.ts
    └── config/
        └── constants.ts          # API URLs, WebSocket URLs
```

**Key Files:**

- **App.tsx**:
  - Main dashboard layout
  - Grid layout with:
    - Header (title, status indicator)
    - P&L Chart (top, full width)
    - Positions Table (left)
    - Trades Table (right)
    - Signals Feed (bottom)
  - WebSocket connection management
  - Dark mode toggle
- **PnLChart.tsx**:
  - Line chart of equity over time
  - Uses Recharts library
  - Real-time updates via WebSocket
  - Shows total portfolio value
- **PositionsTable.tsx**:
  - Table of current holdings
  - Columns: Ticker, Qty, Entry Price, Current Price, P&L, P&L %
  - Color-coded P&L (green/red)
  - Updates in real-time
- **SignalsFeed.tsx**:
  - Live feed of trading signals
  - Shows: Time, Ticker, Action (BUY/SELL), Reason, Confidence
  - Auto-scrolls to latest
  - Updates via WebSocket
- **useWebSocket.ts**:
  - Manages WebSocket connection
  - Auto-reconnect on disconnect
  - Handles incoming messages
  - Provides connection status

---

## 🗄️ Database Directory

### `/database/` - Schemas and Migrations

```
database/
├── init.sql                      # Initial setup script (run on container start)
├── migrations/
│   ├── 001_create_tables.sql     # Create PostgreSQL tables
│   ├── 002_create_hypertables.sql # Create TimescaleDB hypertables
│   └── 003_create_indexes.sql    # Create indexes for performance
└── seeds/
    └── tickers.sql               # Seed data for tickers table
```

**Key Files:**

- **init.sql**:
  - Runs on PostgreSQL container startup
  - Enables TimescaleDB extension
  - Runs migrations in order
  - Creates initial tables and seeds data
- **001_create_tables.sql**:
  - Tables: tickers, trades, positions, config
  - Includes all constraints (PKs, FKs, NOT NULL)
- **002_create_hypertables.sql**:
  - Tables: sentiment_ticks, market_bars, aggregated_signals
  - Converts to TimescaleDB hypertables (partitioned by time)
  - Sets chunk interval to 1 day for optimal query performance
- **003_create_indexes.sql**:
  - Indexes on (ticker, time DESC) for fast time-series queries
  - Indexes on trades(timestamp), positions(ticker)
  - Composite indexes for common query patterns
- **seeds/tickers.sql**:
  - Inserts top 50 most-discussed stocks
  - Includes: symbol, company_name, sector, aliases

---

## 📊 Monitoring Directory

### `/monitoring/` - Prometheus & Grafana

```
monitoring/
├── prometheus.yml                # Prometheus config (scrape targets)
└── grafana/
    ├── datasources/
    │   └── prometheus.yml        # Auto-configure Prometheus datasource
    └── dashboards/
        ├── system.json           # System metrics (CPU, memory, disk)
        ├── trading.json          # Trading metrics (P&L, trades, win rate)
        └── pipeline.json         # Data pipeline metrics (latency, throughput)
```

**Key Files:**

- **prometheus.yml**:
  - Scrape configs for all services
  - Metrics endpoints: `/metrics` on each service
  - Scrape interval: 15 seconds
- **grafana/dashboards/trading.json**:
  - Panels:
    - Equity curve over time
    - Win rate, Sharpe ratio
    - Total trades, open positions
    - Daily P&L
    - Top performing tickers

---

## 🧪 Tests Directory

### `/tests/` - Test Suites

```
tests/
├── conftest.py                   # Pytest fixtures
├── unit/
│   ├── test_sentiment.py         # Test sentiment analyzer
│   ├── test_ticker_mapper.py     # Test ticker extraction
│   ├── test_signal_generator.py  # Test trading logic
│   └── test_risk_manager.py      # Test risk rules
├── integration/
│   ├── test_pipeline.py          # Test full data pipeline
│   ├── test_database.py          # Test database operations
│   └── test_api.py               # Test API endpoints
└── e2e/
    └── test_trading_flow.py      # End-to-end trading simulation
```

**Key Files:**

- **conftest.py**:
  - Pytest fixtures: mock Redis, mock database, test data
  - Cleanup after tests
- **test_sentiment.py**:
  - Test FinBERT model loads
  - Test sentiment scoring (positive/negative/neutral)
  - Test batch processing
- **test_signal_generator.py**:
  - Test BUY signal conditions
  - Test SELL signal conditions
  - Test edge cases
- **test_risk_manager.py**:
  - Test position limits
  - Test loss limits
  - Test position sizing calculation
- **test_trading_flow.py**:
  - Inject mock posts
  - Verify signal generation
  - Verify trade execution
  - Check database state

---

## 📝 Documentation Directory

### `/docs/` - Additional Docs

```
docs/
├── API.md                        # API endpoint documentation
├── DEPLOYMENT.md                 # Deployment guide (local, cloud, k8s)
└── TROUBLESHOOTING.md            # Common issues and solutions
```

---

## 🔧 Configuration Files (Root)

### `.env.example`

Template for environment variables. Copy to `.env` and fill in your API keys.

### `.gitignore`

Ignore:
- `.env` (secrets)
- `node_modules/`
- `__pycache__/`
- `*.pyc`
- `.vscode/`, `.idea/`
- `data/` (local data files)
- Docker volumes

### `docker-compose.yml`

Orchestrates all services. Run with:
```bash
docker-compose up --build
```

---

## 📊 File Count Summary

| Category | Count | Description |
|----------|-------|-------------|
| **Backend Services** | ~30 files | Python microservices |
| **Frontend** | ~25 files | React TypeScript app |
| **Database** | ~5 files | SQL schemas and migrations |
| **Configuration** | ~10 files | Docker, env, configs |
| **Tests** | ~10 files | Unit, integration, e2e tests |
| **Monitoring** | ~5 files | Prometheus, Grafana |
| **Docs** | ~7 files | README, BLUEPRINT, PHASES, etc. |
| **Total** | ~92 files | Complete project |

---

## 🔍 Key Entry Points

When developing or debugging, start with these files:

1. **Start System**: `docker-compose up`
2. **Ingestion**: `services/ingestion/main.py`
3. **Sentiment**: `services/sentiment/main.py`
4. **Trading**: `services/trader/main.py`
5. **API**: `services/api/main.py`
6. **Frontend**: `frontend/src/App.tsx`
7. **Config**: `services/trader/config.yaml`
8. **Logs**: `docker-compose logs -f <service>`

---

## 🎯 Development Workflow

Typical development flow:

1. **Modify code** in respective service directory
2. **Rebuild service**: `docker-compose up <service> --build`
3. **Check logs**: `docker-compose logs -f <service>`
4. **Test**: `pytest tests/unit/test_<component>.py`
5. **Verify in dashboard**: http://localhost:3000

---

## 📚 Further Reading

- **BLUEPRINT.md** - Detailed architecture, data models, algorithms
- **PHASES.md** - Step-by-step build guide
- **README.md** - Quick start and setup
- **API.md** - Complete API reference
- **DEPLOYMENT.md** - Production deployment guide

---

**This structure is designed to be:**
- ✅ **Modular** - Each service is independent
- ✅ **Testable** - Clear separation of concerns
- ✅ **Scalable** - Easy to add new features
- ✅ **Maintainable** - Well-organized and documented
