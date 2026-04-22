import inspect
import unittest

from fastapi.params import Depends as DependsParam

from app.middleware.auth import authenticate_user
from app.routes.review import review_pr
from app.services.cache import CacheService
from app.services.github import GitHubService, MARKER, MAX_COMMENT_CHARS, extract_added_lines
from app.services.review import build_user_prompt, parse_inline_comments, parse_status


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

        self.assertEqual(parse_inline_comments(review), [{
            "path": "app.py",
            "line": 12,
            "body": "Handle the missing value.",
        }])

    def test_parse_inline_comments_from_prompt_shape(self):
        review = """STATUS: OK

## Summary
Looks workable.

## Inline Annotations
[{"path": "app.py", "line": 12, "body": "Handle the missing value."}]
"""

        self.assertEqual(parse_inline_comments(review), [{
            "path": "app.py",
            "line": 12,
            "body": "Handle the missing value.",
        }])


class PromptBuilderTests(unittest.TestCase):
    def test_build_user_prompt_includes_patch_hunks(self):
        prompt = build_user_prompt({
            "title": "Fix bug",
            "author": "alice",
            "pull_number": 12,
            "body": "",
            "diffSummary": "app.py (+1 -0)",
            "files": [{
                "filename": "app.py",
                "patch": "@@ -1,1 +1,2 @@\n print('old')\n+print('new')",
                "fullContent": None,
            }],
        })

        self.assertIn("## Diff Patches", prompt)
        self.assertIn("+print('new')", prompt)


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

    def test_extract_added_lines_from_patch(self):
        patch = "@@ -10,2 +10,3 @@\n unchanged\n-old\n+new\n+another\n"

        self.assertEqual(extract_added_lines(patch), {11, 12})

    def test_valid_inline_comments_only_keeps_added_lines(self):
        service = GitHubService()
        valid = service._valid_inline_comments(
            [
                {"path": "app.py", "line": 11, "body": "Good target."},
                {"path": "app.py", "line": 10, "body": "Context line."},
                {"path": "other.py", "line": 11, "body": "Wrong file."},
            ],
            {"app.py": {11}},
        )

        self.assertEqual(valid, [{"path": "app.py", "line": 11, "body": "Good target."}])

    def test_existing_inline_comment_keys_are_scoped_to_head_sha(self):
        class Comment:
            body = "<!-- CLAUDE_PR_INLINE_REVIEW:abc123 -->"
            path = "app.py"
            line = 11

        class PullRequest:
            def get_review_comments(self):
                return [Comment()]

        keys = GitHubService()._existing_inline_comment_keys(PullRequest(), "abc123")

        self.assertEqual(keys, {("app.py", 11)})


if __name__ == "__main__":
    unittest.main()
