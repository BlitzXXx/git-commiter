#!/usr/bin/env python3
"""
Market Data Fetcher - Fetches real-time market data from Alpaca
"""
import redis
import json
import time
import logging
from datetime import datetime
from alpaca.data.live import StockDataStream
from alpaca.data.models import Bar

logger = logging.getLogger(__name__)


class MarketFetcher:
    """Fetches real-time market data from Alpaca and pushes to Redis streams."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        redis_client: redis.Redis,
        tickers: list[str] = None,
    ):
        """Initialize Market fetcher.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            redis_client: Redis client instance
            tickers: List of ticker symbols to monitor
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.redis = redis_client
        self.tickers = tickers or [
            "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN",
            "NVDA", "META", "GME", "AMC", "SPY"
        ]

        # Initialize Alpaca WebSocket client
        self.stream = StockDataStream(api_key, secret_key)

        logger.info(f"Initialized Market fetcher for {len(self.tickers)} tickers")

    async def handle_bar(self, bar: Bar):
        """Handle incoming bar data from Alpaca.

        Args:
            bar: Bar object from Alpaca
        """
        try:
            # Extract data
            data = {
                "ticker": bar.symbol,
                "time": bar.timestamp.isoformat(),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": int(bar.volume),
                "vwap": float(bar.vwap) if bar.vwap else None,
                "trade_count": bar.trade_count if hasattr(bar, 'trade_count') else None,
                "fetched_at": datetime.utcnow().isoformat(),
            }

            # Push to Redis stream
            self.redis.xadd("raw:market", {"data": json.dumps(data)})

            logger.debug(f"📊 {bar.symbol}: ${bar.close:.2f} (vol: {bar.volume:,})")

        except Exception as e:
            logger.error(f"Error processing bar: {e}", exc_info=True)

    async def run_forever(self):
        """Run market data stream forever."""
        logger.info(f"🚀 Starting Market data stream")
        logger.info(f"Subscribing to {len(self.tickers)} tickers: {', '.join(self.tickers[:5])}...")

        try:
            # Subscribe to bars (1-minute aggregates)
            for ticker in self.tickers:
                self.stream.subscribe_bars(self.handle_bar, ticker)

            logger.info("✅ Subscribed to market data stream")
            logger.info("Waiting for bars...")

            # Run the stream
            await self.stream.run()

        except KeyboardInterrupt:
            logger.info("🛑 Shutting down Market fetcher")
        except Exception as e:
            logger.error(f"Error in market stream: {e}", exc_info=True)
            raise

    def run_sync(self):
        """Synchronous wrapper for running the async stream."""
        import asyncio

        try:
            asyncio.run(self.run_forever())
        except KeyboardInterrupt:
            logger.info("Market fetcher stopped by user")
        except Exception as e:
            logger.error(f"Market fetcher error: {e}", exc_info=True)
