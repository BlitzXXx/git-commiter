# SentimentEdge - Real-Time Market Sentiment Trading System
## Complete Project Blueprint

---

## 🎯 Project Overview

**SentimentEdge** is a production-ready algorithmic trading system that:
- Ingests real-time social media sentiment (Reddit, News)
- Analyzes sentiment using FinBERT (finance-tuned transformer model)
- Generates trading signals based on sentiment spikes + market data
- Executes paper trades via Alpaca API
- Provides live dashboard for monitoring performance

**Key Value:** Demonstrates end-to-end ML pipeline, streaming architecture, and production deployment skills.

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  EXTERNAL DATA SOURCES                                           │
├─────────────────────────────────────────────────────────────────┤
│  • Reddit API (PRAW) - r/wallstreetbets, r/stocks               │
│  • NewsAPI - Financial news articles                             │
│  • Alpaca Market Data API - Real-time stock prices & volumes    │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  INGESTION LAYER (Python Services)                               │
├─────────────────────────────────────────────────────────────────┤
│  • reddit_fetcher.py - Poll Reddit every 30s for new posts      │
│  • news_fetcher.py - Poll NewsAPI every 5 min                   │
│  • market_fetcher.py - WebSocket connection to Alpaca           │
│  Features:                                                       │
│    - Rate limiting (respect API limits)                         │
│    - Retry with exponential backoff                             │
│    - Deduplication (content hashing)                            │
│    - Error handling & logging                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  MESSAGE QUEUE (Redis Streams)                                   │
├─────────────────────────────────────────────────────────────────┤
│  Streams:                                                        │
│    • raw:social - Raw Reddit/news posts                         │
│    • raw:market - Market tick data                              │
│    • processed:sentiment - Scored posts                         │
│    • signals - Trading signals                                  │
│  Benefits: Decoupling, buffering, replay capability             │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  PREPROCESSING SERVICE (FastAPI)                                 │
├─────────────────────────────────────────────────────────────────┤
│  • Text cleaning (lowercase, remove URLs, special chars)        │
│  • Ticker extraction (regex patterns for $AAPL, TSLA, etc.)     │
│  • Entity recognition (spaCy NER for company names)             │
│  • Ticker mapping (company name → ticker symbol)                │
│  • Metadata enrichment (author karma, post upvotes)             │
│  Output: Cleaned text + mapped tickers                          │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  SENTIMENT ANALYSIS SERVICE (FastAPI + ML)                       │
├─────────────────────────────────────────────────────────────────┤
│  Model: FinBERT (ProsusAI/finbert)                              │
│  Inference:                                                      │
│    • Batch processing (10-50 texts per batch)                   │
│    • GPU optional (falls back to CPU)                           │
│    • Returns: {positive, negative, neutral} scores              │
│  Performance:                                                    │
│    • CPU: ~50-100ms per text                                    │
│    • GPU: ~10-20ms per text                                     │
│  Output: Sentiment score (-1 to +1) + confidence                │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  AGGREGATION SERVICE (Python + Pandas)                           │
├─────────────────────────────────────────────────────────────────┤
│  Windows: 1min, 5min, 15min rolling windows                     │
│  Metrics per ticker:                                             │
│    • avg_sentiment (mean sentiment score)                       │
│    • weighted_sentiment (weighted by upvotes/karma)             │
│    • mention_count (volume of posts)                            │
│    • sentiment_momentum (change over last window)               │
│    • std_dev (volatility of sentiment)                          │
│  Storage: TimescaleDB (hypertables for time-series)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  SIGNAL GENERATION ENGINE (Python)                               │
├─────────────────────────────────────────────────────────────────┤
│  Strategy: Sentiment Spike + Volume Confirmation                │
│  BUY Signal Conditions:                                          │
│    1. avg_sentiment > 0.7 (strong positive)                     │
│    2. mention_count > 15 posts in 5min                          │
│    3. sentiment_momentum > 2 std deviations                     │
│    4. market volume > 1.5x average                              │
│    5. Market hours only                                         │
│    6. Not already in position                                   │
│  SELL Signal Conditions:                                         │
│    1. Take profit: +3% gain                                     │
│    2. Stop loss: -2% loss                                       │
│    3. Time exit: 1 hour max hold                                │
│    4. Sentiment reversal: score < 0.3                           │
│  Output: Signal(ticker, action, confidence, reason)             │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  RISK MANAGEMENT MODULE                                          │
├─────────────────────────────────────────────────────────────────┤
│  Position Limits:                                                │
│    • Max 5 concurrent positions                                 │
│    • Max 10% capital per position                               │
│    • Max 30% in any sector                                      │
│  Loss Limits:                                                    │
│    • Daily loss limit: 5% of capital                            │
│    • Per-trade stop loss: 2%                                    │
│    • Kill switch if daily limit hit                             │
│  Validation:                                                     │
│    • Check before every trade                                   │
│    • Block trades that violate limits                           │
│    • Alert on unusual activity                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  EXECUTION ENGINE (Alpaca Paper Trading)                         │
├─────────────────────────────────────────────────────────────────┤
│  Order Types:                                                    │
│    • Market orders (immediate fill)                             │
│    • Limit orders (price control)                               │
│  Features:                                                       │
│    • Retry logic (3 attempts)                                   │
│    • Fill monitoring                                            │
│    • Position tracking                                          │
│    • Auto stop-loss/take-profit orders                          │
│  API: Alpaca Paper Trading (free, unlimited)                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  STORAGE LAYER                                                   │
├─────────────────────────────────────────────────────────────────┤
│  TimescaleDB (PostgreSQL extension):                             │
│    • sentiment_ticks - Time-series sentiment data               │
│    • market_bars - OHLCV price data                             │
│    • aggregated_signals - Windowed metrics                      │
│  PostgreSQL:                                                     │
│    • trades - Executed trades history                           │
│    • positions - Current positions                              │
│    • tickers - Symbol metadata & mappings                       │
│  Redis:                                                          │
│    • Live positions cache                                       │
│    • Recent sentiment scores                                    │
│    • Rate limiting counters                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  API GATEWAY (FastAPI)                                           │
├─────────────────────────────────────────────────────────────────┤
│  REST Endpoints:                                                 │
│    GET  /api/positions - Current positions                      │
│    GET  /api/trades - Trade history                             │
│    GET  /api/sentiment/:ticker - Sentiment data                 │
│    GET  /api/performance - P&L metrics                          │
│    POST /api/config - Update strategy params                    │
│  WebSocket:                                                      │
│    /ws/live - Real-time updates (positions, P&L, signals)       │
│  Auth: JWT tokens (optional for MVP)                            │
│  Rate Limiting: 100 req/min per IP                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  FRONTEND DASHBOARD (React + TypeScript)                         │
├─────────────────────────────────────────────────────────────────┤
│  Components:                                                     │
│    • P&L Chart (Recharts) - Real-time equity curve             │
│    • Positions Table - Current holdings                         │
│    • Signals Feed - Recent trading signals                      │
│    • Sentiment Charts - Per-ticker sentiment trends            │
│    • Trade Log - Executed trades with reasons                   │
│    • Config Panel - Adjust strategy parameters                  │
│  Features:                                                       │
│    • WebSocket updates (live data)                              │
│    • Responsive design (mobile-friendly)                        │
│    • Dark mode                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  MONITORING & OBSERVABILITY                                      │
├─────────────────────────────────────────────────────────────────┤
│  Logging:                                                        │
│    • Structured JSON logs (timestamp, level, service, message)  │
│    • Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL          │
│  Metrics (Prometheus):                                           │
│    • api_latency_seconds (p50, p95, p99)                        │
│    • sentiment_processing_time_seconds                          │
│    • trades_executed_total                                      │
│    • positions_open_count                                       │
│    • daily_pnl_dollars                                          │
│  Dashboards (Grafana):                                           │
│    • System health (CPU, memory, disk)                          │
│    • Trading performance (P&L, win rate, Sharpe)                │
│    • Data pipeline (message lag, throughput)                    │
│  Alerts:                                                         │
│    • Daily loss > 5%                                            │
│    • Service down > 2 minutes                                   │
│    • API errors > 10/min                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Data Models & Schemas

