#!/usr/bin/env python3
"""
Sentiment Aggregator - Aggregates sentiment data into time windows
"""
import json
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import statistics

logger = logging.getLogger(__name__)


class SentimentAggregator:
    """Aggregates sentiment data into time windows and stores in database."""

    def __init__(self, db_url: str, redis_client: redis.Redis, windows: List[str] = None):
        """Initialize sentiment aggregator.

        Args:
            db_url: PostgreSQL connection URL
            redis_client: Redis client instance
            windows: List of window sizes (e.g., ['1min', '5min'])
        """
        self.db_engine = create_engine(db_url, poolclass=NullPool)
        self.redis = redis_client
        self.windows = windows or ['1min', '5min', '15min']

        # In-memory buffers for each ticker
        self.buffers = defaultdict(list)  # ticker -> list of sentiment datapoints

        logger.info(f"Initialized SentimentAggregator with windows: {self.windows}")

    def _window_to_seconds(self, window: str) -> int:
        """Convert window string to seconds.

        Args:
            window: Window size string (e.g., '1min', '5min')

        Returns:
            Number of seconds
        """
        if window.endswith('min'):
            return int(window[:-3]) * 60
        elif window.endswith('s'):
            return int(window[:-1])
        elif window.endswith('h'):
            return int(window[:-1]) * 3600
        else:
            return 60  # default to 1 minute

    def add_datapoint(self, ticker: str, sentiment_score: float, timestamp: float, metadata: dict = None):
        """Add a sentiment datapoint to the buffer.

        Args:
            ticker: Stock ticker symbol
            sentiment_score: Sentiment score (-1 to +1)
            timestamp: Unix timestamp
            metadata: Additional metadata (e.g., upvotes, karma)
        """
        datapoint = {
            'ticker': ticker,
            'score': sentiment_score,
            'timestamp': timestamp,
            'metadata': metadata or {}
        }

        self.buffers[ticker].append(datapoint)

    def aggregate_window(self, ticker: str, window: str, current_time: float) -> Dict:
        """Aggregate sentiment for a specific ticker and window.

        Args:
            ticker: Stock ticker symbol
            window: Window size (e.g., '5min')
            current_time: Current Unix timestamp

        Returns:
            Aggregated metrics dict
        """
        window_seconds = self._window_to_seconds(window)
        cutoff_time = current_time - window_seconds

        # Get datapoints within window
        datapoints = [
            dp for dp in self.buffers[ticker]
            if dp['timestamp'] >= cutoff_time
        ]

        if not datapoints:
            return None

        # Calculate metrics
        scores = [dp['score'] for dp in datapoints]

        # Basic stats
        avg_sentiment = statistics.mean(scores)
        sentiment_std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        mention_count = len(datapoints)

        # Weighted sentiment (by upvotes/karma if available)
        weighted_scores = []
        for dp in datapoints:
            weight = dp['metadata'].get('score', 1) or 1  # upvotes/score
            weighted_scores.extend([dp['score']] * weight)

        weighted_sentiment = statistics.mean(weighted_scores) if weighted_scores else avg_sentiment

        # Calculate momentum (change from previous window)
        prev_cutoff = cutoff_time - window_seconds
        prev_datapoints = [
            dp for dp in self.buffers[ticker]
            if prev_cutoff <= dp['timestamp'] < cutoff_time
        ]

        if prev_datapoints:
            prev_scores = [dp['score'] for dp in prev_datapoints]
            prev_avg = statistics.mean(prev_scores)
            sentiment_momentum = avg_sentiment - prev_avg
        else:
            sentiment_momentum = 0.0

        return {
            'ticker': ticker,
            'window_size': window,
            'avg_sentiment': avg_sentiment,
            'weighted_sentiment': weighted_sentiment,
            'mention_count': mention_count,
            'sentiment_std': sentiment_std,
            'sentiment_momentum': sentiment_momentum,
            'timestamp': datetime.fromtimestamp(current_time).isoformat()
        }

    def store_aggregates(self, aggregates: List[Dict]):
        """Store aggregates in TimescaleDB.

        Args:
            aggregates: List of aggregate dicts
        """
        if not aggregates:
            return

        try:
            with self.db_engine.connect() as conn:
                for agg in aggregates:
                    # Insert into sentiment_ticks
                    conn.execute(
                        text("""
                            INSERT INTO sentiment_ticks
                            (time, ticker, avg_sentiment, weighted_sentiment, mention_count, sentiment_std, source)
                            VALUES (:time, :ticker, :avg_sentiment, :weighted_sentiment, :mention_count, :sentiment_std, 'aggregated')
                        """),
                        {
                            'time': agg['timestamp'],
                            'ticker': agg['ticker'],
                            'avg_sentiment': agg['avg_sentiment'],
                            'weighted_sentiment': agg['weighted_sentiment'],
                            'mention_count': agg['mention_count'],
                            'sentiment_std': agg['sentiment_std']
                        }
                    )

                    # Also store in aggregated_signals table
                    conn.execute(
                        text("""
                            INSERT INTO aggregated_signals
                            (time, ticker, window_size, avg_sentiment, sentiment_momentum, mention_volume)
                            VALUES (:time, :ticker, :window_size, :avg_sentiment, :sentiment_momentum, :mention_volume)
                        """),
                        {
                            'time': agg['timestamp'],
                            'ticker': agg['ticker'],
                            'window_size': agg['window_size'],
                            'avg_sentiment': agg['avg_sentiment'],
                            'sentiment_momentum': agg['sentiment_momentum'],
                            'mention_volume': agg['mention_count']
                        }
                    )

                conn.commit()

        except Exception as e:
            logger.error(f"Error storing aggregates: {e}", exc_info=True)

    def cache_in_redis(self, aggregates: List[Dict]):
        """Cache aggregates in Redis for fast access.

        Args:
            aggregates: List of aggregate dicts
        """
        try:
            for agg in aggregates:
                key = f"sentiment:{agg['ticker']}:{agg['window_size']}"
                self.redis.setex(
                    key,
                    300,  # 5 minute TTL
                    json.dumps(agg)
                )

        except Exception as e:
            logger.error(f"Error caching in Redis: {e}", exc_info=True)

    def cleanup_old_datapoints(self, max_age_seconds: int = 3600):
        """Remove old datapoints from memory to prevent memory leaks.

        Args:
            max_age_seconds: Maximum age to keep in buffer (default: 1 hour)
        """
        current_time = time.time()
        cutoff_time = current_time - max_age_seconds

        for ticker in list(self.buffers.keys()):
            self.buffers[ticker] = [
                dp for dp in self.buffers[ticker]
                if dp['timestamp'] >= cutoff_time
            ]

            # Remove empty buffers
            if not self.buffers[ticker]:
                del self.buffers[ticker]

    def run_aggregation_cycle(self):
        """Run one aggregation cycle for all tickers and windows."""
        current_time = time.time()
        all_aggregates = []

        # Aggregate for each ticker
        for ticker in self.buffers.keys():
            for window in self.windows:
                agg = self.aggregate_window(ticker, window, current_time)
                if agg:
                    all_aggregates.append(agg)

        # Store in database
        if all_aggregates:
            self.store_aggregates(all_aggregates)
            self.cache_in_redis(all_aggregates)

            logger.debug(f"Stored {len(all_aggregates)} aggregates")

        # Cleanup old datapoints
        self.cleanup_old_datapoints()

        return len(all_aggregates)
