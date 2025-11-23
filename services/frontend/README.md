# SentimentEdge Frontend

React + TypeScript dashboard for monitoring the SentimentEdge algorithmic trading system.

## Features

- **Real-time Updates**: WebSocket connection for live signal feeds and performance metrics
- **P&L Visualization**: Cumulative profit/loss chart showing equity curve
- **Position Monitoring**: Live view of all open positions with unrealized P&L
- **Trade History**: Complete trade log with realized P&L
- **Sentiment Analysis**: Time-series charts showing sentiment trends for any ticker
- **Responsive Design**: Dark mode UI optimized for trading dashboards

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **Recharts** - Data visualization
- **TanStack Query** - Data fetching and caching
- **Axios** - HTTP client

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Environment Variables

Create a `.env` file based on `.env.example`:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/live
```

## Components

- **PnLChart**: Displays cumulative profit/loss over time
- **PositionsTable**: Shows all open positions with real-time P&L
- **TradesTable**: Complete trade history with filters
- **SentimentChart**: Multi-ticker sentiment analysis with time windows
- **SignalsFeed**: Real-time trading signals as they're generated

## Docker

```bash
# Build image
docker build -t sentimentedge-frontend .

# Run container
docker run -p 3000:80 sentimentedge-frontend
```

## API Integration

The frontend connects to the FastAPI backend at `/api` endpoints:

- `GET /api/positions` - Current positions
- `GET /api/trades` - Trade history
- `GET /api/sentiment/{ticker}` - Sentiment data
- `GET /api/performance` - Performance metrics
- `WS /ws/live` - Real-time updates

## WebSocket Events

The dashboard subscribes to these WebSocket events:

```typescript
{
  type: 'signal' | 'performance' | 'position_update',
  data: Signal | Performance | Position
}
```

## Performance

- Automatic reconnection with exponential backoff
- Query caching with TanStack Query
- Efficient re-renders with React optimizations
- Nginx-served static assets with compression
