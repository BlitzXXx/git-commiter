# Development Phases - SentimentEdge

This document breaks down the project into **manageable phases** that can be completed step-by-step. Each phase is self-contained and can be given to an LLM as a discrete task.

---

## 📋 How to Use This Guide

### For Manual Development
Work through each phase sequentially. Complete all tasks in a phase before moving to the next.

### For LLM-Assisted Development
Copy the **"LLM Prompt Template"** from each phase and give it to an LLM (Claude, GPT-4, etc.) along with relevant context files.

**Example workflow:**
```bash
# Give this to your LLM:
"I'm building SentimentEdge. Here's the context from BLUEPRINT.md: [paste relevant sections]

Now complete Phase 1:
[paste Phase 1 LLM Prompt Template]
"
```

---

## Phase Overview

| Phase | Description | Est. Complexity | Files Created |
|-------|-------------|-----------------|---------------|
| **Phase 1** | Project setup & infrastructure | Low | 8 files |
| **Phase 2** | Reddit data ingestion | Low | 3 files |
| **Phase 3** | News data ingestion | Low | 2 files |
| **Phase 4** | Market data ingestion | Medium | 3 files |
| **Phase 5** | Sentiment analysis service | Medium | 4 files |
| **Phase 6** | Preprocessing & ticker extraction | Medium | 3 files |
| **Phase 7** | Database setup | Medium | 5 files |
| **Phase 8** | Signal generation engine | High | 4 files |
| **Phase 9** | Risk management | Medium | 2 files |
| **Phase 10** | Alpaca trading execution | High | 3 files |
| **Phase 11** | API Gateway | Medium | 6 files |
| **Phase 12** | Frontend dashboard | High | 15 files |
| **Phase 13** | Monitoring & observability | Medium | 4 files |
| **Phase 14** | Testing suite | Medium | 10 files |
| **Phase 15** | CI/CD pipeline | Low | 2 files |
| **Phase 16** | Documentation & polish | Low | 3 files |

---

# Phase 1: Project Setup & Infrastructure

## Goals
- Set up project directory structure
- Create Docker Compose configuration
- Initialize databases (PostgreSQL/TimescaleDB, Redis)
- Create environment configuration

## Tasks

### 1.1 Create Directory Structure
```bash
mkdir -p services/{ingestion,sentiment,trader,api}
mkdir -p frontend/src/{components,hooks,utils}
mkdir -p database/{migrations,seeds}
mkdir -p monitoring
mkdir -p tests/{unit,integration,e2e}
mkdir -p docs
```

### 1.2 Create `docker-compose.yml`

**File:** `/docker-compose.yml`

```yaml
version: '3.8'

services:
  # Database: TimescaleDB (PostgreSQL with time-series extension)
  postgres:
    image: timescale/timescaledb:latest-pg15
    container_name: sentimentedge-postgres
    environment:
      POSTGRES_DB: sentimentedge
      POSTGRES_USER: trader
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trader -d sentimentedge"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache & Message Queue: Redis
  redis:
    image: redis:7-alpine
    container_name: sentimentedge-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # Ingestion Service
  ingestion:
    build:
      context: ./services/ingestion
      dockerfile: Dockerfile
    container_name: sentimentedge-ingestion
    environment:
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDDIT_CLIENT_ID: ${REDDIT_CLIENT_ID}
      REDDIT_CLIENT_SECRET: ${REDDIT_CLIENT_SECRET}
      REDDIT_USER_AGENT: ${REDDIT_USER_AGENT:-SentimentEdge/1.0}
      NEWS_API_KEY: ${NEWS_API_KEY}
      ALPACA_API_KEY: ${ALPACA_API_KEY}
      ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  # Sentiment Analysis Service
  sentiment:
    build:
      context: ./services/sentiment
      dockerfile: Dockerfile
    container_name: sentimentedge-sentiment
    environment:
      REDIS_HOST: redis
      REDIS_PORT: 6379
      MODEL_NAME: ${SENTIMENT_MODEL:-ProsusAI/finbert}
      BATCH_SIZE: ${SENTIMENT_BATCH_SIZE:-20}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    # Uncomment for GPU support
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

  # Trading Service (Signal Generation + Execution)
  trader:
    build:
      context: ./services/trader
      dockerfile: Dockerfile
    container_name: sentimentedge-trader
    environment:
      REDIS_HOST: redis
      REDIS_PORT: 6379
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: sentimentedge
      POSTGRES_USER: trader
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      ALPACA_API_KEY: ${ALPACA_API_KEY}
      ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY}
      ALPACA_BASE_URL: ${ALPACA_BASE_URL:-https://paper-api.alpaca.markets}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped

  # API Gateway
  api:
    build:
      context: ./services/api
      dockerfile: Dockerfile
    container_name: sentimentedge-api
    environment:
      REDIS_HOST: redis
      REDIS_PORT: 6379
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: sentimentedge
      POSTGRES_USER: trader
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    ports:
      - "8000:8000"
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped

  # Frontend Dashboard
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: sentimentedge-frontend
    environment:
      REACT_APP_API_URL: ${REACT_APP_API_URL:-http://localhost:8000}
      REACT_APP_WS_URL: ${REACT_APP_WS_URL:-ws://localhost:8000/ws/live}
    ports:
      - "3000:3000"
    depends_on:
      - api
    restart: unless-stopped

  # Monitoring: Prometheus
  prometheus:
    image: prom/prometheus:latest
    container_name: sentimentedge-prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

  # Monitoring: Grafana
  grafana:
    image: grafana/grafana:latest
    container_name: sentimentedge-grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: 'false'
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3001:3000"
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  default:
    name: sentimentedge-network
```