### TimescaleDB Tables

```sql
-- Sentiment time-series data
CREATE TABLE sentiment_ticks (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    avg_sentiment DOUBLE PRECISION,
    weighted_sentiment DOUBLE PRECISION,
    mention_count INTEGER,
    sentiment_std DOUBLE PRECISION,
    source TEXT  -- 'reddit' or 'news'
);
SELECT create_hypertable('sentiment_ticks', 'time');
CREATE INDEX idx_ticker_time ON sentiment_ticks (ticker, time DESC);

-- Market data (OHLCV bars)
CREATE TABLE market_bars (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,
    vwap NUMERIC
);
SELECT create_hypertable('market_bars', 'time');

-- Aggregated signals
CREATE TABLE aggregated_signals (
    time TIMESTAMPTZ NOT NULL,
    ticker TEXT NOT NULL,
    window_size TEXT,  -- '1min', '5min', '15min'
    avg_sentiment DOUBLE PRECISION,
    sentiment_momentum DOUBLE PRECISION,
    mention_volume INTEGER,
    price_change_pct DOUBLE PRECISION,
    volume_ratio DOUBLE PRECISION  -- current / avg volume
);
SELECT create_hypertable('aggregated_signals', 'time');
```

### PostgreSQL Tables

```sql
-- Trade execution history
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'BUY' or 'SELL'
    quantity INTEGER NOT NULL,
    price NUMERIC NOT NULL,
    total_value NUMERIC NOT NULL,
    commission NUMERIC DEFAULT 0,
    signal_reason TEXT,
    sentiment_score DOUBLE PRECISION,
    order_id TEXT UNIQUE  -- Alpaca order ID
);
CREATE INDEX idx_trades_timestamp ON trades (timestamp DESC);
CREATE INDEX idx_trades_ticker ON trades (ticker);

-- Current positions
CREATE TABLE positions (
    ticker TEXT PRIMARY KEY,
    quantity INTEGER NOT NULL,
    avg_entry_price NUMERIC NOT NULL,
    current_price NUMERIC,
    unrealized_pnl NUMERIC,
    realized_pnl NUMERIC DEFAULT 0,
    entry_timestamp TIMESTAMPTZ NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Ticker metadata & mappings
CREATE TABLE tickers (
    symbol TEXT PRIMARY KEY,
    company_name TEXT,
    sector TEXT,
    aliases TEXT[],  -- ['AAPL', 'Apple', 'Apple Inc']
    is_active BOOLEAN DEFAULT TRUE,
    last_traded TIMESTAMPTZ
);

-- Strategy configuration
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default config
INSERT INTO config (key, value, description) VALUES
('sentiment_threshold', '0.7', 'Min sentiment score for BUY signal'),
('min_mentions', '15', 'Min post count in window'),
('max_positions', '5', 'Max concurrent positions'),
('position_size_pct', '0.10', 'Percent of capital per position'),
('take_profit_pct', '0.03', 'Take profit at +3%'),
('stop_loss_pct', '0.02', 'Stop loss at -2%'),
('max_hold_seconds', '3600', 'Max holding time (1 hour)');
```

