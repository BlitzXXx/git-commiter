#!/usr/bin/env python3
"""
Ticker Mapper - Extracts ticker symbols from text
"""
import re
import logging
from typing import List, Set
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class TickerMapper:
    """Extracts and maps ticker symbols from text."""

    def __init__(self, db_url: str):
        """Initialize ticker mapper.

        Args:
            db_url: PostgreSQL connection URL
        """
        # Create database connection
        self.engine = create_engine(db_url, poolclass=NullPool)

        # Load ticker mappings into memory
        self.ticker_map = {}  # company_name (lowercase) -> ticker
        self.valid_tickers = set()  # set of valid ticker symbols

        self._load_ticker_mappings()

        # Regex patterns
        self.cashtag_pattern = re.compile(r'\$([A-Z]{1,5})\b')

        logger.info(f"Initialized TickerMapper with {len(self.valid_tickers)} tickers")

    def _load_ticker_mappings(self):
        """Load ticker mappings from database."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT symbol, company_name, aliases FROM tickers WHERE is_active = true")
                )

                for row in result:
                    symbol = row[0]
                    company_name = row[1]
                    aliases = row[2] if row[2] else []

                    # Add to valid tickers
                    self.valid_tickers.add(symbol)

                    # Map company name to ticker
                    if company_name:
                        self.ticker_map[company_name.lower()] = symbol

                    # Map all aliases to ticker
                    for alias in aliases:
                        self.ticker_map[alias.lower()] = symbol

            logger.info(f"Loaded {len(self.ticker_map)} ticker mappings")

        except Exception as e:
            logger.error(f"Error loading ticker mappings: {e}", exc_info=True)

    def extract_cashtags(self, text: str) -> Set[str]:
        """Extract cashtag tickers ($AAPL, $TSLA, etc).

        Args:
            text: Text to search

        Returns:
            Set of ticker symbols found
        """
        if not text:
            return set()

        matches = self.cashtag_pattern.findall(text)

        # Filter to only valid tickers
        valid_matches = {m for m in matches if m in self.valid_tickers}

        return valid_matches

    def extract_from_text(self, text: str) -> Set[str]:
        """Extract tickers by matching company names/aliases.

        Args:
            text: Text to search

        Returns:
            Set of ticker symbols found
        """
        if not text:
            return set()

        text_lower = text.lower()
        found_tickers = set()

        # Look for company names/aliases
        for name, ticker in self.ticker_map.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(name) + r'\b'
            if re.search(pattern, text_lower):
                found_tickers.add(ticker)

        return found_tickers

    def extract(self, text: str) -> List[str]:
        """Extract all tickers from text (cashtags + company names).

        Args:
            text: Text to search

        Returns:
            List of unique ticker symbols found (sorted)
        """
        if not text:
            return []

        # Extract from both methods
        cashtags = self.extract_cashtags(text)
        text_matches = self.extract_from_text(text)

        # Combine and return sorted
        all_tickers = cashtags.union(text_matches)

        return sorted(list(all_tickers))
