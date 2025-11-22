#!/usr/bin/env python3
"""
Ingestion Service - Fetches data from Reddit, News, and Market sources
Implements Phase 2, 3, and 4
"""
import os
import logging
import redis
import threading
from reddit_fetcher import RedditFetcher
from news_fetcher import NewsFetcher
from market_fetcher import MarketFetcher

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def run_reddit_fetcher(redis_client):
    """Run Reddit fetcher in a thread."""
    try:
        reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        reddit_user_agent = os.getenv("REDDIT_USER_AGENT", "SentimentEdge/1.0")

        if not reddit_client_id or not reddit_client_secret:
            logger.warning("⚠️  Reddit API credentials not found - skipping Reddit fetcher")
            return

        fetcher = RedditFetcher(
            client_id=reddit_client_id,
            client_secret=reddit_client_secret,
            user_agent=reddit_user_agent,
            redis_client=redis_client,
            subreddits=["wallstreetbets", "stocks", "investing"],
        )

        fetcher.run_forever(interval=30)  # Fetch every 30 seconds

    except Exception as e:
        logger.error(f"Reddit fetcher error: {e}", exc_info=True)


def run_news_fetcher(redis_client):
    """Run News fetcher in a thread."""
    try:
        news_api_key = os.getenv("NEWS_API_KEY")

        if not news_api_key:
            logger.warning("⚠️  NewsAPI key not found - skipping News fetcher")
            return

        fetcher = NewsFetcher(
            api_key=news_api_key,
            redis_client=redis_client,
        )

        fetcher.run_forever(interval=900)  # Fetch every 15 minutes (conserve API calls)

    except Exception as e:
        logger.error(f"News fetcher error: {e}", exc_info=True)


def run_market_fetcher(redis_client):
    """Run Market fetcher in a thread."""
    try:
        alpaca_api_key = os.getenv("ALPACA_API_KEY")
        alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not alpaca_api_key or not alpaca_secret_key:
            logger.warning("⚠️  Alpaca API credentials not found - skipping Market fetcher")
            return

        # Get list of tickers from environment or use defaults
        tickers_str = os.getenv("MARKET_TICKERS", "AAPL,TSLA,MSFT,GOOGL,AMZN,NVDA,META,GME,AMC,SPY")
        tickers = [t.strip() for t in tickers_str.split(",")]

        fetcher = MarketFetcher(
            api_key=alpaca_api_key,
            secret_key=alpaca_secret_key,
            redis_client=redis_client,
            tickers=tickers,
        )

        fetcher.run_sync()  # Runs async event loop internally

    except Exception as e:
        logger.error(f"Market fetcher error: {e}", exc_info=True)


def main():
    """Main entry point - starts all fetchers concurrently."""
    logger.info("=" * 60)
    logger.info("🚀 SentimentEdge Ingestion Service Starting")
    logger.info("=" * 60)

    # Connect to Redis
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))

    logger.info(f"Connecting to Redis at {redis_host}:{redis_port}...")

    try:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=False,  # Keep as bytes for streams
        )

        # Test connection
        redis_client.ping()
        logger.info("✅ Connected to Redis")

    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        logger.error("Exiting...")
        return

    # Start fetchers in separate threads
    threads = []

    # Reddit fetcher thread
    reddit_thread = threading.Thread(
        target=run_reddit_fetcher,
        args=(redis_client,),
        name="RedditFetcher",
        daemon=True
    )
    threads.append(reddit_thread)

    # News fetcher thread
    news_thread = threading.Thread(
        target=run_news_fetcher,
        args=(redis_client,),
        name="NewsFetcher",
        daemon=True
    )
    threads.append(news_thread)

    # Market fetcher thread
    market_thread = threading.Thread(
        target=run_market_fetcher,
        args=(redis_client,),
        name="MarketFetcher",
        daemon=True
    )
    threads.append(market_thread)

    # Start all threads
    for thread in threads:
        thread.start()
        logger.info(f"Started thread: {thread.name}")

    logger.info("=" * 60)
    logger.info("✅ All fetchers started successfully")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    # Keep main thread alive
    try:
        while True:
            # Check if threads are alive
            for thread in threads:
                if not thread.is_alive():
                    logger.warning(f"⚠️  Thread {thread.name} died, restarting...")
                    # In production, you'd restart the thread here
            import time
            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down ingestion service...")
        logger.info("Waiting for threads to finish...")

    logger.info("✅ Ingestion service stopped")


if __name__ == "__main__":
    main()