### Redis Data Structures

```
# Live positions (hash)
positions:{ticker} -> {
    "quantity": 100,
    "avg_price": 150.50,
    "entry_time": "2025-11-22T10:30:00Z"
}

# Recent sentiment (sorted set by timestamp)
sentiment:{ticker}:recent -> [
    (timestamp1, score1),
    (timestamp2, score2),
    ...
]

# Rate limiting (counter with TTL)
ratelimit:api:{ip} -> count (expires in 60s)

# Message queues (streams)
raw:social -> stream of social posts
raw:market -> stream of market data
processed:sentiment -> stream of scored posts
signals -> stream of trading signals
```

---

## 🧠 Machine Learning Pipeline

### Sentiment Model: FinBERT

**Model:** `ProsusAI/finbert` (HuggingFace)
- **Type:** BERT fine-tuned on financial texts
- **Input:** Text (max 512 tokens)
- **Output:** {positive, negative, neutral} probabilities

**Preprocessing:**
```python
def preprocess_text(text: str) -> str:
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    # Remove mentions
    text = re.sub(r'@\w+', '', text)
    # Remove hashtags (keep text)
    text = re.sub(r'#(\w+)', r'\1', text)
    # Lowercase
    text = text.lower()
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text
```

**Inference:**
```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")

def get_sentiment(text: str) -> dict:
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.softmax(outputs.logits, dim=-1).numpy()[0]

    # Map to sentiment score (-1 to +1)
    score = probs[0] - probs[1]  # positive - negative

    return {
        "score": float(score),
        "positive": float(probs[0]),
        "negative": float(probs[1]),
        "neutral": float(probs[2]),
        "confidence": float(max(probs))
    }
```

