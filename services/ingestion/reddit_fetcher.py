#!/usr/bin/env python3
"""
Reddit Data Fetcher - Fetches posts from configured subreddits
"""
import praw
import redis
import json
import time
import logging
import hashlib
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class RedditFetcher:
    """Fetches posts from Reddit and pushes to Redis streams."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        redis_client: redis.Redis,
        subreddits: list[str] = None,
    ):
        """Initialize Reddit fetcher.

        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: User agent string
            redis_client: Redis client instance
            subreddits: List of subreddit names to monitor
        """
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        self.redis = redis_client
        self.subreddits = subreddits or ["wallstreetbets", "stocks"]
        self.seen_ids = set()
        logger.info(f"Initialized Reddit fetcher for subreddits: {self.subreddits}")

    def fetch_posts(self, limit: int = 100) -> int:
        """Fetch recent posts from configured subreddits.

        Args:
            limit: Maximum number of posts to fetch per subreddit

        Returns:
            Number of new posts fetched
        """
        count = 0
        for subreddit_name in self.subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                logger.debug(f"Fetching from r/{subreddit_name}")

                for post in subreddit.new(limit=limit):
                    if self._process_post(post, subreddit_name):
                        count += 1

            except Exception as e:
                logger.error(f"Error fetching from r/{subreddit_name}: {e}", exc_info=True)

        return count

    def _process_post(self, post, subreddit_name: str) -> bool:
        """Process a single post and push to Redis if new.

        Args:
            post: PRAW submission object
            subreddit_name: Name of the subreddit

        Returns:
            True if post was new and processed, False otherwise
        """
        post_id = post.id

        # Check if already seen in memory
        if post_id in self.seen_ids:
            return False

        # Create content for deduplication
        content = f"{post.title} {post.selftext}"
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # Check if content already exists in Redis
        if self.redis.sismember("seen_content_hashes", content_hash):
            logger.debug(f"Duplicate content detected: {post_id}")
            self.seen_ids.add(post_id)  # Add to memory to skip faster next time
            return False

        # Extract data
        data = {
            "id": post_id,
            "source": "reddit",
            "subreddit": subreddit_name,
            "title": post.title,
            "text": post.selftext if post.selftext else "",
            "author": str(post.author) if post.author else "[deleted]",
            "score": post.score,
            "upvote_ratio": post.upvote_ratio,
            "num_comments": post.num_comments,
            "created_utc": post.created_utc,
            "url": post.url,
            "permalink": f"https://reddit.com{post.permalink}",
            "content_hash": content_hash,
            "fetched_at": datetime.utcnow().isoformat(),
        }

        # Push to Redis stream
        try:
            self.redis.xadd("raw:social", {"data": json.dumps(data)})
            self.seen_ids.add(post_id)

            # Add content hash to Redis set with 24-hour expiry
            self.redis.sadd("seen_content_hashes", content_hash)
            self.redis.expire("seen_content_hashes", 86400)  # 24 hours

            logger.info(f"✅ Fetched post: r/{subreddit_name}/{post_id} - {post.title[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Error pushing to Redis: {e}", exc_info=True)
            return False

    def run_forever(self, interval: int = 30):
        """Run fetcher in a loop.

        Args:
            interval: Seconds between fetch cycles
        """
        logger.info(f"🚀 Starting Reddit fetcher (interval: {interval}s)")
        logger.info(f"Monitoring subreddits: {', '.join(self.subreddits)}")

        while True:
            try:
                start_time = time.time()
                count = self.fetch_posts()
                elapsed = time.time() - start_time

                logger.info(f"📊 Fetched {count} new posts in {elapsed:.2f}s")

                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("🛑 Shutting down Reddit fetcher")
                break
            except Exception as e:
                logger.error(f"Error in fetch loop: {e}", exc_info=True)
                logger.info(f"Retrying in {interval}s...")
                time.sleep(interval)
