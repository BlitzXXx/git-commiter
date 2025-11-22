# Phase 1 Verification Checklist

## ✅ Phase 1 Complete: Project Setup & Infrastructure

All files for Phase 1 have been created. Use this checklist to verify everything works on your local machine.

---

## Prerequisites

Ensure you have installed:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux)
- Docker Compose (included with Docker Desktop)

Verify installation:
```bash
docker --version
docker compose version
```

Expected output:
```
Docker version 24.x.x or higher
Docker Compose version v2.x.x or higher
```

---

## Step 1: Start Core Infrastructure (PostgreSQL + Redis)

```bash
# From project root
docker compose up -d postgres redis
```

**Expected output:**
```
[+] Running 2/2
 ✔ Container sentimentedge-postgres  Started
 ✔ Container sentimentedge-redis     Started
```

### Verify PostgreSQL

```bash
# Check PostgreSQL is running
docker compose ps postgres

# View PostgreSQL logs
docker compose logs postgres

# Connect to PostgreSQL
docker exec -it sentimentedge-postgres psql -U trader -d sentimentedge
```

**In PostgreSQL shell, run:**
```sql
-- List tables
\dt

-- Check hypertables
SELECT * FROM timescaledb_information.hypertables;

-- Check seeded tickers
SELECT symbol, company_name, sector FROM tickers LIMIT 10;

-- Exit
\q
```

**Expected results:**
- Tables: tickers, trades, positions, config, sentiment_ticks, market_bars, aggregated_signals
- Hypertables: 3 (sentiment_ticks, market_bars, aggregated_signals)
- Tickers: 25 rows (AAPL, TSLA, MSFT, etc.)

### Verify Redis

```bash
# Test Redis connection
docker exec -it sentimentedge-redis redis-cli ping
```

**Expected output:**
```
PONG
```

```bash
# Check Redis info
docker exec -it sentimentedge-redis redis-cli INFO server
```

---

## Step 2: Start Application Services

```bash
# Start all services
docker compose up -d
```

**Expected output:**
```
[+] Running 9/9
 ✔ Container sentimentedge-postgres     Running
 ✔ Container sentimentedge-redis        Running
 ✔ Container sentimentedge-ingestion    Started
 ✔ Container sentimentedge-sentiment    Started
 ✔ Container sentimentedge-trader       Started
 ✔ Container sentimentedge-api          Started
 ✔ Container sentimentedge-frontend     Started
 ✔ Container sentimentedge-prometheus   Started
 ✔ Container sentimentedge-grafana      Started
```

### Check Service Status

```bash
docker compose ps
```

**Expected:** All services should show "Up" status.

---

## Step 3: Verify Service Health

### API Gateway

```bash
curl http://localhost:8000/health
```

**Expected output:**
```json
{"status":"healthy","service":"api"}
```

Visit in browser: http://localhost:8000/docs

**Expected:** FastAPI interactive documentation (Swagger UI)

### Frontend Dashboard

Visit in browser: http://localhost:3000

**Expected:** React app showing "SentimentEdge" with placeholder message

### Prometheus

Visit in browser: http://localhost:9090

**Expected:** Prometheus UI
- Go to Status → Targets
- Should see configured targets (may be down since services are placeholders)

### Grafana

Visit in browser: http://localhost:3001

**Expected:** Grafana login page
- Username: `admin`
- Password: `admin` (or what you set in `.env`)

After login:
- Go to Configuration → Data Sources
- Should see "Prometheus" configured and connected

---

## Step 4: Check Logs

```bash
# View all logs
docker compose logs

# View specific service logs
docker compose logs ingestion
docker compose logs sentiment
docker compose logs trader
docker compose logs api
docker compose logs frontend

# Follow logs in real-time
docker compose logs -f api
```

**Expected in placeholder services:**
- Ingestion: "Ingestion service running... (waiting for implementation)"
- Sentiment: "Sentiment service running... (waiting for implementation)"
- Trader: "Trading service running... (waiting for implementation)"
- API: Uvicorn running on 0.0.0.0:8000

---

## Step 5: Verify Network Communication

```bash
# From ingestion container, ping Redis
docker exec sentimentedge-ingestion ping -c 2 redis

# From trader container, connect to PostgreSQL
docker exec sentimentedge-trader sh -c 'apt-get update && apt-get install -y postgresql-client && psql -h postgres -U trader -d sentimentedge -c "SELECT COUNT(*) FROM tickers;"'
```

**Expected:** Successful pings and database query returns 25

---

## Step 6: Test Redis Streams (Manual)

```bash
# Connect to Redis
docker exec -it sentimentedge-redis redis-cli

# Create test stream
XADD raw:social * data '{"ticker":"AAPL","text":"Apple stock is great!"}'

# Read from stream
XREAD COUNT 1 STREAMS raw:social 0

# Check stream length
XLEN raw:social

# Exit
exit
```

---

## Common Issues & Solutions

### Issue: Port already in use
```
Error: bind: address already in use
```

**Solution:** Change port in `docker-compose.yml` or stop conflicting service:
```bash
# Find what's using port 5432
lsof -i :5432

# Kill process or change POSTGRES port in docker-compose.yml to 5433:5432
```

### Issue: Services won't start
```
ERROR: Service 'xxx' failed to build
```

**Solution:** Check Docker is running and has enough resources:
```bash
# Check Docker status
docker info

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### Issue: PostgreSQL init.sql didn't run
```
Table 'tickers' doesn't exist
```

**Solution:** Remove volume and recreate:
```bash
docker compose down -v  # -v removes volumes
docker compose up -d postgres
```

---

## Cleanup

```bash
# Stop all services
docker compose down

# Stop and remove volumes (CAUTION: deletes all data)
docker compose down -v

# Remove specific service
docker compose rm -s -v postgres
```

---

## ✅ Phase 1 Complete Checklist

- [ ] PostgreSQL running with TimescaleDB extension enabled
- [ ] Database tables created (7 tables including hypertables)
- [ ] Tickers seeded (25 symbols)
- [ ] Redis running and responding to PING
- [ ] API accessible at http://localhost:8000/health
- [ ] Frontend accessible at http://localhost:3000
- [ ] Prometheus accessible at http://localhost:9090
- [ ] Grafana accessible at http://localhost:3001
- [ ] All service containers running
- [ ] No error logs in services

---

## Next Steps

Once Phase 1 is verified:

1. **Move to Phase 2:** Reddit data ingestion
   - See `PHASES.md` for detailed instructions
   - Or give Phase 2 prompt to an LLM

2. **Get API keys** (if you haven't already):
   - Alpaca: https://alpaca.markets
   - Reddit: https://www.reddit.com/prefs/apps
   - NewsAPI: https://newsapi.org

3. **Copy .env.example to .env**:
   ```bash
   cp .env.example .env
   nano .env  # Add your API keys
   ```

---

## Questions?

- Check `README.md` for overview
- Check `BLUEPRINT.md` for architecture details
- Check `PROJECT_STRUCTURE.md` for file explanations

**Phase 1 infrastructure is ready! 🚀**