### Ticker Extraction & Mapping

**Patterns:**
```python
# Cashtag pattern: $AAPL, $TSLA
cashtag_pattern = r'\$([A-Z]{1,5})\b'

# Common mentions: "Apple stock", "Tesla shares"
company_patterns = {
    "Apple": ["AAPL"],
    "Tesla": ["TSLA"],
    "Microsoft": ["MSFT"],
    # ... load from database
}
```

**Entity Recognition:**
```python
import spacy

nlp = spacy.load("en_core_web_sm")

def extract_tickers(text: str) -> list[str]:
    tickers = set()

    # Extract cashtags
    cashtags = re.findall(r'\$([A-Z]{1,5})\b', text)
    tickers.update(cashtags)

    # NER for company names
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "ORG":
            # Look up in mapping database
            ticker = lookup_ticker(ent.text)
            if ticker:
                tickers.add(ticker)

    return list(tickers)
```

---

## 🎮 Trading Strategy Logic

### Signal Generation

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class Signal:
    timestamp: datetime
    ticker: str
    action: str  # 'BUY' or 'SELL'
    confidence: float
    reason: str
    metadata: dict

class SignalGenerator:
    def __init__(self, config: dict):
        self.sentiment_threshold = config['sentiment_threshold']
        self.min_mentions = config['min_mentions']
        self.volume_multiplier = 1.5

    def generate(self, ticker: str) -> Signal | None:
        # Get 5-minute aggregated data
        sentiment_data = self.get_sentiment_aggregate(ticker, window='5min')
        market_data = self.get_market_data(ticker, bars=20)

        if not sentiment_data or not market_data:
            return None

        # Check for BUY signal
        if self._should_buy(sentiment_data, market_data, ticker):
            return Signal(
                timestamp=datetime.utcnow(),
                ticker=ticker,
                action='BUY',
                confidence=sentiment_data['avg_sentiment'],
                reason=f"Sentiment spike: {sentiment_data['avg_sentiment']:.2f}, "
                       f"Mentions: {sentiment_data['mention_count']}",
                metadata={
                    'sentiment': sentiment_data,
                    'price': market_data['close']
                }
            )

        # Check for SELL signal (if in position)
        if self.is_in_position(ticker):
            if self._should_sell(ticker, market_data):
                return Signal(
                    timestamp=datetime.utcnow(),
                    ticker=ticker,
                    action='SELL',
                    confidence=1.0,
                    reason=self._get_exit_reason(ticker, market_data),
                    metadata={'price': market_data['close']}
                )

        return None

    def _should_buy(self, sentiment, market, ticker) -> bool:
        # Calculate sentiment momentum
        momentum = sentiment['sentiment_momentum']
        std_dev = sentiment.get('sentiment_std', 0.1)

        return all([
            sentiment['avg_sentiment'] > self.sentiment_threshold,
            sentiment['mention_count'] >= self.min_mentions,
            momentum > 2 * std_dev,  # Spike detection
            market['volume'] > market['avg_volume'] * self.volume_multiplier,
            self._is_market_hours(),
            not self.is_in_position(ticker),
            self._has_buying_power()
        ])

    def _should_sell(self, ticker, market) -> bool:
        position = self.get_position(ticker)
        current_price = market['close']
        entry_price = position['avg_entry_price']

        pnl_pct = (current_price - entry_price) / entry_price
        hold_time = (datetime.utcnow() - position['entry_time']).total_seconds()

        # Get current sentiment
        sentiment = self.get_sentiment_aggregate(ticker, window='5min')

        return any([
            pnl_pct >= 0.03,  # Take profit
            pnl_pct <= -0.02,  # Stop loss
            hold_time > 3600,  # Max hold time
            sentiment and sentiment['avg_sentiment'] < 0.3  # Sentiment reversal
        ])
