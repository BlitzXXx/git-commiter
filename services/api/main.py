#!/usr/bin/env python3
"""
API Gateway Service - Placeholder
This will be implemented in Phase 11
"""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SentimentEdge API",
    description="Real-time market sentiment trading bot API",
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "SentimentEdge API (placeholder mode)",
        "version": "0.1.0"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "api"
    }

@app.get("/api/positions")
async def get_positions():
    logger.info("Positions endpoint called (placeholder)")
    return {"positions": [], "message": "Will be implemented in Phase 11"}

@app.get("/api/trades")
async def get_trades(limit: int = 50):
    logger.info(f"Trades endpoint called with limit={limit} (placeholder)")
    return {"trades": [], "message": "Will be implemented in Phase 11"}

@app.get("/api/performance")
async def get_performance():
    logger.info("Performance endpoint called (placeholder)")
    return {
        "total_pnl": 0.0,
        "daily_pnl": 0.0,
        "win_rate": 0.0,
        "message": "Will be implemented in Phase 11"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
