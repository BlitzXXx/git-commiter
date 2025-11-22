# SentimentEdge - Real-Time Market Sentiment Trading Bot

> **Paper Trading Bot** that analyzes social media sentiment and executes trades on Alpaca's paper trading platform.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

---

## 🎯 What This Does

**SentimentEdge** monitors Reddit and financial news, analyzes sentiment using AI, and automatically trades stocks on Alpaca's **free paper trading** platform.

### Key Features

✅ **Real-time sentiment analysis** from r/wallstreetbets, r/stocks, and financial news
✅ **AI-powered trading signals** using FinBERT (finance-tuned BERT model)
✅ **Automated paper trading** via Alpaca API (zero risk, real market data)
✅ **Live dashboard** to watch trades happen in real-time
✅ **Risk management** with position limits, stop-loss, and take-profit
✅ **Production-ready** with Docker, monitoring, and observability

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- **Docker & Docker Compose** installed
- **Python 3.11+** (if running locally without Docker)
- **API Keys** (all free):
  - [Alpaca Paper Trading](https://alpaca.markets) - Free paper trading account
  - [Reddit API](https://www.reddit.com/prefs/apps) - Create a "script" app
  - [NewsAPI](https://newsapi.org) - Free tier (100 requests/day)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd sentiment-trader
```

### Step 2: Set Up API Keys

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API keys
nano .env  # or use your favorite editor
```

Add your keys:
```env
# Alpaca Paper Trading (get from https://app.alpaca.markets/paper/dashboard/overview)
ALPACA_API_KEY=your_paper_key_here
ALPACA_SECRET_KEY=your_paper_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Reddit (create app at https://www.reddit.com/prefs/apps)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=SentimentEdge/1.0

# NewsAPI (get from https://newsapi.org)
NEWS_API_KEY=your_newsapi_key
```

### Step 3: Start the System

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

### Step 4: Open the Dashboard

Visit **http://localhost:3000** to see:
- Live P&L chart
- Current positions
- Trading signals
- Sentiment trends

---

## 📊 How It Works

```
Reddit/News Posts → Sentiment Analysis (FinBERT) → Signal Generation → Paper Trade on Alpaca
                                                                              ↓
                                                        Live Dashboard ← WebSocket Updates
```

### Trading Strategy

The bot looks for **sentiment spikes** + **volume confirmation**:

**BUY when:**
- Sentiment score > 0.7 (strong positive)
- 15+ mentions in 5 minutes
- Market volume > 1.5x average
- Not already holding the stock

**SELL when:**
- Profit target hit (+3%)
- Stop loss hit (-2%)
- Held for 1 hour (time exit)
- Sentiment turns negative

### Risk Management

- Max 5 positions at once
- Max 10% of capital per position
- Daily loss limit: 5%
- All trades have automatic stop-loss

---

## 🗂️ Project Structure

```
sentiment-trader/
├── services/
│   ├── ingestion/          # Fetch Reddit, news, market data
│   ├── sentiment/          # FinBERT sentiment analysis
│   ├── trader/             # Signal generation & order execution
│   └── api/                # REST API + WebSocket server
├── frontend/               # React dashboard
├── database/               # SQL schemas and migrations
├── monitoring/             # Prometheus + Grafana configs
├── tests/                  # Unit and integration tests
├── docker-compose.yml      # All services orchestrated
├── .env.example            # Environment template
├── README.md               # This file
├── BLUEPRINT.md            # Detailed architecture
└── PHASES.md               # Development roadmap
```

---

## 🛠️ Development Guide

### Running Individual Services

```bash
# Ingestion service only
cd services/ingestion
pip install -r requirements.txt
python reddit_fetcher.py

# Sentiment service
cd services/sentiment
pip install -r requirements.txt
python analyzer.py

# Run tests
pytest tests/ -v

# Lint code
ruff check .
black --check .
mypy .
```

### Modifying the Strategy

Edit `services/trader/config.yaml`:

```yaml
strategy:
  sentiment_threshold: 0.7    # How positive (0-1)
  min_mentions: 15            # Min posts in 5min
  take_profit_pct: 0.03       # 3% profit target
  stop_loss_pct: 0.02         # 2% stop loss
  max_hold_seconds: 3600      # 1 hour max
```

Restart the trader service:
```bash
docker-compose restart trader
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f trader

# Last 100 lines
docker-compose logs --tail=100 trader
```

### Monitoring

- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090
- **API Docs**: http://localhost:8000/docs

---

## 📈 API Endpoints

### REST API

```bash
# Get current positions
GET http://localhost:8000/api/positions

# Get trade history
GET http://localhost:8000/api/trades?limit=50

# Get sentiment for a ticker
GET http://localhost:8000/api/sentiment/AAPL

# Get performance metrics
GET http://localhost:8000/api/performance

# Update strategy config
POST http://localhost:8000/api/config
{
  "sentiment_threshold": 0.8,
  "max_positions": 3
}
```

### WebSocket (Real-time Updates)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/live');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
  // { type: 'position', ticker: 'AAPL', pnl: 150.50 }
  // { type: 'signal', ticker: 'TSLA', action: 'BUY', reason: '...' }
  // { type: 'trade', ticker: 'MSFT', action: 'SELL', price: 350.25 }
};
```

---

## 🧪 Testing

### Run All Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires services running)
pytest tests/integration/ -v

# End-to-end tests
pytest tests/e2e/ -v --slow

# With coverage
pytest --cov=services --cov-report=html
```

### Test Data

Use the mock data generator:

```bash
python tests/generate_mock_data.py --posts 100 --tickers AAPL,TSLA,MSFT
```

This injects test posts into Redis for testing the pipeline.

---

## 🐛 Troubleshooting

### Service won't start

```bash
# Check logs
docker-compose logs <service-name>

# Rebuild from scratch
docker-compose down -v
docker-compose up --build
```

### "Invalid API key" errors

- Verify your `.env` file has correct keys
- Ensure you're using **paper trading** keys from Alpaca (not live keys)
- Reddit: Make sure app type is "script" not "web app"

### No trades happening

- Check Reddit is returning posts: `docker-compose logs ingestion`
- Verify sentiment scores are being calculated: `docker-compose logs sentiment`
- Lower the `sentiment_threshold` in config if signals are too rare
- Check market hours (bot only trades 9:30 AM - 4:00 PM ET)

### Dashboard not updating

- Check WebSocket connection in browser console
- Verify API service is running: `curl http://localhost:8000/health`
- Check CORS settings in `services/api/main.py`

### Database errors

```bash
# Reset database
docker-compose down -v
docker-compose up postgres -d
# Wait 10 seconds for init
docker-compose up --build
```

---

## 📚 Learn More

- **[BLUEPRINT.md](BLUEPRINT.md)** - Complete architecture and technical details
- **[PHASES.md](PHASES.md)** - Step-by-step development guide
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - File-by-file descriptions

### Key Technologies

- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern Python web framework
- **[FinBERT](https://huggingface.co/ProsusAI/finbert)** - Financial sentiment model
- **[Alpaca API](https://alpaca.markets/docs/)** - Paper trading platform
- **[TimescaleDB](https://www.timescale.com/)** - Time-series database
- **[React](https://react.dev/)** - Frontend framework

---

## 🎓 Educational Use

This project is designed for:
- Learning algorithmic trading concepts
- Understanding ML in production
- Demonstrating full-stack skills
- Portfolio/resume projects

**⚠️ Not Financial Advice**
- This is for educational purposes only
- Paper trading only - no real money
- Past performance doesn't predict future results
- Always do your own research

---

## 📋 Development Phases

This project is designed to be built in phases. See **[PHASES.md](PHASES.md)** for detailed instructions.

### Quick Overview

1. **Phase 1** - Core data ingestion (Reddit, news, market data)
2. **Phase 2** - Sentiment analysis with FinBERT
3. **Phase 3** - Signal generation and risk management
4. **Phase 4** - Alpaca integration and paper trading
5. **Phase 5** - Dashboard and visualization
6. **Phase 6** - Monitoring and observability
7. **Phase 7** - Testing and CI/CD
8. **Phase 8** - Documentation and polish

Each phase can be completed independently and tested before moving on.

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Development Setup

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run linters
ruff check .
black .
mypy .

# Run tests
pytest
```

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🙏 Acknowledgments

- **Alpaca Markets** for free paper trading API
- **HuggingFace** for FinBERT model
- **Reddit** for public API access
- **NewsAPI** for news data

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/sentiment-trader/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/sentiment-trader/discussions)
- **Documentation**: See `BLUEPRINT.md` and `PHASES.md`

---

**Happy Trading! 📈**

*Remember: This is a learning project. Always use paper trading. Never risk real money without understanding the risks.*