```

### Risk Management

```python
class RiskManager:
    def __init__(self, config: dict):
        self.max_positions = config['max_positions']
        self.position_size_pct = config['position_size_pct']
        self.max_daily_loss_pct = 0.05
        self.max_sector_exposure_pct = 0.30

    def validate_trade(self, signal: Signal, portfolio: dict) -> tuple[bool, str]:
        """Returns (is_valid, reason)"""

        if signal.action == 'BUY':
            # Check position count
            if len(portfolio['positions']) >= self.max_positions:
                return False, "Max positions reached"

            # Check buying power
            position_value = portfolio['cash'] * self.position_size_pct
            if position_value > portfolio['cash']:
                return False, "Insufficient buying power"

            # Check daily loss limit
            if portfolio['daily_pnl_pct'] <= -self.max_daily_loss_pct:
                return False, "Daily loss limit hit - trading halted"

            # Check sector exposure
            ticker_sector = self.get_sector(signal.ticker)
            sector_exposure = self.get_sector_exposure(portfolio, ticker_sector)
            if sector_exposure + position_value > portfolio['total_value'] * self.max_sector_exposure_pct:
                return False, f"Max sector exposure for {ticker_sector}"

            return True, "Valid"

        elif signal.action == 'SELL':
            # Always allow sells (to exit positions)
            if signal.ticker not in portfolio['positions']:
                return False, "Not in position"
            return True, "Valid"

        return False, "Unknown action"

    def calculate_position_size(self, signal: Signal, portfolio: dict) -> int:
        """Calculate number of shares to buy"""
        max_value = portfolio['cash'] * self.position_size_pct
        current_price = self.get_current_price(signal.ticker)
        shares = int(max_value / current_price)
        return max(1, shares)  # At least 1 share
