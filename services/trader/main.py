#!/usr/bin/env python3
"""
Trading Service - Complete Trading Pipeline
Implements Phase 8: Signal generation
Implements Phase 9: Risk management
Implements Phase 10: Order execution
"""
import os
import json
import time
import logging
import threading
import redis
import yaml
from datetime import datetime
from aggregator import SentimentAggregator
from signal_generator import SignalGenerator
from risk_manager import RiskManager
from executor import OrderExecutor
from portfolio import Portfolio

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


def load_config():
    """Load strategy configuration from config.yaml."""
    config_path = os.getenv("CONFIG_PATH", "/app/config.yaml")

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"✅ Loaded config from {config_path}")
        return config
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {
            'strategy': {
                'sentiment_threshold': 0.7,
                'min_mentions': 15,
                'volume_multiplier': 1.5,
                'take_profit_pct': 0.03,
                'stop_loss_pct': 0.02,
                'max_hold_seconds': 3600
            }
        }
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}


def run_aggregator(redis_client, db_url, config):
    """Run sentiment aggregator in a loop.

    Args:
        redis_client: Redis client instance
        db_url: Database connection URL
        config: Strategy configuration
    """
    logger.info("Starting aggregator thread...")

    strategy = config.get('strategy', {})
    windows = strategy.get('aggregation_windows', ['1min', '5min', '15min'])

    aggregator = SentimentAggregator(
        db_url=db_url,
        redis_client=redis_client,
        windows=windows
    )

    last_id = "0"

    try:
        while True:
            # Read from processed:sentiment stream
            try:
                streams = redis_client.xread(
                    {"processed:sentiment": last_id},
                    count=100,
                    block=5000  # 5 second timeout
                )

                if not streams:
                    # No new messages, run aggregation cycle
                    aggregator.run_aggregation_cycle()
                    continue

                # Process new sentiment data
                for stream_name, messages in streams:
                    for message_id, message_data in messages:
                        try:
                            # Parse sentiment data
                            post_json = message_data.get(b"data")
                            if not post_json:
                                continue

                            post_data = json.loads(post_json.decode("utf-8"))

                            # Extract info
                            tickers = post_data.get('tickers', [])
                            sentiment = post_data.get('sentiment', {})
                            score = sentiment.get('score', 0.0)
                            timestamp = post_data.get('processed_at', time.time())

                            # Add to aggregator for each ticker mentioned
                            for ticker in tickers:
                                metadata = {
                                    'score': post_data.get('score', 1),  # Reddit upvotes
                                    'source': post_data.get('source', 'unknown')
                                }

                                aggregator.add_datapoint(
                                    ticker=ticker,
                                    sentiment_score=score,
                                    timestamp=timestamp,
                                    metadata=metadata
                                )

                            last_id = message_id

                        except Exception as e:
                            logger.error(f"Error processing message in aggregator: {e}")
                            continue

                # Run aggregation cycle after processing batch
                count = aggregator.run_aggregation_cycle()
                if count > 0:
                    logger.debug(f"Aggregated {count} windows")

            except redis.exceptions.ResponseError as e:
                logger.error(f"Redis error in aggregator: {e}")
                time.sleep(5)

    except Exception as e:
        logger.error(f"Aggregator error: {e}", exc_info=True)


def run_signal_generator(redis_client, db_url, config):
    """Run signal generator in a loop.

    Args:
        redis_client: Redis client instance
        db_url: Database connection URL
        config: Strategy configuration
    """
    logger.info("Starting signal generator thread...")

    generator = SignalGenerator(
        db_url=db_url,
        redis_client=redis_client,
        config=config
    )

    signals_generated = 0

    try:
        while True:
            # Get list of tickers that have recent sentiment data
            try:
                # Query tickers with recent aggregated data
                tickers_to_check = set()

                # Get tickers from Redis cache
                for key in redis_client.scan_iter("sentiment:*:5min"):
                    # Extract ticker from key (sentiment:TICKER:5min)
                    parts = key.decode('utf-8').split(':')
                    if len(parts) == 3:
                        tickers_to_check.add(parts[1])

                logger.debug(f"Checking {len(tickers_to_check)} tickers for signals")

                # Generate signals for each ticker
                for ticker in tickers_to_check:
                    try:
                        signal = generator.generate(ticker)

                        if signal:
                            # Push signal to Redis stream
                            redis_client.xadd(
                                "signals",
                                {"data": json.dumps(signal.to_dict())}
                            )

                            signals_generated += 1

                            logger.info(
                                f"🚨 SIGNAL: {signal.action} {signal.ticker} | "
                                f"Confidence: {signal.confidence:.2f} | "
                                f"Reason: {signal.reason}"
                            )

                    except Exception as e:
                        logger.error(f"Error generating signal for {ticker}: {e}")
                        continue

                # Log stats periodically
                if signals_generated > 0 and signals_generated % 10 == 0:
                    logger.info(f"📊 Total signals generated: {signals_generated}")

                # Sleep between cycles
                time.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Error in signal generation loop: {e}")
                time.sleep(10)

    except Exception as e:
        logger.error(f"Signal generator error: {e}", exc_info=True)


