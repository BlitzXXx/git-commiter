#!/usr/bin/env python3
"""
Portfolio Manager - Tracks positions and syncs with Alpaca
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class Portfolio:
    """Manages portfolio state and syncs with Alpaca."""

    def __init__(self, api_key: str, secret_key: str, db_url: str, paper: bool = True):
        """Initialize portfolio manager.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            db_url: PostgreSQL connection URL
            paper: Use paper trading (default: True)
        """
        self.trading_client = TradingClient(api_key, secret_key, paper=paper)
        self.db_engine = create_engine(db_url, poolclass=NullPool)

        logger.info(f"Initialized Portfolio ({'paper' if paper else 'live'} trading)")

    def sync_with_alpaca(self):
        """Sync local database with Alpaca account state."""
        try:
            # Get account info
            account = self.trading_client.get_account()

            logger.info(f"Account: Cash=${float(account.cash):.2f}, "
                       f"Equity=${float(account.equity):.2f}, "
                       f"Buying Power=${float(account.buying_power):.2f}")

            # Get positions from Alpaca
            alpaca_positions = self.trading_client.get_all_positions()

            # Update database
            with self.db_engine.connect() as conn:
                # Clear current positions
                conn.execute(text("DELETE FROM positions"))

                # Insert Alpaca positions
                for position in alpaca_positions:
                    conn.execute(
                        text("""
                            INSERT INTO positions
                            (ticker, quantity, avg_entry_price, current_price, unrealized_pnl, entry_timestamp)
                            VALUES (:ticker, :quantity, :avg_price, :current_price, :pnl, :entry_time)
                        """),
                        {
                            'ticker': position.symbol,
                            'quantity': int(position.qty),
                            'avg_price': float(position.avg_entry_price),
                            'current_price': float(position.current_price),
                            'pnl': float(position.unrealized_pl),
                            'entry_time': datetime.utcnow()  # Approximate
                        }
                    )

                conn.commit()

            logger.info(f"Synced {len(alpaca_positions)} positions from Alpaca")

        except Exception as e:
            logger.error(f"Error syncing with Alpaca: {e}", exc_info=True)

    def get_position(self, ticker: str) -> Optional[Dict]:
        """Get position for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Position dict or None
        """
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT ticker, quantity, avg_entry_price, current_price, unrealized_pnl, entry_timestamp
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
                        'current_price': float(row[3]) if row[3] else 0.0,
                        'unrealized_pnl': float(row[4]) if row[4] else 0.0,
                        'entry_timestamp': row[5]
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None

    def get_all_positions(self) -> List[Dict]:
        """Get all current positions.

        Returns:
            List of position dicts
        """
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT ticker, quantity, avg_entry_price, current_price, unrealized_pnl, entry_timestamp
                        FROM positions
                        ORDER BY entry_timestamp DESC
                    """)
                )

                positions = []
                for row in result:
                    positions.append({
                        'ticker': row[0],
                        'quantity': int(row[1]),
                        'avg_entry_price': float(row[2]),
                        'current_price': float(row[3]) if row[3] else 0.0,
                        'unrealized_pnl': float(row[4]) if row[4] else 0.0,
                        'entry_timestamp': row[5]
                    })

                return positions

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def update_position_prices(self):
        """Update current prices for all positions from Alpaca."""
        try:
            positions = self.get_all_positions()

            if not positions:
                return

            for position in positions:
                ticker = position['ticker']

                # Get latest price from Alpaca
                try:
                    alpaca_position = self.trading_client.get_open_position(ticker)
                    current_price = float(alpaca_position.current_price)
                    unrealized_pnl = float(alpaca_position.unrealized_pl)

                    # Update database
                    with self.db_engine.connect() as conn:
                        conn.execute(
                            text("""
                                UPDATE positions
                                SET current_price = :price,
                                    unrealized_pnl = :pnl,
                                    last_updated = NOW()
                                WHERE ticker = :ticker
                            """),
                            {
                                'price': current_price,
                                'pnl': unrealized_pnl,
                                'ticker': ticker
                            }
                        )
                        conn.commit()

                except Exception as e:
                    logger.debug(f"Could not update price for {ticker}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error updating position prices: {e}")

    def get_buying_power(self) -> float:
        """Get available buying power.

        Returns:
            Buying power in dollars
        """
        try:
            account = self.trading_client.get_account()
            return float(account.buying_power)
        except Exception as e:
            logger.error(f"Error getting buying power: {e}")
            return 0.0

    def get_account_value(self) -> float:
        """Get total account value.

        Returns:
            Account value in dollars
        """
        try:
            account = self.trading_client.get_account()
            return float(account.equity)
        except Exception as e:
            logger.error(f"Error getting account value: {e}")
            return 0.0

    def is_market_open(self) -> bool:
        """Check if market is currently open.

        Returns:
            True if market is open
        """
        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return False
