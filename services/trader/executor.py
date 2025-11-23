#!/usr/bin/env python3
"""
Order Executor - Executes trades on Alpaca paper trading
"""
import logging
import time
from typing import Optional, Dict
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from signal_generator import Signal

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Executes trading orders on Alpaca."""

    def __init__(self, api_key: str, secret_key: str, db_url: str, paper: bool = True):
        """Initialize order executor.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            db_url: PostgreSQL connection URL
            paper: Use paper trading (default: True)
        """
        self.trading_client = TradingClient(api_key, secret_key, paper=paper)
        self.db_engine = create_engine(db_url, poolclass=NullPool)

        logger.info(f"Initialized OrderExecutor ({'paper' if paper else 'live'} trading)")

    def execute_signal(self, signal: Signal, quantity: int) -> Optional[Dict]:
        """Execute a trading signal.

        Args:
            signal: Trading signal
            quantity: Number of shares to trade

        Returns:
            Order result dict or None
        """
        if signal.action == 'BUY':
            return self._execute_buy(signal, quantity)
        elif signal.action == 'SELL':
            return self._execute_sell(signal)
        else:
            logger.error(f"Unknown signal action: {signal.action}")
            return None

    def _execute_buy(self, signal: Signal, quantity: int, retries: int = 3) -> Optional[Dict]:
        """Execute a BUY order.

        Args:
            signal: BUY signal
            quantity: Number of shares to buy
            retries: Number of retry attempts

        Returns:
            Order result dict or None
        """
        for attempt in range(retries):
            try:
                logger.info(f"Executing BUY {quantity} shares of {signal.ticker} (attempt {attempt + 1}/{retries})")

                # Create market buy order
                order_request = MarketOrderRequest(
                    symbol=signal.ticker,
                    qty=quantity,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY
                )

                # Submit order
                order = self.trading_client.submit_order(order_request)

                logger.info(f"✅ BUY order submitted: {order.id} for {signal.ticker}")

                # Wait for fill (with timeout)
                filled_order = self._wait_for_fill(order.id, timeout=30)

                if filled_order:
                    # Store trade in database
                    self._store_trade(
                        ticker=signal.ticker,
                        action='BUY',
                        quantity=quantity,
                        price=float(filled_order.filled_avg_price) if filled_order.filled_avg_price else 0.0,
                        order_id=str(order.id),
                        signal_reason=signal.reason,
                        sentiment_score=signal.confidence
                    )

                    # Update position in database
                    self._update_position_after_buy(
                        ticker=signal.ticker,
                        quantity=quantity,
                        price=float(filled_order.filled_avg_price) if filled_order.filled_avg_price else 0.0
                    )

                    return {
                        'order_id': str(order.id),
                        'ticker': signal.ticker,
                        'action': 'BUY',
                        'quantity': quantity,
                        'price': float(filled_order.filled_avg_price) if filled_order.filled_avg_price else 0.0,
                        'status': 'filled'
                    }
                else:
                    logger.warning(f"Order {order.id} not filled within timeout")
                    return None

            except Exception as e:
                logger.error(f"Error executing BUY (attempt {attempt + 1}): {e}", exc_info=True)

                if attempt < retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to execute BUY after {retries} attempts")
                    return None

        return None

    def _execute_sell(self, signal: Signal, retries: int = 3) -> Optional[Dict]:
        """Execute a SELL order (close position).

        Args:
            signal: SELL signal
            retries: Number of retry attempts

        Returns:
            Order result dict or None
        """
        for attempt in range(retries):
            try:
                # Get current position quantity
                position = self.trading_client.get_open_position(signal.ticker)
                quantity = int(float(position.qty))

                logger.info(f"Executing SELL {quantity} shares of {signal.ticker} (attempt {attempt + 1}/{retries})")

                # Create market sell order
                order_request = MarketOrderRequest(
                    symbol=signal.ticker,
                    qty=quantity,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY
                )

                # Submit order
                order = self.trading_client.submit_order(order_request)

                logger.info(f"✅ SELL order submitted: {order.id} for {signal.ticker}")

                # Wait for fill
                filled_order = self._wait_for_fill(order.id, timeout=30)

                if filled_order:
                    # Calculate P&L
                    sell_price = float(filled_order.filled_avg_price) if filled_order.filled_avg_price else 0.0
                    entry_price = float(position.avg_entry_price)
                    pnl = (sell_price - entry_price) * quantity

                    # Store trade
                    self._store_trade(
                        ticker=signal.ticker,
                        action='SELL',
                        quantity=quantity,
                        price=sell_price,
                        order_id=str(order.id),
                        signal_reason=signal.reason,
                        sentiment_score=signal.confidence
                    )

                    # Remove position from database
                    self._remove_position(signal.ticker, pnl)

                    logger.info(f"💰 Closed position {signal.ticker}: P&L = ${pnl:.2f}")

                    return {
                        'order_id': str(order.id),
                        'ticker': signal.ticker,
                        'action': 'SELL',
                        'quantity': quantity,
                        'price': sell_price,
                        'pnl': pnl,
                        'status': 'filled'
                    }
                else:
                    logger.warning(f"Order {order.id} not filled within timeout")
                    return None

            except Exception as e:
                logger.error(f"Error executing SELL (attempt {attempt + 1}): {e}", exc_info=True)

                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to execute SELL after {retries} attempts")
                    return None

        return None

    def _wait_for_fill(self, order_id: str, timeout: int = 30) -> Optional:
        """Wait for order to be filled.

        Args:
            order_id: Alpaca order ID
            timeout: Timeout in seconds

        Returns:
            Filled order or None
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                order = self.trading_client.get_order_by_id(order_id)

                if order.status == 'filled':
                    return order
                elif order.status in ['canceled', 'expired', 'rejected']:
                    logger.error(f"Order {order_id} status: {order.status}")
                    return None

                time.sleep(1)  # Poll every second

            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                return None

        logger.warning(f"Order {order_id} fill timeout after {timeout}s")
        return None

    def _store_trade(self, ticker: str, action: str, quantity: int, price: float,
                     order_id: str, signal_reason: str = None, sentiment_score: float = None):
        """Store executed trade in database.

        Args:
            ticker: Stock ticker
            action: BUY or SELL
            quantity: Number of shares
            price: Execution price
            order_id: Alpaca order ID
            signal_reason: Reason from signal
            sentiment_score: Sentiment score from signal
        """
        try:
            with self.db_engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO trades
                        (timestamp, ticker, action, quantity, price, total_value, order_id, signal_reason, sentiment_score)
                        VALUES (NOW(), :ticker, :action, :quantity, :price, :total_value, :order_id, :reason, :sentiment)
                    """),
                    {
                        'ticker': ticker,
                        'action': action,
                        'quantity': quantity,
                        'price': price,
                        'total_value': quantity * price,
                        'order_id': order_id,
                        'reason': signal_reason,
                        'sentiment': sentiment_score
                    }
                )
                conn.commit()

            logger.debug(f"Stored trade: {action} {quantity} {ticker} @ ${price:.2f}")

        except Exception as e:
            logger.error(f"Error storing trade: {e}", exc_info=True)

    def _update_position_after_buy(self, ticker: str, quantity: int, price: float):
        """Update or create position after BUY.

        Args:
            ticker: Stock ticker
            quantity: Number of shares bought
            price: Purchase price
        """
        try:
            with self.db_engine.connect() as conn:
                # Check if position exists
                result = conn.execute(
                    text("SELECT quantity, avg_entry_price FROM positions WHERE ticker = :ticker"),
                    {'ticker': ticker}
                )
                row = result.fetchone()

                if row:
                    # Update existing position (average down/up)
                    existing_qty = int(row[0])
                    existing_price = float(row[1])

                    new_qty = existing_qty + quantity
                    new_avg_price = ((existing_qty * existing_price) + (quantity * price)) / new_qty

                    conn.execute(
                        text("""
                            UPDATE positions
                            SET quantity = :quantity,
                                avg_entry_price = :price,
                                current_price = :current_price,
                                last_updated = NOW()
                            WHERE ticker = :ticker
                        """),
                        {
                            'quantity': new_qty,
                            'price': new_avg_price,
                            'current_price': price,
                            'ticker': ticker
                        }
                    )
                else:
                    # Create new position
                    conn.execute(
                        text("""
                            INSERT INTO positions
                            (ticker, quantity, avg_entry_price, current_price, entry_timestamp)
                            VALUES (:ticker, :quantity, :price, :current_price, NOW())
                        """),
                        {
                            'ticker': ticker,
                            'quantity': quantity,
                            'price': price,
                            'current_price': price
                        }
                    )

                conn.commit()

        except Exception as e:
            logger.error(f"Error updating position: {e}", exc_info=True)

    def _remove_position(self, ticker: str, realized_pnl: float):
        """Remove position after SELL.

        Args:
            ticker: Stock ticker
            realized_pnl: Realized profit/loss
        """
        try:
            with self.db_engine.connect() as conn:
                # Update realized P&L before deleting (optional - could keep history)
                conn.execute(
                    text("UPDATE positions SET realized_pnl = :pnl WHERE ticker = :ticker"),
                    {'pnl': realized_pnl, 'ticker': ticker}
                )

                # Delete position
                conn.execute(
                    text("DELETE FROM positions WHERE ticker = :ticker"),
                    {'ticker': ticker}
                )

                conn.commit()

        except Exception as e:
            logger.error(f"Error removing position: {e}", exc_info=True)
