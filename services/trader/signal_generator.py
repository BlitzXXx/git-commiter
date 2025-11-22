#!/usr/bin/env python3
"""
Signal Generator - Generates BUY/SELL trading signals based on sentiment and market data
"""
import json
import logging
from datetime import datetime, time as dt_time
from typing import Dict, Optional
from dataclasses import dataclass
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Trading signal data class."""
    timestamp: datetime
    ticker: str
    action: str  # 'BUY' or 'SELL'
    confidence: float
    reason: str
    metadata: dict

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'ticker': self.ticker,
            'action': self.action,
            'confidence': self.confidence,
            'reason': self.reason,
            'metadata': self.metadata
        }


class SignalGenerator:
    """Generates trading signals based on sentiment and market conditions."""

    def __init__(self, db_url: str, redis_client: redis.Redis, config: dict):
        """Initialize signal generator.

        Args:
            db_url: PostgreSQL connection URL
            redis_client: Redis client instance
            config: Strategy configuration dict
        """
        self.db_engine = create_engine(db_url, poolclass=NullPool)
        self.redis = redis_client
        self.config = config

        # Extract thresholds from config
        strategy = config.get('strategy', {})
        self.sentiment_threshold = strategy.get('sentiment_threshold', 0.7)
        self.min_mentions = strategy.get('min_mentions', 15)
        self.volume_multiplier = strategy.get('volume_multiplier', 1.5)
        self.take_profit_pct = strategy.get('take_profit_pct', 0.03)
        self.stop_loss_pct = strategy.get('stop_loss_pct', 0.02)
        self.max_hold_seconds = strategy.get('max_hold_seconds', 3600)

        logger.info(f"Initialized SignalGenerator with thresholds: "
                   f"sentiment={self.sentiment_threshold}, mentions={self.min_mentions}")

    def _is_market_hours(self) -> bool:
        """Check if it's currently market hours (9:30 AM - 4:00 PM ET).

        Returns:
            True if market is open
        """
        now = datetime.utcnow()

        # Convert to ET (rough approximation - doesn't account for DST)
        et_hour = (now.hour - 5) % 24

        # Market hours: 9:30 AM - 4:00 PM ET (Mon-Fri)
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)

        current_time = dt_time(et_hour, now.minute)

        # Check day of week (0 = Monday, 6 = Sunday)
        is_weekday = now.weekday() < 5

        return is_weekday and market_open <= current_time <= market_close

    def _get_sentiment_data(self, ticker: str, window: str = '5min') -> Optional[Dict]:
        """Get aggregated sentiment data for a ticker.

        Args:
            ticker: Stock ticker symbol
            window: Time window size

        Returns:
            Sentiment data dict or None
        """
        try:
            # Try Redis cache first
            key = f"sentiment:{ticker}:{window}"
            cached = self.redis.get(key)

            if cached:
                return json.loads(cached)

            # Fall back to database
            with self.db_engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT avg_sentiment, sentiment_momentum, mention_volume, time
                        FROM aggregated_signals
                        WHERE ticker = :ticker
                        AND window_size = :window
                        ORDER BY time DESC
                        LIMIT 1
                    """),
                    {'ticker': ticker, 'window': window}
                )

                row = result.fetchone()
                if row:
                    return {
                        'avg_sentiment': float(row[0]),
                        'sentiment_momentum': float(row[1]),
                        'mention_count': int(row[2]),
                        'time': row[3]
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting sentiment data: {e}")
            return None

    def _get_market_data(self, ticker: str, bars: int = 20) -> Optional[Dict]:
        """Get recent market data for a ticker.

        Args:
            ticker: Stock ticker symbol
            bars: Number of recent bars to fetch

        Returns:
            Market data dict or None
        """
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT close, volume, time
                        FROM market_bars
                        WHERE ticker = :ticker
                        ORDER BY time DESC
                        LIMIT :limit
                    """),
                    {'ticker': ticker, 'limit': bars}
                )

                rows = result.fetchall()
                if not rows:
                    return None

                # Current (most recent) bar
                current = rows[0]

                # Calculate average volume
                volumes = [float(row[1]) for row in rows]
                avg_volume = sum(volumes) / len(volumes)

                return {
                    'close': float(current[0]),
                    'volume': float(current[1]),
                    'avg_volume': avg_volume,
                    'time': current[2]
                }

        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return None

    def _is_in_position(self, ticker: str) -> bool:
        """Check if we currently hold a position in this ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if in position
        """
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM positions WHERE ticker = :ticker"),
                    {'ticker': ticker}
                )
                count = result.scalar()
                return count > 0

        except Exception as e:
            logger.error(f"Error checking position: {e}")
            return False

    def _get_position(self, ticker: str) -> Optional[Dict]:
        """Get current position data for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Position data dict or None
        """
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT ticker, quantity, avg_entry_price, entry_timestamp
                        FROM positions
                        WHERE ticker = :ticker
                    """),
                    {'ticker': ticker}
                )

                row = result.fetchone()
                if row:
                    return {
                        'ticker': row[0],
                        'quantity': int(row[1]),
                        'avg_entry_price': float(row[2]),
                        'entry_timestamp': row[3]
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None

    def _should_buy(self, ticker: str, sentiment_data: Dict, market_data: Dict) -> tuple[bool, str]:
        """Determine if we should generate a BUY signal.

        Args:
            ticker: Stock ticker symbol
            sentiment_data: Aggregated sentiment data
            market_data: Market bar data

        Returns:
            (should_buy, reason)
        """
        # Check all conditions
        checks = []

        # 1. Sentiment above threshold
        if sentiment_data['avg_sentiment'] > self.sentiment_threshold:
            checks.append(f"sentiment={sentiment_data['avg_sentiment']:.2f}")
        else:
            return False, "Sentiment too low"

        # 2. Mention count sufficient
        if sentiment_data['mention_count'] >= self.min_mentions:
            checks.append(f"mentions={sentiment_data['mention_count']}")
        else:
            return False, f"Not enough mentions ({sentiment_data['mention_count']} < {self.min_mentions})"

        # 3. Sentiment momentum (spike detection)
        sentiment_std = sentiment_data.get('sentiment_std', 0.1)
        if sentiment_data.get('sentiment_momentum', 0) > 2 * sentiment_std:
            checks.append(f"momentum={sentiment_data['sentiment_momentum']:.3f}")
        else:
            return False, "No sentiment spike"

        # 4. Volume confirmation
        if market_data and market_data['volume'] > market_data['avg_volume'] * self.volume_multiplier:
            checks.append(f"volume={market_data['volume']/market_data['avg_volume']:.1f}x")
        else:
            return False, "Volume not confirmed"

        # 5. Market hours
        if not self._is_market_hours():
            return False, "Market closed"

        # 6. Not already in position
        if self._is_in_position(ticker):
            return False, "Already in position"

        # All checks passed
        reason = "BUY: " + ", ".join(checks)
        return True, reason

    def _should_sell(self, ticker: str, market_data: Dict) -> tuple[bool, str]:
        """Determine if we should generate a SELL signal for an open position.

        Args:
            ticker: Stock ticker symbol
            market_data: Market bar data

        Returns:
            (should_sell, reason)
        """
        position = self._get_position(ticker)
        if not position or not market_data:
            return False, "No position or market data"

        current_price = market_data['close']
        entry_price = position['avg_entry_price']

        # Calculate P&L
        pnl_pct = (current_price - entry_price) / entry_price

        # Check exit conditions

        # 1. Take profit
        if pnl_pct >= self.take_profit_pct:
            return True, f"Take profit: {pnl_pct*100:.1f}% gain"

        # 2. Stop loss
        if pnl_pct <= -self.stop_loss_pct:
            return True, f"Stop loss: {pnl_pct*100:.1f}% loss"

        # 3. Time exit
        entry_time = position['entry_timestamp']
        hold_time = (datetime.utcnow() - entry_time).total_seconds()

        if hold_time > self.max_hold_seconds:
            return True, f"Time exit: held {hold_time/60:.0f} minutes"

        # 4. Sentiment reversal
        sentiment_data = self._get_sentiment_data(ticker)
        if sentiment_data and sentiment_data['avg_sentiment'] < 0.3:
            return True, f"Sentiment reversal: {sentiment_data['avg_sentiment']:.2f}"

        return False, "Hold position"

    def generate(self, ticker: str) -> Optional[Signal]:
        """Generate a trading signal for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Signal object or None
        """
        # Get data
        sentiment_data = self._get_sentiment_data(ticker)
        market_data = self._get_market_data(ticker)

        if not sentiment_data:
            return None

        # Check for BUY signal
        if not self._is_in_position(ticker):
            should_buy, reason = self._should_buy(ticker, sentiment_data, market_data or {})

            if should_buy:
                return Signal(
                    timestamp=datetime.utcnow(),
                    ticker=ticker,
                    action='BUY',
                    confidence=sentiment_data['avg_sentiment'],
                    reason=reason,
                    metadata={
                        'sentiment': sentiment_data,
                        'price': market_data['close'] if market_data else None
                    }
                )

        # Check for SELL signal
        else:
            should_sell, reason = self._should_sell(ticker, market_data or {})

            if should_sell:
                return Signal(
                    timestamp=datetime.utcnow(),
                    ticker=ticker,
                    action='SELL',
                    confidence=1.0,
                    reason=reason,
                    metadata={
                        'price': market_data['close'] if market_data else None
                    }
                )

        return None
