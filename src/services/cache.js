'use strict';

/**
 * In-memory LRU cache for Claude PR review results.
 *
 * Cache key: owner/repo/pull_number/headSha
 * A new commit to the PR branch changes headSha → automatic cache invalidation.
 *
 * Each entry stores: { reviewText, status, inlineComments, cachedAt }
 */

const MAX_ENTRIES = 500;
const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

// Map maintains insertion order — oldest entries are at the front (LRU eviction).
const _cache = new Map();

function _makeKey(owner, repo, pull_number, headSha) {
  return `${owner}/${repo}/${pull_number}/${headSha}`;
}

/**
 * Retrieve a cached review. Returns null on miss or expiry.
 */
function get(owner, repo, pull_number, headSha) {
  const key = _makeKey(owner, repo, pull_number, headSha);
  const entry = _cache.get(key);
  if (!entry) return null;

  if (Date.now() - entry.cachedAt > TTL_MS) {
    _cache.delete(key);
    return null;
  }

  // LRU: bump to tail so it isn't the first eviction candidate
  _cache.delete(key);
  _cache.set(key, entry);
  return entry;
}

/**
 * Store a review result. Evicts the oldest entry when the cache is full.
 * @param {object} value  { reviewText, status, inlineComments }
 */
function set(owner, repo, pull_number, headSha, value) {
  const key = _makeKey(owner, repo, pull_number, headSha);

  // Evict oldest entry if at capacity and this is a new key
  if (_cache.size >= MAX_ENTRIES && !_cache.has(key)) {
    const oldestKey = _cache.keys().next().value;
    _cache.delete(oldestKey);
  }

  _cache.set(key, { ...value, cachedAt: Date.now() });
}

/**
 * Returns current cache statistics for observability.
 */
function stats() {
  return { size: _cache.size, maxEntries: MAX_ENTRIES, ttlHours: TTL_MS / 3_600_000 };
}

module.exports = { get, set, stats };
