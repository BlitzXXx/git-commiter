#!/usr/bin/env python3
"""
API Gateway Service - REST API + WebSocket
Implements Phase 11: API Gateway
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import redis.asyncio as aioredis

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="SentimentEdge API",
    description="Real-time market sentiment trading bot API",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
def get_db_url():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "sentimentedge")
    user = os.getenv("POSTGRES_USER", "trader")
    password = os.getenv("POSTGRES_PASSWORD", "changeme")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"

db_engine = create_engine(get_db_url(), poolclass=NullPool)

# Redis connection for WebSocket updates
redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_client = await aioredis.from_url(f"redis://{redis_host}:{redis_port}", decode_responses=True)
    logger.info(f"✅ Connected to Redis at {redis_host}:{redis_port}")

@app.on_event("shutdown")
async def shutdown_event():
    if redis_client:
        await redis_client.close()


# ============================================
# REST API Endpoints
# ============================================

@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "SentimentEdge API - Real-time Market Sentiment Trading",
        "version": "1.0.0",
        "endpoints": {
            "positions": "/api/positions",
            "trades": "/api/trades",
            "sentiment": "/api/sentiment/{ticker}",
            "performance": "/api/performance",
            "websocket": "/ws/live"
        }
    }

@app.get("/health")
async def health():
    # Check database connection
    try:
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_healthy = False

    # Check Redis connection
    try:
        await redis_client.ping()
        redis_healthy = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_healthy = False

    status = "healthy" if (db_healthy and redis_healthy) else "degraded"

    return {
        "status": status,
        "service": "api",
        "database": "healthy" if db_healthy else "unhealthy",
        "redis": "healthy" if redis_healthy else "unhealthy"
    }


@app.get("/api/positions")
async def get_positions():
    """Get all current positions."""
    try:
        with db_engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT ticker, quantity, avg_entry_price, current_price,
                           unrealized_pnl, entry_timestamp, last_updated
                    FROM positions
                    ORDER BY entry_timestamp DESC
                """)
            )

            positions = []
            for row in result:
                positions.append({
                    "ticker": row[0],
                    "quantity": int(row[1]),
                    "avg_entry_price": float(row[2]),
                    "current_price": float(row[3]) if row[3] else 0.0,
                    "unrealized_pnl": float(row[4]) if row[4] else 0.0,
                    "unrealized_pnl_pct": ((float(row[3]) - float(row[2])) / float(row[2]) * 100) if row[3] and row[2] else 0.0,
                    "entry_timestamp": row[5].isoformat() if row[5] else None,
                    "last_updated": row[6].isoformat() if row[6] else None
                })

            return {"positions": positions, "count": len(positions)}

    except Exception as e:
        logger.error(f"Error getting positions: {e}", exc_info=True)
        return {"positions": [], "count": 0, "error": str(e)}


@app.get("/api/trades")
async def get_trades(limit: int = Query(50, ge=1, le=500), ticker: Optional[str] = None):
    """Get trade history."""
    try:
        with db_engine.connect() as conn:
            if ticker:
                result = conn.execute(
                    text("""
                        SELECT id, timestamp, ticker, action, quantity, price,
                               total_value, signal_reason, sentiment_score
                        FROM trades
                        WHERE ticker = :ticker
                        ORDER BY timestamp DESC
                        LIMIT :limit
                    """),
                    {"ticker": ticker, "limit": limit}
                )
            else:
                result = conn.execute(
                    text("""
                        SELECT id, timestamp, ticker, action, quantity, price,
                               total_value, signal_reason, sentiment_score
                        FROM trades
                        ORDER BY timestamp DESC
                        LIMIT :limit
                    """),
                    {"limit": limit}
                )

            trades = []
            for row in result:
                trades.append({
                    "id": row[0],
                    "timestamp": row[1].isoformat() if row[1] else None,
                    "ticker": row[2],
                    "action": row[3],
                    "quantity": int(row[4]),
                    "price": float(row[5]),
                    "total_value": float(row[6]),
                    "signal_reason": row[7],
                    "sentiment_score": float(row[8]) if row[8] else None
                })

            return {"trades": trades, "count": len(trades)}

    except Exception as e:
        logger.error(f"Error getting trades: {e}", exc_info=True)
        return {"trades": [], "count": 0, "error": str(e)}


