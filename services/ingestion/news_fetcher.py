#!/usr/bin/env python3
"""
News Data Fetcher - Fetches financial news from NewsAPI
"""
import requests
import redis
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class NewsFetcher:
    """Fetches financial news and pushes to Redis streams."""

    def __init__(
        self,
        api_key: str,
        redis_client: redis.Redis,
    ):
        """Initialize News fetcher.

        Args:
            api_key: NewsAPI.org API key
            redis_client: Redis client instance
        """
        self.api_key = api_key
        self.redis = redis_client
        self.base_url = "https://newsapi.org/v2/everything"
        self.seen_urls = set()
        logger.info("Initialized News fetcher")

    def fetch_articles(self, limit: int = 20) -> int:
        """Fetch recent financial news articles.

        Args:
            limit: Maximum number of articles to fetch

        Returns:
            Number of new articles fetched
        """
        # NewsAPI free tier: 100 requests/day
        # So we fetch infrequently but get more articles each time
        keywords = ["stock market", "trading", "earnings", "IPO", "stocks"]
        count = 0

        for keyword in keywords[:2]:  # Limit to 2 keywords to conserve API calls
            try:
                # Get articles from last hour
                from_date = (datetime.utcnow() - timedelta(hours=1)).isoformat()

                params = {
                    "q": keyword,
                    "apiKey": self.api_key,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "from": from_date,
                    "pageSize": limit,
                }

                logger.debug(f"Fetching news for keyword: {keyword}")
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()

                if data.get("status") == "ok":
                    articles = data.get("articles", [])
                    logger.debug(f"Received {len(articles)} articles for '{keyword}'")

                    for article in articles:
                        if self._process_article(article):
                            count += 1
                else:
                    logger.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")

            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching news for '{keyword}': {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error processing news: {e}", exc_info=True)

        return count

    def _process_article(self, article: dict) -> bool:
        """Process a single article and push to Redis if new.

        Args:
            article: Article data from NewsAPI

        Returns:
            True if article was new and processed, False otherwise
        """
        url = article.get("url")
        if not url:
            return False

        # Check if already seen
        if url in self.seen_urls:
            return False

        # Create content hash for deduplication
        content = f"{article.get('title', '')} {article.get('description', '')}"
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # Check if content already exists
        if self.redis.sismember("seen_content_hashes", content_hash):
            logger.debug(f"Duplicate content detected: {url}")
            self.seen_urls.add(url)
            return False

        # Extract data
        data = {
            "id": content_hash,  # Use content hash as ID
            "source": "news",
            "subreddit": None,  # Not from Reddit
            "title": article.get("title", ""),
            "text": article.get("description", "") + " " + article.get("content", ""),
            "author": article.get("author", "Unknown"),
            "score": 0,  # News doesn't have scores
            "upvote_ratio": 1.0,
            "num_comments": 0,
            "created_utc": self._parse_published_at(article.get("publishedAt")),
            "url": url,
            "permalink": url,
            "content_hash": content_hash,
            "fetched_at": datetime.utcnow().isoformat(),
            "news_source": article.get("source", {}).get("name", "Unknown"),
        }

        # Push to Redis stream (same stream as Reddit)
        try:
            self.redis.xadd("raw:social", {"data": json.dumps(data)})
            self.seen_urls.add(url)

            # Add content hash to Redis set with 24-hour expiry
            self.redis.sadd("seen_content_hashes", content_hash)
            self.redis.expire("seen_content_hashes", 86400)

            logger.info(f"✅ Fetched article: {article.get('title', '')[:60]}...")
            return True

        except Exception as e:
            logger.error(f"Error pushing to Redis: {e}", exc_info=True)
            return False

    def _parse_published_at(self, published_at: Optional[str]) -> float:
        """Parse NewsAPI publishedAt timestamp to Unix timestamp.

        Args:
            published_at: ISO 8601 timestamp string

        Returns:
            Unix timestamp (float)
        """
        if not published_at:
            return datetime.utcnow().timestamp()

        try:
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return datetime.utcnow().timestamp()

    def run_forever(self, interval: int = 900):
        """Run fetcher in a loop.

        Args:
            interval: Seconds between fetch cycles (default: 15 minutes)
        """
        logger.info(f"🚀 Starting News fetcher (interval: {interval}s = {interval/60:.1f} min)")
        logger.info("⚠️  NewsAPI free tier: 100 requests/day - fetching conservatively")

        while True:
            try:
                start_time = time.time()
                count = self.fetch_articles()
                elapsed = time.time() - start_time

                logger.info(f"📰 Fetched {count} new articles in {elapsed:.2f}s")

                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("🛑 Shutting down News fetcher")
                break
            except Exception as e:
                logger.error(f"Error in fetch loop: {e}", exc_info=True)
                logger.info(f"Retrying in {interval}s...")
                time.sleep(interval)
