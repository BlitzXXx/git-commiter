#!/usr/bin/env python3
"""
Text Preprocessor - Cleans and normalizes text
"""
import re
import logging

logger = logging.getLogger(__name__)


class TextPreprocessor:
    """Preprocesses social media text for sentiment analysis."""

    def __init__(self):
        """Initialize text preprocessor."""
        # Common patterns
        self.url_pattern = re.compile(r'http\S+|www.\S+')
        self.mention_pattern = re.compile(r'@\w+')
        self.hashtag_pattern = re.compile(r'#(\w+)')
        self.whitespace_pattern = re.compile(r'\s+')

    def clean(self, text: str) -> str:
        """Clean text while preserving sentiment indicators.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove URLs (don't contain sentiment)
        text = self.url_pattern.sub('', text)

        # Remove mentions (don't contain sentiment)
        text = self.mention_pattern.sub('', text)

        # Keep hashtag text (remove # symbol but keep word)
        text = self.hashtag_pattern.sub(r'\1', text)

        # Normalize whitespace
        text = self.whitespace_pattern.sub(' ', text)

        # Trim
        text = text.strip()

        return text

    def normalize(self, text: str) -> str:
        """Normalize text (lowercase, etc).

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Lowercase for consistency
        text = text.lower()

        return text

    def process(self, text: str) -> str:
        """Full preprocessing pipeline.

        Args:
            text: Raw text

        Returns:
            Cleaned and normalized text
        """
        text = self.clean(text)
        text = self.normalize(text)
        return text
