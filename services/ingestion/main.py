#!/usr/bin/env python3
"""
Ingestion Service - Placeholder
This will be implemented in Phase 2-4
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
    logger.info("🚀 Ingestion service starting (placeholder mode)")
    logger.info("Will be implemented in Phase 2: Reddit, Phase 3: News, Phase 4: Market data")

    while True:
        logger.info("Ingestion service running... (waiting for implementation)")
        time.sleep(60)

if __name__ == "__main__":
    main()