```

---

## 🔧 Technology Stack

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Data Ingestion** | Python 3.11+ | Best libraries for APIs (PRAW, requests) |
| **Message Queue** | Redis Streams | Simpler than Kafka, sufficient for MVP |
| **ML Framework** | PyTorch + HuggingFace | Industry standard, FinBERT available |
| **NLP** | spaCy | Fast NER, good for entity extraction |
| **API Framework** | FastAPI | Fast, async, auto docs, WebSocket support |
| **Time-Series DB** | TimescaleDB | SQL + time-series, easier than ClickHouse |
| **Cache** | Redis | Fast in-memory store, pub/sub |
| **Frontend** | React + TypeScript | Standard, good ecosystem |
| **Charts** | Recharts | Simple, React-native charting |
| **WebSocket** | FastAPI WebSocket | Built-in, no extra deps |
| **Containerization** | Docker + Compose | Reproducible, easy deployment |
| **Testing** | pytest | Python standard |
| **Linting** | ruff + black + mypy | Fast, comprehensive |
| **CI/CD** | GitHub Actions | Free, integrated |
| **Monitoring** | Prometheus + Grafana | Industry standard, self-hosted |

---

## 🚀 Deployment Architecture

### Local Development (Docker Compose)

```yaml
services:
  # Databases
  postgres:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_DB: sentimentedge
      POSTGRES_USER: trader
      POSTGRES_PASSWORD: secret
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # Services
  ingestion:
    build: ./services/ingestion
    environment:
      REDDIT_CLIENT_ID: ${REDDIT_CLIENT_ID}
      REDDIT_CLIENT_SECRET: ${REDDIT_CLIENT_SECRET}
      NEWS_API_KEY: ${NEWS_API_KEY}
    depends_on:
      - redis

  sentiment:
    build: ./services/sentiment
    environment:
      MODEL_NAME: ProsusAI/finbert
      BATCH_SIZE: 20
    depends_on:
      - redis

  trader:
    build: ./services/trader
    environment:
      ALPACA_API_KEY: ${ALPACA_API_KEY}
      ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY}
      ALPACA_BASE_URL: https://paper-api.alpaca.markets
    depends_on:
      - redis
      - postgres

  api:
    build: ./services/api
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - api

  # Monitoring
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
```

### Production (Kubernetes) - Future

- Deploy to GKE/EKS/AKS
- Horizontal Pod Autoscaler for services
- Managed PostgreSQL (AWS RDS, GCP Cloud SQL)
- Managed Redis (AWS ElastiCache, GCP Memorystore)
- Ingress with SSL/TLS
- Secret management (Vault, AWS Secrets Manager)

---

## 📈 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Ingestion Latency** | <5s from post to DB | Track timestamp differences |
| **Sentiment Analysis** | <100ms per text (CPU) | Prometheus histogram |
| **Signal Generation** | <50ms | Execution time logging |
| **Order Execution** | <500ms | Alpaca API latency |
| **End-to-End** | <10s from post to trade | Full pipeline trace |
| **API Response** | p95 <200ms | FastAPI middleware |
| **WebSocket Updates** | <100ms | Client-side measurement |
| **Data Throughput** | 1000+ posts/hour | Redis stream metrics |

---

## 🧪 Testing Strategy

### Unit Tests (pytest)

```python
# Test sentiment analysis
def test_sentiment_analyzer():
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze("Apple stock is soaring!")
    assert result['score'] > 0.5
    assert 'confidence' in result

# Test ticker extraction
def test_ticker_extraction():
    extractor = TickerExtractor()
    tickers = extractor.extract("$AAPL and $TSLA are trending")
    assert 'AAPL' in tickers
    assert 'TSLA' in tickers