def run_executor(redis_client, db_url, config):
    """Run order executor in a loop.

    Args:
        redis_client: Redis client instance
        db_url: Database connection URL
        config: Strategy configuration
    """
    logger.info("Starting executor thread...")

    # Get Alpaca credentials
    alpaca_api_key = os.getenv("ALPACA_API_KEY")
    alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY")
    trading_mode = os.getenv("TRADING_MODE", "paper")

    if not alpaca_api_key or not alpaca_secret_key:
        logger.error("❌ Alpaca API credentials not found - executor cannot start")
        return

    # Initialize components
    risk_manager = RiskManager(db_url=db_url, config=config)
    executor = OrderExecutor(
        api_key=alpaca_api_key,
        secret_key=alpaca_secret_key,
        db_url=db_url,
        paper=(trading_mode == "paper")
    )
    portfolio = Portfolio(
        api_key=alpaca_api_key,
        secret_key=alpaca_secret_key,
        db_url=db_url,
        paper=(trading_mode == "paper")
    )

    # Sync portfolio
    portfolio.sync_with_alpaca()

    last_id = "0"
    signals_processed = 0
    trades_executed = 0

    try:
        while True:
            # Read from signals stream
            try:
                streams = redis_client.xread(
                    {"signals": last_id},
                    count=10,
                    block=5000  # 5 second timeout
                )

                if not streams:
                    # Update position prices periodically
                    portfolio.update_position_prices()
                    continue

                # Process signals
                for stream_name, messages in streams:
                    for message_id, message_data in messages:
                        try:
                            # Parse signal
                            signal_json = message_data.get(b"data")
                            if not signal_json:
                                continue

                            signal_data = json.loads(signal_json.decode("utf-8"))

                            # Reconstruct Signal object
                            from signal_generator import Signal
                            signal = Signal(
                                timestamp=datetime.fromisoformat(signal_data['timestamp']),
                                ticker=signal_data['ticker'],
                                action=signal_data['action'],
                                confidence=signal_data['confidence'],
                                reason=signal_data['reason'],
                                metadata=signal_data.get('metadata', {})
                            )

                            signals_processed += 1

                            # Get portfolio state
                            portfolio_state = risk_manager.get_portfolio_state()

                            # Validate with risk manager
                            is_valid, reason = risk_manager.validate_trade(signal, portfolio_state)

                            if not is_valid:
                                logger.info(f"❌ Signal rejected: {signal.action} {signal.ticker} - {reason}")
                                last_id = message_id
                                continue

                            logger.info(f"✅ Signal approved: {signal.action} {signal.ticker}")

                            # Execute trade
                            if signal.action == 'BUY':
                                # Calculate position size
                                current_price = signal.metadata.get('price', 0.0)
                                if not current_price:
                                    logger.warning(f"No price in signal metadata for {signal.ticker}")
                                    last_id = message_id
                                    continue

                                quantity = risk_manager.calculate_position_size(
                                    signal,
                                    portfolio_state,
                                    current_price
                                )

                                result = executor.execute_signal(signal, quantity)

                                if result:
                                    trades_executed += 1
                                    logger.info(
                                        f"💰 EXECUTED: BUY {result['quantity']} {result['ticker']} "
                                        f"@ ${result['price']:.2f}"
                                    )

                            elif signal.action == 'SELL':
                                result = executor.execute_signal(signal, 0)  # Quantity determined from position

                                if result:
                                    trades_executed += 1
                                    logger.info(
                                        f"💰 EXECUTED: SELL {result['quantity']} {result['ticker']} "
                                        f"@ ${result['price']:.2f} | P&L: ${result.get('pnl', 0):.2f}"
                                    )

                            last_id = message_id

                        except Exception as e:
                            logger.error(f"Error processing signal: {e}", exc_info=True)
                            continue

                # Log stats periodically
                if signals_processed % 10 == 0 and signals_processed > 0:
                    logger.info(
                        f"📊 Executor stats: {signals_processed} signals processed, "
                        f"{trades_executed} trades executed"
                    )

            except redis.exceptions.ResponseError as e:
                logger.error(f"Redis error in executor: {e}")
                time.sleep(5)

    except Exception as e:
        logger.error(f"Executor error: {e}", exc_info=True)


def main():
    """Main entry point - starts aggregator and signal generator."""
    logger.info("=" * 60)
    logger.info("🚀 SentimentEdge Trading Service Starting")
    logger.info("=" * 60)

    # Load configuration
    config = load_config()

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

    # Build database URL
    db_url = build_db_url()

    # Start aggregator thread
    aggregator_thread = threading.Thread(
        target=run_aggregator,
        args=(redis_client, db_url, config),
        name="Aggregator",
        daemon=True
    )
    aggregator_thread.start()
    logger.info("Started aggregator thread")

    # Start signal generator thread
    signal_thread = threading.Thread(
        target=run_signal_generator,
        args=(redis_client, db_url, config),
        name="SignalGenerator",
        daemon=True
    )
    signal_thread.start()
    logger.info("Started signal generator thread")

    # Start executor thread
    executor_thread = threading.Thread(
        target=run_executor,
        args=(redis_client, db_url, config),
        name="Executor",
        daemon=True
    )
    executor_thread.start()
    logger.info("Started executor thread")

    logger.info("=" * 60)
    logger.info("✅ Trading service started successfully")
    logger.info("Phase 8: Signal generation ✅")
    logger.info("Phase 9: Risk management ✅")
    logger.info("Phase 10: Order execution ✅")
    logger.info("=" * 60)

    # Keep main thread alive
    try:
        while True:
            # Check thread health
            if not aggregator_thread.is_alive():
                logger.error("❌ Aggregator thread died!")
            if not signal_thread.is_alive():
                logger.error("❌ Signal generator thread died!")
            if not executor_thread.is_alive():
                logger.error("❌ Executor thread died!")

            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down trading service...")

    logger.info("✅ Trading service stopped")


if __name__ == "__main__":
    main()
