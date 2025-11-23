#!/usr/bin/env python3
"""
Risk Manager - Validates trades and manages risk limits
"""
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from signal_generator import Signal

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages trading risk and validates all trades before execution."""

    def __init__(self, db_url: str, config: dict):
        """Initialize risk manager.

        Args:
            db_url: PostgreSQL connection URL
            config: Risk configuration dict
        """
        self.db_engine = create_engine(db_url, poolclass=NullPool)

        # Load risk limits from config
        risk = config.get('risk', {})
        self.max_positions = risk.get('max_positions', 5)
        self.position_size_pct = risk.get('position_size_pct', 0.10)
        self.max_daily_loss_pct = risk.get('max_daily_loss_pct', 0.05)
        self.max_sector_exposure_pct = risk.get('max_sector_exposure_pct', 0.30)
        self.max_trade_loss_pct = risk.get('max_trade_loss_pct', 0.02)

        # Kill switch
        self.enable_kill_switch = risk.get('enable_kill_switch', True)
        self.kill_switch_threshold_pct = risk.get('kill_switch_threshold_pct', 0.05)
        self.trading_halted = False

        logger.info(f"Initialized RiskManager: max_positions={self.max_positions}, "
                   f"position_size={self.position_size_pct*100}%, "
                   f"daily_loss_limit={self.max_daily_loss_pct*100}%")

    def get_portfolio_state(self) -> Dict:
        """Get current portfolio state.

        Returns:
            Dict with portfolio metrics
        """
        try:
            with self.db_engine.connect() as conn:
                # Get positions
                result = conn.execute(
                    text("""
                        SELECT COUNT(*) as position_count,
                               COALESCE(SUM(quantity * current_price), 0) as total_value,
                               COALESCE(SUM(unrealized_pnl), 0) as total_unrealized_pnl,
                               COALESCE(SUM(realized_pnl), 0) as total_realized_pnl
                        FROM positions
                    """)
                )
                row = result.fetchone()

                position_count = int(row[0]) if row[0] else 0
                total_value = float(row[1]) if row[1] else 0.0
                unrealized_pnl = float(row[2]) if row[2] else 0.0
                realized_pnl = float(row[3]) if row[3] else 0.0

                # Get cash (assuming starting capital - we'll update this in Phase 10)
                starting_capital = 100000.0  # $100k paper trading
                cash = starting_capital - total_value + realized_pnl

                # Get daily P&L (trades from today)
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
                daily_pnl_pct = daily_pnl / starting_capital if starting_capital > 0 else 0.0

                return {
                    'position_count': position_count,
                    'cash': cash,
                    'total_value': starting_capital + unrealized_pnl + realized_pnl,
                    'unrealized_pnl': unrealized_pnl,
                    'realized_pnl': realized_pnl,
                    'daily_pnl': daily_pnl,
                    'daily_pnl_pct': daily_pnl_pct,
                    'starting_capital': starting_capital
                }

        except Exception as e:
            logger.error(f"Error getting portfolio state: {e}")
            return {
                'position_count': 0,
                'cash': 100000.0,
                'total_value': 100000.0,
                'unrealized_pnl': 0.0,
                'realized_pnl': 0.0,
                'daily_pnl': 0.0,
                'daily_pnl_pct': 0.0,
                'starting_capital': 100000.0
            }

    def get_sector_exposure(self, ticker: str) -> float:
        """Get current exposure to a ticker's sector.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current value invested in this sector
        """
        try:
            with self.db_engine.connect() as conn:
                # Get ticker's sector
                result = conn.execute(
                    text("SELECT sector FROM tickers WHERE symbol = :ticker"),
                    {'ticker': ticker}
                )
                row = result.fetchone()
                if not row or not row[0]:
                    return 0.0

                sector = row[0]

                # Get total value in this sector
                result = conn.execute(
                    text("""
                        SELECT COALESCE(SUM(p.quantity * p.current_price), 0)
                        FROM positions p
                        JOIN tickers t ON p.ticker = t.symbol
                        WHERE t.sector = :sector
                    """),
                    {'sector': sector}
                )
                row = result.fetchone()
                return float(row[0]) if row[0] else 0.0

        except Exception as e:
            logger.error(f"Error getting sector exposure: {e}")
            return 0.0

    def should_halt_trading(self, portfolio: Dict) -> bool:
        """Check if trading should be halted (kill switch).

        Args:
            portfolio: Portfolio state dict

        Returns:
            True if trading should be halted
        """
        if not self.enable_kill_switch:
            return False

        if portfolio['daily_pnl_pct'] <= -self.kill_switch_threshold_pct:
            if not self.trading_halted:
                logger.critical(
                    f"🚨 KILL SWITCH ACTIVATED! Daily loss: {portfolio['daily_pnl_pct']*100:.2f}% "
                    f"(threshold: {self.kill_switch_threshold_pct*100:.2f}%)"
                )
                self.trading_halted = True
            return True

        return False

    def validate_trade(self, signal: Signal, portfolio: Dict) -> Tuple[bool, str]:
        """Validate a trade signal against risk rules.

        Args:
            signal: Trading signal to validate
            portfolio: Current portfolio state

        Returns:
            (is_valid, reason)
        """
        # Check kill switch
        if self.should_halt_trading(portfolio):
            return False, "Trading halted - daily loss limit exceeded"

        if signal.action == 'BUY':
            return self._validate_buy(signal, portfolio)
        elif signal.action == 'SELL':
            return self._validate_sell(signal, portfolio)
        else:
            return False, f"Unknown action: {signal.action}"

    def _validate_buy(self, signal: Signal, portfolio: Dict) -> Tuple[bool, str]:
        """Validate a BUY signal.

        Args:
            signal: BUY signal
            portfolio: Portfolio state

        Returns:
            (is_valid, reason)
        """
        # 1. Check position count
        if portfolio['position_count'] >= self.max_positions:
            return False, f"Max positions reached ({self.max_positions})"

        # 2. Check buying power
        position_value = portfolio['starting_capital'] * self.position_size_pct
        if position_value > portfolio['cash']:
            return False, f"Insufficient cash (need ${position_value:.2f}, have ${portfolio['cash']:.2f})"

        # 3. Check daily loss
        if portfolio['daily_pnl_pct'] <= -self.max_daily_loss_pct:
            return False, f"Daily loss limit hit ({portfolio['daily_pnl_pct']*100:.2f}%)"

        # 4. Check sector exposure
        sector_exposure = self.get_sector_exposure(signal.ticker)
        max_sector_value = portfolio['total_value'] * self.max_sector_exposure_pct

        if sector_exposure + position_value > max_sector_value:
            return False, f"Max sector exposure would be exceeded"

        return True, "Risk checks passed"

    def _validate_sell(self, signal: Signal, portfolio: Dict) -> Tuple[bool, str]:
        """Validate a SELL signal.

        Args:
            signal: SELL signal
            portfolio: Portfolio state

        Returns:
            (is_valid, reason)
        """
        # Always allow sells (we want to exit positions)
        # Just check that position exists
        try:
            with self.db_engine.connect() as conn:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM positions WHERE ticker = :ticker"),
                    {'ticker': signal.ticker}
                )
                count = result.scalar()

                if count == 0:
                    return False, "Not in position"

                return True, "Valid SELL"

        except Exception as e:
            logger.error(f"Error validating SELL: {e}")
            return False, "Database error"

    def calculate_position_size(self, signal: Signal, portfolio: Dict, current_price: float) -> int:
        """Calculate number of shares to buy.

        Args:
            signal: Trading signal
            portfolio: Portfolio state
            current_price: Current stock price

        Returns:
            Number of shares to buy
        """
        if signal.action != 'BUY':
            return 0

        # Calculate position value
        max_position_value = portfolio['starting_capital'] * self.position_size_pct

        # Don't exceed available cash
        position_value = min(max_position_value, portfolio['cash'])

        # Calculate shares
        shares = int(position_value / current_price)

        # Must buy at least 1 share
        return max(1, shares)

    def reset_kill_switch(self):
        """Reset the kill switch (e.g., start of new trading day)."""
        if self.trading_halted:
            logger.info("Resetting kill switch for new trading day")
            self.trading_halted = False