### 1.3 Create `.env.example`

Already done in separate task below.

### 1.4 Create `.gitignore`

Already done in separate task below.

### 1.5 Create Database Initialization Script

**File:** `/database/init.sql`

```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create tables (basic structure, migrations will add more)
CREATE TABLE IF NOT EXISTS tickers (
    symbol TEXT PRIMARY KEY,
    company_name TEXT,
    sector TEXT,
    aliases TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    last_traded TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed some common tickers
INSERT INTO tickers (symbol, company_name, sector, aliases) VALUES
('AAPL', 'Apple Inc.', 'Technology', ARRAY['Apple', 'AAPL']),
('TSLA', 'Tesla Inc.', 'Automotive', ARRAY['Tesla', 'TSLA']),
('MSFT', 'Microsoft Corporation', 'Technology', ARRAY['Microsoft', 'MSFT']),
('GOOGL', 'Alphabet Inc.', 'Technology', ARRAY['Google', 'Alphabet', 'GOOGL']),
('AMZN', 'Amazon.com Inc.', 'E-commerce', ARRAY['Amazon', 'AMZN']),
('NVDA', 'NVIDIA Corporation', 'Technology', ARRAY['NVIDIA', 'Nvidia', 'NVDA']),
('META', 'Meta Platforms Inc.', 'Technology', ARRAY['Meta', 'Facebook', 'META']),
('AMD', 'Advanced Micro Devices', 'Technology', ARRAY['AMD']),
('GME', 'GameStop Corp.', 'Retail', ARRAY['GameStop', 'GME']),
('AMC', 'AMC Entertainment', 'Entertainment', ARRAY['AMC'])
ON CONFLICT (symbol) DO NOTHING;
```

## Verification

After completing Phase 1:

```bash
# Start just the databases
docker-compose up postgres redis -d

# Check they're running
docker-compose ps

# Connect to PostgreSQL
docker exec -it sentimentedge-postgres psql -U trader -d sentimentedge -c "SELECT * FROM tickers;"

# Connect to Redis
docker exec -it sentimentedge-redis redis-cli ping
```

Expected output:
- PostgreSQL returns list of tickers
- Redis returns "PONG"

## LLM Prompt Template for Phase 1

```
Task: Set up the infrastructure for SentimentEdge project

Context:
- This is a paper trading bot that analyzes sentiment and trades via Alpaca API
- Uses microservices architecture with Docker Compose
- Databases: TimescaleDB (PostgreSQL) and Redis
- See BLUEPRINT.md for full architecture

Requirements:
1. Create docker-compose.yml with services: postgres (timescaledb), redis, ingestion, sentiment, trader, api, frontend, prometheus, grafana
2. Create database/init.sql to initialize TimescaleDB and seed ticker data
3. Include health checks for all services
4. Use environment variables for all secrets
5. Create named volumes for data persistence

Acceptance Criteria:
- `docker-compose up postgres redis -d` starts successfully
- Can query tickers table and get seeded data
- Redis responds to PING command
- All services have health checks configured

Please provide the complete docker-compose.yml and init.sql files.
```

