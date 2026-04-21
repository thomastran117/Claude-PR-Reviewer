"""
In-memory LRU cache for Claude PR review results.

Cache key: owner/repo/pull_number/headSha
A new commit to the PR branch changes headSha → automatic cache invalidation.

Each entry stores: { reviewText, status, inlineComments, cachedAt }
"""

import time
from typing import Dict, Any, Optional, Tuple
from collections import OrderedDict

MAX_ENTRIES = 500
TTL_MS = 24 * 60 * 60 * 1000  # 24 hours

class CacheEntry:
    """Cache entry with data and timestamp"""
    def __init__(self, review_text: str, status: str, inline_comments: list):
        self.review_text = review_text
        self.status = status
        self.inline_comments = inline_comments
        self.cached_at = time.time() * 1000  # milliseconds

class CacheService:
    """In-memory LRU cache service"""

    def __init__(self, max_entries: int = MAX_ENTRIES, ttl_ms: int = TTL_MS):
        self.max_entries = max_entries
        self.ttl_ms = ttl_ms
        # OrderedDict maintains insertion order — oldest entries are at the front (LRU eviction)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

    def _make_key(self, owner: str, repo: str, pull_number: int, head_sha: str) -> str:
        """Create cache key"""
        return f"{owner}/{repo}/{pull_number}/{head_sha}"

    def get(self, owner: str, repo: str, pull_number: int, head_sha: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached review. Returns None on miss or expiry.
        """
        key = self._make_key(owner, repo, pull_number, head_sha)
        entry = self._cache.get(key)

        if not entry:
            return None

        # Check TTL
        current_time = time.time() * 1000
        if current_time - entry.cached_at > self.ttl_ms:
            del self._cache[key]
            return None

        # LRU: move to end (most recently used)
        self._cache.move_to_end(key)

        return {
            "reviewText": entry.review_text,
            "status": entry.status,
            "inlineComments": entry.inline_comments
        }

    def set(self, owner: str, repo: str, pull_number: int, head_sha: str, value: Dict[str, Any]):
        """
        Store a review result. Evicts the oldest entry when the cache is full.
        """
        key = self._make_key(owner, repo, pull_number, head_sha)

        # Evict oldest entry if at capacity and this is a new key
        if len(self._cache) >= self.max_entries and key not in self._cache:
            self._cache.popitem(last=False)  # Remove oldest (first) item

        # Store new entry
        entry = CacheEntry(
            review_text=value["reviewText"],
            status=value["status"],
            inline_comments=value["inlineComments"]
        )
        self._cache[key] = entry
        self._cache.move_to_end(key)  # Move to end (most recently used)

    def stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "size": len(self._cache),
            "maxEntries": self.max_entries
        }

# Global cache instance
cache_service = CacheService()