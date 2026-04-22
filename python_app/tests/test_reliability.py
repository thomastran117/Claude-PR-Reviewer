import inspect
import unittest

from fastapi.params import Depends as DependsParam

from app.middleware.auth import authenticate_user
from app.routes.review import review_pr
from app.services.cache import CacheService
from app.services.github import GitHubService, MARKER, MAX_COMMENT_CHARS
from app.services.review import parse_inline_comments, parse_status


class ReviewRouteTests(unittest.TestCase):
    def test_review_route_uses_auth_dependency(self):
        user_param = inspect.signature(review_pr).parameters["user"]

        self.assertIsInstance(user_param.default, DependsParam)
        self.assertIs(user_param.default.dependency, authenticate_user)


class ReviewParserTests(unittest.TestCase):
    def test_parse_status(self):
        self.assertEqual(parse_status("STATUS: FAIL\n\n## Summary\nNope."), "FAIL")

    def test_parse_inline_comments_from_fenced_json(self):
        review = """STATUS: OK

## Summary
Looks workable.

## Inline Annotations
```json
[{"file": "app.py", "line": 12, "message": "Handle the missing value."}]
```
"""

        self.assertEqual(
            parse_inline_comments(review),
            [{"file": "app.py", "line": 12, "message": "Handle the missing value."}],
        )


class CacheServiceTests(unittest.TestCase):
    def test_expired_entry_returns_none(self):
        cache = CacheService(max_entries=2, ttl_ms=1000)
        cache.set("owner", "repo", 1, "sha", {
            "reviewText": "review",
            "status": "OK",
            "inlineComments": [],
        })

        key = cache._make_key("owner", "repo", 1, "sha")
        cache._cache[key].cached_at -= 1001

        self.assertIsNone(cache.get("owner", "repo", 1, "sha"))


class GitHubReviewBodyTests(unittest.TestCase):
    def test_review_body_includes_marker_and_head_sha(self):
        body = GitHubService()._build_review_body("STATUS: PASS", "abc123")

        self.assertIn(MARKER, body)
        self.assertIn("abc123", body)

    def test_review_body_is_truncated_to_comment_limit(self):
        body = GitHubService()._build_review_body("x" * (MAX_COMMENT_CHARS + 1000), "abc123")

        self.assertLessEqual(len(body), MAX_COMMENT_CHARS)
        self.assertIn("Review truncated", body)
        self.assertIn(MARKER, body)


if __name__ == "__main__":
    unittest.main()