---

# Phase 2: Reddit Data Ingestion

## Goals
- Fetch posts from r/wallstreetbets and r/stocks
- Extract text content and metadata
- Push raw data to Redis streams
- Handle rate limiting and retries

## Tasks

### 2.1 Create Ingestion Service Structure

**File:** `/services/ingestion/requirements.txt`

```txt
praw==7.7.1
redis==5.0.1
requests==2.31.0
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0
```

**File:** `/services/ingestion/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Run the main script
CMD ["python", "-u", "main.py"]
```

### 2.2 Create Reddit Fetcher

**File:** `/services/ingestion/reddit_fetcher.py`

```python
import praw
import redis
import json
import time
import logging
from datetime import datetime
from typing import Optional
import hashlib

logger = logging.getLogger(__name__)


class RedditFetcher:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        redis_client: redis.Redis,
        subreddits: list[str] = None,
    ):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        self.redis = redis_client
        self.subreddits = subreddits or ["wallstreetbets", "stocks"]
        self.seen_ids = set()

    def fetch_posts(self, limit: int = 100) -> int:
        """Fetch recent posts from configured subreddits.

        Returns number of new posts fetched.
        """
        count = 0
        for subreddit_name in self.subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                for post in subreddit.new(limit=limit):
                    if self._process_post(post, subreddit_name):
                        count += 1
            except Exception as e:
                logger.error(f"Error fetching from r/{subreddit_name}: {e}")

        return count

    def _process_post(self, post, subreddit_name: str) -> bool:
        """Process a single post and push to Redis if new.

        Returns True if post was new and processed.
        """
        post_id = post.id

        # Check if already seen
        if post_id in self.seen_ids:
            return False

        # Create content hash for deduplication
        content = f"{post.title} {post.selftext}"
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # Check if content already exists (different post, same content)
        if self.redis.sismember("seen_content_hashes", content_hash):
            logger.debug(f"Duplicate content detected: {post_id}")
            return False

        # Extract data
        data = {
            "id": post_id,
            "source": "reddit",
            "subreddit": subreddit_name,
            "title": post.title,
            "text": post.selftext,
            "author": str(post.author),
            "score": post.score,
            "upvote_ratio": post.upvote_ratio,
            "num_comments": post.num_comments,
            "created_utc": post.created_utc,
            "url": post.url,
            "permalink": f"https://reddit.com{post.permalink}",
            "content_hash": content_hash,
            "fetched_at": datetime.utcnow().isoformat(),
        }

        # Push to Redis stream
        try:
            self.redis.xadd("raw:social", {"data": json.dumps(data)})
            self.seen_ids.add(post_id)
            self.redis.sadd("seen_content_hashes", content_hash)
            # Expire hashes after 24 hours
            self.redis.expire("seen_content_hashes", 86400)
            logger.info(f"Fetched post: r/{subreddit_name}/{post_id}")
            return True
        except Exception as e:
            logger.error(f"Error pushing to Redis: {e}")
            return False

    def run_forever(self, interval: int = 30):
        """Run fetcher in a loop.

        Args:
            interval: Seconds between fetch cycles
        """
        logger.info(f"Starting Reddit fetcher (subreddits: {self.subreddits})")
        while True:
            try:
                count = self.fetch_posts()
                logger.info(f"Fetched {count} new posts")
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Shutting down Reddit fetcher")
                break
            except Exception as e:
                logger.error(f"Error in fetch loop: {e}")
                time.sleep(interval)
```

### 2.3 Create Main Entry Point

**File:** `/services/ingestion/main.py`

```python
import os
import logging
import redis
from reddit_fetcher import RedditFetcher

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    # Get environment variables
    reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    reddit_user_agent = os.getenv("REDDIT_USER_AGENT", "SentimentEdge/1.0")

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))

    # Validate required env vars
    if not reddit_client_id or not reddit_client_secret:
        raise ValueError("Missing required Reddit API credentials")

    # Connect to Redis
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=False,  # Keep as bytes for streams
    )

    # Test connection
    redis_client.ping()
    logger.info("Connected to Redis")

    # Create and run fetcher
    fetcher = RedditFetcher(
        client_id=reddit_client_id,
        client_secret=reddit_client_secret,
        user_agent=reddit_user_agent,
        redis_client=redis_client,
        subreddits=["wallstreetbets", "stocks"],
    )

    fetcher.run_forever(interval=30)


if __name__ == "__main__":
    main()
```

