#!/usr/bin/env python3
"""
Sentiment Analysis Service - Processes social posts with FinBERT
Implements Phase 5 and 6
"""
import os
import json
import time
import logging
import redis
from analyzer import SentimentAnalyzer
from preprocessor import TextPreprocessor
from ticker_mapper import TickerMapper

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def build_db_url():
    """Build PostgreSQL connection URL from environment variables."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "sentimentedge")
    user = os.getenv("POSTGRES_USER", "trader")
    password = os.getenv("POSTGRES_PASSWORD", "changeme")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def process_post(post_data: dict, analyzer: SentimentAnalyzer, preprocessor: TextPreprocessor,
                  ticker_mapper: TickerMapper) -> dict:
    """Process a single post: preprocess, extract tickers, analyze sentiment.

    Args:
        post_data: Post data dict
        analyzer: Sentiment analyzer instance
        preprocessor: Text preprocessor instance
        ticker_mapper: Ticker mapper instance

    Returns:
        Processed post with sentiment and tickers
    """
    # Combine title and text
    title = post_data.get("title", "")
    text = post_data.get("text", "")
    full_text = f"{title} {text}".strip()

    # Preprocess
    clean_text = preprocessor.process(full_text)

    # Extract tickers
    tickers = ticker_mapper.extract(full_text)  # Use original text for ticker extraction

    # Analyze sentiment
    sentiment = analyzer.analyze(clean_text)

    # Build result
    result = {
        **post_data,  # Keep original data
        "clean_text": clean_text,
        "tickers": tickers,
        "sentiment": sentiment,
        "processed_at": time.time(),
    }

    return result


def main():
    """Main entry point - processes posts from Redis stream."""
    logger.info("=" * 60)
    logger.info("🚀 SentimentEdge Sentiment Analysis Service Starting")
    logger.info("=" * 60)

    # Connect to Redis
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))

    logger.info(f"Connecting to Redis at {redis_host}:{redis_port}...")

    try:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=False,
        )

        redis_client.ping()
        logger.info("✅ Connected to Redis")

    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        return

    # Connect to database
    db_url = build_db_url()
    logger.info("Connecting to database...")

    # Initialize components
    try:
        model_name = os.getenv("MODEL_NAME", "ProsusAI/finbert")
        batch_size = int(os.getenv("BATCH_SIZE", "20"))

        logger.info("Initializing components...")
        analyzer = SentimentAnalyzer(model_name=model_name, batch_size=batch_size)
        preprocessor = TextPreprocessor()
        ticker_mapper = TickerMapper(db_url=db_url)

        logger.info("✅ All components initialized")

    except Exception as e:
        logger.error(f"❌ Failed to initialize components: {e}", exc_info=True)
        return

    logger.info("=" * 60)
    logger.info("✅ Sentiment service ready")
    logger.info("Listening for posts on stream 'raw:social'...")
    logger.info("=" * 60)

    # Track last processed ID
    last_id = "0"
    posts_processed = 0
    posts_with_tickers = 0

    try:
        while True:
            # Read from stream (blocking with timeout)
            try:
                streams = redis_client.xread(
                    {"raw:social": last_id},
                    count=batch_size,
                    block=5000  # 5 second timeout
                )

                if not streams:
                    # No new messages
                    continue

                # Process messages
                for stream_name, messages in streams:
                    for message_id, message_data in messages:
                        try:
                            # Parse post data
                            post_json = message_data.get(b"data")
                            if not post_json:
                                continue

                            post_data = json.loads(post_json.decode("utf-8"))

                            # Process post
                            result = process_post(post_data, analyzer, preprocessor, ticker_mapper)

                            # Only push if tickers were found
                            if result["tickers"]:
                                # Push to processed stream
                                redis_client.xadd(
                                    "processed:sentiment",
                                    {"data": json.dumps(result)}
                                )

                                posts_with_tickers += 1

                                logger.info(
                                    f"✅ Processed: {result.get('source', 'unknown')} | "
                                    f"Tickers: {', '.join(result['tickers'])} | "
                                    f"Sentiment: {result['sentiment']['score']:.2f}"
                                )

                            posts_processed += 1

                            # Update last ID
                            last_id = message_id

                        except Exception as e:
                            logger.error(f"Error processing message: {e}", exc_info=True)
                            # Continue processing other messages
                            continue

                # Log stats periodically
                if posts_processed % 100 == 0 and posts_processed > 0:
                    logger.info(
                        f"📊 Stats: Processed {posts_processed} posts, "
                        f"{posts_with_tickers} with tickers "
                        f"({posts_with_tickers/posts_processed*100:.1f}%)"
                    )

            except redis.exceptions.ResponseError as e:
                logger.error(f"Redis error: {e}")
                time.sleep(5)
                continue

    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down sentiment service...")

    logger.info(f"✅ Processed {posts_processed} total posts")
    logger.info("✅ Sentiment service stopped")


if __name__ == "__main__":
    main()
