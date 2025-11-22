#!/usr/bin/env python3
"""
Sentiment Analysis Service - Placeholder
This will be implemented in Phase 5-6
"""
import os
import time
import logging

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Sentiment analysis service starting (placeholder mode)")
    logger.info("Will be implemented in Phase 5: FinBERT analysis, Phase 6: Ticker extraction")

    while True:
        logger.info("Sentiment service running... (waiting for implementation)")
        time.sleep(60)

if __name__ == "__main__":
    main()