## Verification

```bash
# Build and run ingestion service
docker-compose up ingestion --build

# In another terminal, monitor Redis stream
docker exec -it sentimentedge-redis redis-cli XLEN raw:social

# Read a message
docker exec -it sentimentedge-redis redis-cli XREAD COUNT 1 STREAMS raw:social 0
```

Expected: Should see posts being added to `raw:social` stream every 30 seconds.

## LLM Prompt Template for Phase 2

```
Task: Create Reddit data ingestion service for SentimentEdge

Context:
- Fetch posts from r/wallstreetbets and r/stocks using PRAW library
- Push raw posts to Redis stream "raw:social"
- Implement deduplication using content hashing
- Handle rate limiting (Reddit API: 60 req/min)

Requirements:
1. Create services/ingestion/reddit_fetcher.py with RedditFetcher class
2. Implement fetch_posts() method that:
   - Fetches new posts from configured subreddits
   - Deduplicates using post ID and content hash
   - Extracts: title, selftext, author, score, upvote_ratio, num_comments, created_utc
   - Pushes to Redis stream "raw:social" as JSON
3. Create main.py that runs fetcher in a loop (30s interval)
4. Create Dockerfile and requirements.txt
5. Add comprehensive logging

Acceptance Criteria:
- Service starts without errors
- Posts appear in Redis stream "raw:social"
- Duplicate posts are filtered out
- Handles API errors gracefully with retries

Please provide all three files: reddit_fetcher.py, main.py, Dockerfile, requirements.txt
```

---

# Phase 3: News Data Ingestion

## Goals
- Fetch financial news from NewsAPI
- Filter for business/finance articles
- Push to same Redis stream as Reddit data
- Handle free tier rate limits (100 req/day)

## Files to Create

1. `/services/ingestion/news_fetcher.py` - NewsAPI integration
2. Update `/services/ingestion/main.py` - Add news fetcher
3. Update `/services/ingestion/requirements.txt` - Add `newsapi-python`

## LLM Prompt Template for Phase 3

```
Task: Create News data ingestion for SentimentEdge

Context:
- Use NewsAPI (newsapi.org) to fetch financial news
- Free tier: 100 requests/day, so fetch every 15 minutes
- Push to same Redis stream "raw:social" for processing

Requirements:
1. Create services/ingestion/news_fetcher.py with NewsFetcher class
2. Implement:
   - Fetch articles from business/finance categories
   - Search for finance keywords: "stock", "market", "earnings", "trading"
   - Extract: title, description, content, source, publishedAt, url
   - Add source="news" field
   - Deduplicate by URL
3. Update main.py to run both Reddit and News fetchers concurrently
4. Respect rate limits: max 1 request per 15 minutes
5. Add comprehensive error handling

Acceptance Criteria:
- News articles appear in Redis stream "raw:social"
- Runs alongside Reddit fetcher without interference
- Respects 100 req/day limit
- Logs fetch statistics

Structure:
- NewsFetcher class similar to RedditFetcher
- fetch_articles() method
- run_forever() with 900s (15min) interval

Please provide news_fetcher.py and updated main.py
```

---

# Phase 4: Market Data Ingestion

## Goals
- Connect to Alpaca WebSocket for real-time bars
- Fetch OHLCV data for tracked tickers
- Push to Redis stream `raw:market`
- Handle reconnections

## Files to Create

1. `/services/ingestion/market_fetcher.py` - Alpaca WebSocket client
2. Update `/services/ingestion/main.py` - Add market fetcher
3. Update `/services/ingestion/requirements.txt` - Add `alpaca-py`

## LLM Prompt Template for Phase 4

```
Task: Create market data ingestion using Alpaca API

Context:
- Use Alpaca's WebSocket API for real-time market data
- Fetch 1-minute bars for tracked tickers
- Paper trading account provides free real-time data

Requirements:
1. Create services/ingestion/market_fetcher.py with MarketFetcher class
2. Implement:
   - WebSocket connection to Alpaca data feed
   - Subscribe to bars for multiple tickers (AAPL, TSLA, MSFT, etc.)
   - Extract: timestamp, open, high, low, close, volume, vwap
   - Push to Redis stream "raw:market"
3. Handle:
   - Connection errors and automatic reconnection
   - Authentication with API keys
   - Graceful shutdown
4. Update main.py to run market fetcher concurrently with others

Acceptance Criteria:
- WebSocket connects and streams market data
- 1-minute bars appear in Redis stream "raw:market"
- Auto-reconnects on disconnect
- Only fetches data during market hours

Library: Use alpaca-py (official Python library)

Please provide market_fetcher.py and updated main.py
```