@app.get("/api/sentiment/{ticker}")
async def get_sentiment(ticker: str, window: str = "5min", limit: int = Query(100, ge=1, le=1000)):
    """Get sentiment time-series for a ticker."""
    try:
        with db_engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT time, ticker, avg_sentiment, sentiment_momentum, mention_volume
                    FROM aggregated_signals
                    WHERE ticker = :ticker
                    AND window_size = :window
                    ORDER BY time DESC
                    LIMIT :limit
                """),
                {"ticker": ticker, "window": window, "limit": limit}
            )

            data_points = []
            for row in result:
                data_points.append({
                    "time": row[0].isoformat() if row[0] else None,
                    "ticker": row[1],
                    "avg_sentiment": float(row[2]) if row[2] else 0.0,
                    "sentiment_momentum": float(row[3]) if row[3] else 0.0,
                    "mention_volume": int(row[4]) if row[4] else 0
                })

            # Reverse to get chronological order
            data_points.reverse()

            return {"ticker": ticker, "window": window, "data": data_points, "count": len(data_points)}

    except Exception as e:
        logger.error(f"Error getting sentiment: {e}", exc_info=True)
        return {"ticker": ticker, "window": window, "data": [], "count": 0, "error": str(e)}


@app.get("/api/performance")
async def get_performance():
    """Get overall trading performance metrics."""
    try:
        with db_engine.connect() as conn:
            # Get total P&L
            result = conn.execute(
                text("""
                    SELECT
                        COALESCE(SUM(unrealized_pnl), 0) as total_unrealized_pnl,
                        COALESCE(SUM(realized_pnl), 0) as total_realized_pnl
                    FROM positions
                """)
            )
            row = result.fetchone()
            unrealized_pnl = float(row[0]) if row[0] else 0.0
            realized_pnl = float(row[1]) if row[1] else 0.0
            total_pnl = unrealized_pnl + realized_pnl

            # Get daily P&L
            result = conn.execute(
                text("""
                    SELECT COALESCE(SUM(
                        CASE
                            WHEN action = 'SELL' THEN total_value
                            WHEN action = 'BUY' THEN -total_value
                        END
                    ), 0) as daily_pnl
                    FROM trades
                    WHERE DATE(timestamp) = CURRENT_DATE
                """)
            )
            row = result.fetchone()
            daily_pnl = float(row[0]) if row[0] else 0.0

            # Get win rate
            result = conn.execute(
                text("""
                    WITH sell_trades AS (
                        SELECT ticker, price as sell_price, timestamp as sell_time
                        FROM trades
                        WHERE action = 'SELL'
                    ),
                    buy_trades AS (
                        SELECT ticker, price as buy_price, timestamp as buy_time
                        FROM trades
                        WHERE action = 'BUY'
                    ),
                    matched_trades AS (
                        SELECT
                            s.ticker,
                            b.buy_price,
                            s.sell_price,
                            (s.sell_price - b.buy_price) as pnl
                        FROM sell_trades s
                        JOIN buy_trades b ON s.ticker = b.ticker AND s.sell_time > b.buy_time
                    )
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades
                    FROM matched_trades
                """)
            )
            row = result.fetchone()
            total_trades = int(row[0]) if row[0] else 0
            winning_trades = int(row[1]) if row[1] else 0
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

            # Get trade count
            result = conn.execute(text("SELECT COUNT(*) FROM trades"))
            trade_count = result.scalar()

            # Starting capital
            starting_capital = 100000.0

            return {
                "total_pnl": total_pnl,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": realized_pnl,
                "daily_pnl": daily_pnl,
                "daily_pnl_pct": (daily_pnl / starting_capital * 100) if starting_capital > 0 else 0.0,
                "win_rate": win_rate,
                "total_trades": trade_count,
                "starting_capital": starting_capital,
                "current_value": starting_capital + total_pnl
            }

    except Exception as e:
        logger.error(f"Error getting performance: {e}", exc_info=True)
        return {
            "total_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "daily_pnl": 0.0,
            "daily_pnl_pct": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "starting_capital": 100000.0,
            "current_value": 100000.0,
            "error": str(e)
        }


# ============================================
# WebSocket Endpoint for Real-time Updates
# ============================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")

manager = ConnectionManager()


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Start Redis listener task
    listener_task = asyncio.create_task(redis_listener(websocket))

    try:
        while True:
            # Keep connection alive and receive messages from client
            data = await websocket.receive_text()
            logger.debug(f"Received from client: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        listener_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)
        listener_task.cancel()


async def redis_listener(websocket: WebSocket):
    """Listen to Redis streams and push updates to WebSocket client."""
    try:
        # Create a separate Redis client for this connection
        redis_url = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}"
        redis_conn = await aioredis.from_url(redis_url, decode_responses=False)

        last_signal_id = "0"
        last_trade_id = "$"  # Use $ to get only new messages

        while True:
            try:
                # Listen for new signals
                streams = await redis_conn.xread(
                    {"signals": last_signal_id},
                    count=10,
                    block=1000  # 1 second timeout
                )

                if streams:
                    for stream_name, messages in streams:
                        for message_id, message_data in messages:
                            signal_json = message_data.get(b"data")
                            if signal_json:
                                signal = json.loads(signal_json.decode("utf-8"))
                                await websocket.send_json({
                                    "type": "signal",
                                    "data": signal
                                })

                            last_signal_id = message_id.decode("utf-8")

                # Also periodically send position updates
                # (In production, you'd listen to a positions stream)
                await asyncio.sleep(5)

                # Send performance update
                performance = await get_performance()
                await websocket.send_json({
                    "type": "performance",
                    "data": performance
                })

            except Exception as e:
                logger.error(f"Error in Redis listener: {e}")
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Redis listener cancelled")
    finally:
        await redis_conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