# Test risk manager
def test_risk_manager_max_positions():
    rm = RiskManager(config={'max_positions': 5})
    portfolio = {'positions': ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN']}
    signal = Signal(ticker='NVDA', action='BUY')
    is_valid, reason = rm.validate_trade(signal, portfolio)
    assert not is_valid
    assert "Max positions" in reason
```

### Integration Tests

```python
# Test full pipeline
@pytest.mark.integration
async def test_sentiment_pipeline():
    # Mock Reddit post
    post = create_mock_post(text="$AAPL to the moon! 🚀")

    # Process through pipeline
    processed = await preprocess(post)
    sentiment = await analyze_sentiment(processed)
    stored = await store_sentiment(sentiment)

    # Verify storage
    result = await db.query("SELECT * FROM sentiment_ticks WHERE ticker='AAPL'")
    assert result[0]['avg_sentiment'] > 0.5
```

### End-to-End Tests

```python
# Test trading workflow
@pytest.mark.e2e
async def test_trading_workflow():
    # Inject high-sentiment posts
    await inject_mock_posts(ticker='AAPL', sentiment=0.9, count=20)

    # Wait for signal generation
    await asyncio.sleep(5)

    # Check if trade executed
    trades = await get_recent_trades()
    assert any(t['ticker'] == 'AAPL' and t['action'] == 'BUY' for t in trades)
```

---

## 🔒 Security Considerations

1. **API Keys**
   - Store in `.env` (never commit)
   - Use environment variables
   - Rotate regularly

2. **Rate Limiting**
   - Per-IP limits on API (100 req/min)
   - Respect external API limits

3. **Input Validation**
   - Pydantic schemas for all inputs
   - Sanitize text data
   - Validate ticker symbols

4. **SQL Injection Prevention**
   - Use parameterized queries (SQLAlchemy)
   - No raw SQL with user input

5. **Access Control**
   - JWT auth for API (optional in MVP)
   - Dashboard login (future)

6. **Data Privacy**
   - Don't store PII
   - Comply with API TOS

---

## 📊 Success Metrics

### Technical Metrics
- System uptime: >99%
- API latency p95: <200ms
- Zero data loss (messages processed)
- Test coverage: >80%

### Trading Metrics (Paper)
- Win rate: Target >50%
- Average profit per trade: >1%
- Sharpe ratio: >1.0
- Max drawdown: <15%

### Product Metrics
- Dashboard load time: <2s
- Real-time update latency: <500ms
- Data freshness: <30s

---

## 🎓 Learning Outcomes

This project demonstrates:

1. **Distributed Systems** - Microservices, message queues, async processing
2. **Machine Learning** - NLP, sentiment analysis, production ML
3. **Data Engineering** - Stream processing, time-series data, ETL
4. **Backend Development** - FastAPI, WebSockets, REST APIs
5. **Frontend Development** - React, real-time updates, data viz
6. **DevOps** - Docker, CI/CD, monitoring, infrastructure
7. **Domain Knowledge** - Financial markets, trading strategies, risk management

---

## 📚 External Dependencies & APIs

### Required (Free Tiers)

1. **Alpaca Markets**
   - Sign up: https://alpaca.markets
   - Paper trading API keys (unlimited, free)
   - Real-time market data (free for paper trading)

2. **Reddit API**
   - Create app: https://www.reddit.com/prefs/apps
   - Free tier: 60 requests/minute
   - PRAW library handles auth

3. **NewsAPI**
   - Sign up: https://newsapi.org
   - Free tier: 100 requests/day
   - Upgrade: $449/month for more (optional)

### Optional

4. **Polygon.io** (better market data)
   - Free tier: delayed data
   - $199/month: real-time

5. **Alpha Vantage** (alternative market data)
   - Free tier: 5 API requests/minute

---

## 🔮 Future Enhancements

### Phase 2 Features
- Multi-timeframe analysis (1m, 5m, 15m, 1h)
- More sophisticated NLP (BERT embeddings, topic modeling)
- Backtesting framework with historical replay
- Strategy optimization (grid search, genetic algorithms)

### Phase 3 Features
- Live trading mode (real money, small capital)
- Multiple strategies (mean reversion, momentum)
- Options trading signals
- Portfolio rebalancing

### Phase 4 Features
- Machine learning signal generation (LSTM, transformers)
- Reinforcement learning for strategy optimization
- Multi-asset trading (stocks, crypto, forex)
- Mobile app (React Native)

---

## 📞 Support & Resources

- **Documentation**: See `README.md` for setup
- **Phase Guide**: See `PHASES.md` for development steps
- **Architecture**: This document (BLUEPRINT.md)
- **Issues**: Use GitHub issues for bugs/features

---

**Built with ❤️ for learning, not financial advice.**
**Always trade paper accounts first. Never risk money you can't afford to lose.**