---

# Phase 5: Sentiment Analysis Service

## Goals
- Load FinBERT model from HuggingFace
- Consume from `raw:social` Redis stream
- Analyze sentiment for each post
- Push results to `processed:sentiment` stream

## Files to Create

1. `/services/sentiment/analyzer.py` - FinBERT inference
2. `/services/sentiment/main.py` - Service entry point
3. `/services/sentiment/Dockerfile`
4. `/services/sentiment/requirements.txt`

## LLM Prompt Template for Phase 5

```
Task: Create sentiment analysis service using FinBERT

Context:
- Use ProsusAI/finbert model from HuggingFace
- Process posts from Redis stream "raw:social"
- Output sentiment scores to stream "processed:sentiment"

Requirements:
1. Create services/sentiment/analyzer.py with SentimentAnalyzer class
2. Implement:
   - Load FinBERT model (ProsusAI/finbert)
   - Batch processing (10-50 texts for efficiency)
   - Preprocess text (remove URLs, mentions, clean)
   - Inference: return positive/negative/neutral probabilities
   - Convert to score (-1 to +1): positive_prob - negative_prob
3. Create main.py that:
   - Consumes from "raw:social" Redis stream
   - Processes in batches
   - Pushes results to "processed:sentiment" stream
   - Handles CUDA/CPU automatically
4. Include comprehensive logging (batch size, inference time)

Acceptance Criteria:
- Model loads successfully
- Processes posts from raw:social
- Outputs scored posts to processed:sentiment
- Logs inference latency (target <100ms per text on CPU)

Dependencies: transformers, torch, redis, pydantic

Please provide analyzer.py, main.py, Dockerfile, requirements.txt
```

---

# Phase 6: Preprocessing & Ticker Extraction

## Goals
- Extract ticker symbols from text ($AAPL, "Apple", etc.)
- Map company names to symbols using NER
- Clean and normalize text
- Add as preprocessing step before sentiment

## Files to Create

1. `/services/sentiment/preprocessor.py` - Text preprocessing & ticker extraction
2. `/services/sentiment/ticker_mapper.py` - Company name → ticker mapping
3. Update `/services/sentiment/main.py` - Add preprocessing step

## LLM Prompt Template for Phase 6

```
Task: Create text preprocessing and ticker extraction

Context:
- Extract ticker symbols from social media posts
- Map company names (eg "Apple") to tickers (eg "AAPL")
- Clean text for better sentiment analysis

Requirements:
1. Create preprocessor.py with TextPreprocessor class:
   - Remove URLs, mentions (@user), hashtags (keep text)
   - Lowercase, remove extra whitespace
   - Keep emojis (sentiment indicators)

2. Create ticker_mapper.py with TickerMapper class:
   - Extract cashtags: $AAPL, $TSLA using regex
   - Use spaCy NER to find company names (ORG entities)
   - Query PostgreSQL tickers table for mapping
   - Fuzzy matching for partial names
   - Return list of unique ticker symbols per post

3. Update main.py to:
   - First run preprocessing
   - Extract tickers
   - Run sentiment on cleaned text
   - Include tickers in output

Acceptance Criteria:
- Correctly extracts $AAPL from "$AAPL to the moon"
- Maps "Apple" to AAPL using NER + database lookup
- Cleans text while preserving sentiment
- Handles posts with multiple tickers

Dependencies: spacy, fuzzywuzzy, sqlalchemy

Please provide preprocessor.py, ticker_mapper.py, and updated main.py
```

---

# Phase 7: Database Setup (TimescaleDB Tables & Migrations)

## Goals
- Create all required database tables
- Set up TimescaleDB hypertables
- Create indexes for performance
- Add database migration system

## Files to Create

1. `/database/migrations/001_create_tables.sql`
2. `/database/migrations/002_create_hypertables.sql`
3. `/database/migrations/003_create_indexes.sql`
4. `/database/seeds/tickers.sql` (expand ticker list)
5. Update `/database/init.sql` to run migrations

## LLM Prompt Template for Phase 7

```
Task: Create complete database schema for SentimentEdge

Context:
- Use TimescaleDB for time-series data (sentiment, market bars)
- Use PostgreSQL for transactional data (trades, positions)
- See BLUEPRINT.md section "Data Models & Schemas" for table definitions

Requirements:
1. Create migration 001_create_tables.sql:
   - Tables: tickers, trades, positions, config
   - Include all columns from BLUEPRINT.md
   - Add created_at, updated_at timestamps
   - Add appropriate constraints (PKs, FKs, NOT NULL)

2. Create migration 002_create_hypertables.sql:
   - Tables: sentiment_ticks, market_bars, aggregated_signals
   - Convert to TimescaleDB hypertables (partitioned by time)
   - Set chunk interval to 1 day

3. Create migration 003_create_indexes.sql:
   - Index on (ticker, time DESC) for time-series tables
   - Index on trades(timestamp), positions(ticker)
   - Index on tickers(symbol), tickers(company_name)

4. Create seeds/tickers.sql:
   - Insert top 50 most-discussed stocks (FAANG, meme stocks, etc.)
   - Include company_name, sector, aliases

5. Update init.sql to run migrations in order

Acceptance Criteria:
- All tables created successfully
- Hypertables configured with 1-day chunks
- Indexes improve query performance
- Can query tables without errors

Please provide all migration files and updated init.sql
```

---

# Phase 8: Signal Generation Engine

## Goals
- Aggregate sentiment data into time windows (1min, 5min)
- Calculate metrics (avg_sentiment, mention_count, momentum)
- Implement trading logic (when to BUY/SELL)
- Generate Signal objects

## Files to Create

1. `/services/trader/aggregator.py` - Time-window aggregation
2. `/services/trader/signal_generator.py` - Trading logic
3. `/services/trader/config.yaml` - Strategy parameters
4. `/services/trader/main.py` - Service entry point

## LLM Prompt Template for Phase 8

```
Task: Create signal generation engine with trading logic

Context:
- Aggregate sentiment data into rolling windows (1min, 5min, 15min)
- Detect sentiment spikes and generate BUY signals
- Generate SELL signals based on profit targets/stop losses
- See BLUEPRINT.md section "Trading Strategy Logic" for details

Requirements:
1. Create aggregator.py with SentimentAggregator class:
   - Consume from "processed:sentiment" Redis stream
   - Group by ticker and time window
   - Calculate per window:
     * avg_sentiment (mean)
     * weighted_sentiment (weighted by upvotes/karma)
     * mention_count (number of posts)
     * sentiment_std (standard deviation)
     * sentiment_momentum (change from previous window)
   - Store in TimescaleDB sentiment_ticks table
   - Also store in Redis for real-time access

2. Create signal_generator.py with SignalGenerator class:
   - Load config from config.yaml (thresholds, limits)
   - Implement _should_buy() logic:
     * avg_sentiment > threshold (default 0.7)
     * mention_count > min_mentions (default 15)
     * sentiment_momentum > 2 * std_dev (spike detection)
     * market volume > 1.5x average
     * market hours only
     * not already in position
   - Implement _should_sell() logic:
     * PnL >= +3% (take profit)
     * PnL <= -2% (stop loss)
     * hold_time > 1 hour (time exit)
     * sentiment < 0.3 (reversal)
   - Return Signal dataclass with: ticker, action, confidence, reason, metadata

3. Create config.yaml with default parameters

4. Create main.py that:
   - Runs aggregator in background thread
   - Runs signal generator in main loop
   - Pushes signals to Redis stream "signals"
   - Logs all signals generated

Acceptance Criteria:
- Aggregates sentiment data into time windows
- Stores in TimescaleDB and Redis
- Generates BUY signals when conditions met
- Generates SELL signals for open positions
- All signals logged and pushed to Redis

Please provide aggregator.py, signal_generator.py, config.yaml, main.py
```

---

# Phase 9: Risk Management

## Goals
- Validate all trades before execution
- Enforce position limits, loss limits
- Implement kill switch for daily loss limit
- Calculate position sizes using risk rules

## Files to Create

1. `/services/trader/risk_manager.py` - Risk validation logic
2. Update `/services/trader/signal_generator.py` - Add risk checks

## LLM Prompt Template for Phase 9

```
Task: Create risk management system

Context:
- Validate every trade before execution
- Enforce limits: max positions, position size, daily loss
- Calculate safe position sizes
- See BLUEPRINT.md section "Trading Strategy Logic" -> "Risk Management"

Requirements:
1. Create risk_manager.py with RiskManager class:
   - Load config (max_positions, position_size_pct, max_daily_loss_pct)
   - Implement validate_trade(signal, portfolio) -> (bool, str):
     * Check: position count < max_positions (default 5)
     * Check: buying power sufficient
     * Check: daily PnL > -5% (kill switch)
     * Check: sector exposure < 30%
     * Return (is_valid, reason)
   - Implement calculate_position_size(signal, portfolio) -> int:
     * Use position_size_pct of available cash (default 10%)
     * Divide by current stock price to get shares
     * Round down to integer shares
   - Implement get_sector_exposure(portfolio, sector) -> float
   - Implement should_halt_trading(portfolio) -> bool

2. Update signal_generator.py:
   - Add risk_manager as dependency
   - Validate all BUY signals before emitting
   - Log risk violations
   - Add risk_approved field to Signal dataclass

Acceptance Criteria:
- Blocks trades that exceed limits
- Logs risk violations clearly
- Calculates position sizes correctly
- Implements kill switch for daily loss

Please provide risk_manager.py and updated signal_generator.py
```

---

# Phase 10: Alpaca Trading Execution

## Goals
- Submit orders to Alpaca paper trading API
- Monitor order fills
- Track positions and P&L
- Handle errors and retries

## Files to Create

1. `/services/trader/executor.py` - Order execution logic
2. `/services/trader/portfolio.py` - Portfolio state management
3. Update `/services/trader/main.py` - Add execution

## LLM Prompt Template for Phase 10

```
Task: Create Alpaca trading execution engine

Context:
- Execute BUY/SELL orders on Alpaca paper trading
- Track positions and calculate P&L
- Store trades in database
- Handle order errors with retries

Requirements:
1. Create executor.py with OrderExecutor class:
   - Initialize Alpaca TradingClient (alpaca-py library)
   - Implement execute_signal(signal):
     * For BUY: submit market buy order
     * For SELL: close position (market sell)
     * Retry up to 3 times with exponential backoff
     * Log order submission and fills
     * Store in trades table
   - Implement monitor_orders():
     * Poll for order fills
     * Update positions table on fill
     * Calculate unrealized P&L
   - Implement place_stop_loss_take_profit(position):
     * Bracket orders for stop/profit targets
     * Use Alpaca bracket order API

2. Create portfolio.py with Portfolio class:
   - Load current positions from Alpaca
   - Calculate metrics:
     * total_value (cash + holdings)
     * daily_pnl (today's profit/loss)
     * daily_pnl_pct
     * positions (list of open positions)
   - Sync with database every minute
   - Provide get_position(ticker) method

3. Update main.py:
   - Add executor and portfolio
   - Consume from "signals" Redis stream
   - Execute approved signals
   - Monitor orders continuously

Acceptance Criteria:
- Successfully places orders on Alpaca paper account
- Tracks fills and updates positions
- Calculates P&L correctly
- Stores all trades in database
- Handles errors gracefully

Dependencies: alpaca-py, sqlalchemy, redis

Please provide executor.py, portfolio.py, and updated main.py
```

---

# Phase 11: API Gateway

## Goals
- Create REST API for frontend
- Implement WebSocket for real-time updates
- Provide endpoints for positions, trades, sentiment
- Add health checks and metrics

## Files to Create

1. `/services/api/main.py` - FastAPI application
2. `/services/api/routes/positions.py`
3. `/services/api/routes/trades.py`
4. `/services/api/routes/sentiment.py`
5. `/services/api/routes/performance.py`
6. `/services/api/websocket.py` - WebSocket handler

## LLM Prompt Template for Phase 11

```
Task: Create REST API and WebSocket server

Context:
- Provide data to frontend dashboard
- Real-time updates via WebSocket
- Query TimescaleDB and PostgreSQL
- See BLUEPRINT.md section "API Gateway"

Requirements:
1. Create main.py with FastAPI app:
   - CORS middleware (allow localhost:3000)
   - Database connection pool (SQLAlchemy)
   - Redis connection
   - Health check endpoint: GET /health
   - Metrics endpoint: GET /metrics (Prometheus format)

2. Create routes/positions.py:
   - GET /api/positions - Current open positions
   - Response: [{ticker, quantity, avg_entry_price, current_price, unrealized_pnl}]

3. Create routes/trades.py:
   - GET /api/trades?limit=50&ticker=AAPL - Trade history
   - Response: [{id, timestamp, ticker, action, quantity, price, pnl, reason}]

4. Create routes/sentiment.py:
   - GET /api/sentiment/:ticker?window=5min&limit=100
   - Returns time-series sentiment data
   - Response: [{time, avg_sentiment, mention_count, weighted_sentiment}]

5. Create routes/performance.py:
   - GET /api/performance - Overall stats
   - Response: {total_pnl, daily_pnl, win_rate, sharpe_ratio, max_drawdown, total_trades}

6. Create websocket.py:
   - WebSocket endpoint: /ws/live
   - Subscribe to Redis pub/sub channels
   - Emit updates when:
     * New position opened/closed
     * Trade executed
     * Signal generated
     * P&L changes
   - Format: {type: "position|trade|signal", data: {...}}

Acceptance Criteria:
- All endpoints return correct data
- WebSocket sends real-time updates
- Handles database errors gracefully
- CORS configured for frontend
- OpenAPI docs at /docs

Please provide all files
```

---

# Phase 12: Frontend Dashboard

## Goals
- Create React dashboard with live updates
- Display P&L chart, positions, signals
- WebSocket integration for real-time data
- Responsive design

## Files to Create

*Too many to list (15+ files). See detailed breakdown in full phase.*

## LLM Prompt Template for Phase 12

```
Task: Create React dashboard for SentimentEdge

Context:
- Real-time trading dashboard
- Display P&L, positions, trades, sentiment
- WebSocket for live updates
- Uses Recharts for visualization

Requirements:
1. Create React app with TypeScript
2. Components:
   - PnLChart: Line chart of equity curve over time
   - PositionsTable: Current holdings with live P&L
   - TradesTable: Recent trade history
   - SentimentChart: Per-ticker sentiment trends
   - SignalsFeed: Live feed of trading signals
3. Hooks:
   - useWebSocket: Manage WebSocket connection
   - useAPI: Fetch data from REST API
4. Features:
   - Auto-reconnect WebSocket on disconnect
   - Update charts in real-time
   - Dark mode
   - Responsive (mobile-friendly)

Tech Stack:
- React + TypeScript
- Recharts for charts
- TanStack Query for data fetching
- Tailwind CSS for styling
- WebSocket for real-time

Acceptance Criteria:
- Dashboard loads and displays data
- Charts update in real-time via WebSocket
- All API calls handled correctly
- Responsive on mobile
- Dark mode works

This is a large task - start with basic structure and we'll iterate.

Please provide:
1. package.json
2. src/App.tsx (main layout)
3. src/components/PnLChart.tsx
4. src/hooks/useWebSocket.ts
```

---

*Remaining phases (13-16) follow similar structure...*

---

# Quick Reference: Phase Checklist

Use this to track progress:

- [ ] Phase 1: Project setup & infrastructure
- [ ] Phase 2: Reddit data ingestion
- [ ] Phase 3: News data ingestion
- [ ] Phase 4: Market data ingestion
- [ ] Phase 5: Sentiment analysis service
- [ ] Phase 6: Preprocessing & ticker extraction
- [ ] Phase 7: Database setup
- [ ] Phase 8: Signal generation engine
- [ ] Phase 9: Risk management
- [ ] Phase 10: Alpaca trading execution
- [ ] Phase 11: API Gateway
- [ ] Phase 12: Frontend dashboard
- [ ] Phase 13: Monitoring & observability
- [ ] Phase 14: Testing suite
- [ ] Phase 15: CI/CD pipeline
- [ ] Phase 16: Documentation & polish

---

# Tips for LLM-Assisted Development

1. **Always provide context:** Include relevant sections from BLUEPRINT.md
2. **One phase at a time:** Complete and test before moving on
3. **Verify each phase:** Use the verification steps
4. **Iterate:** LLMs might not get it perfect first try
5. **Test incrementally:** Don't wait until the end to test

**Example workflow:**
```bash
# After LLM provides Phase 2 code
docker-compose up ingestion --build
# Verify it works
# Move to Phase 3
```

---

**Need help?** Refer to BLUEPRINT.md for architectural details and README.md for setup instructions.
