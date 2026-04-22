"""
Review API route
"""

import asyncio
import re
import time
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.middleware.auth import authenticate_user
from app.services.github import github_service, GitHubServiceError
from app.services.claude import REVIEW_MODEL, review as claude_review, ClaudeServiceError
from app.services.review import SYSTEM_PROMPT, SYSTEM_PROMPT_HASH, build_user_prompt, parse_status, parse_inline_comments, FALLBACK_REVIEW
from app.services.cache import cache_service

logger = logging.getLogger(__name__)

router = APIRouter()
_review_locks: Dict[str, asyncio.Lock] = {}

# Regex for PR URL validation
PR_URL_REGEX = re.compile(r'github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)')

class ReviewRequest(BaseModel):
    """Request model for PR review"""
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    pr_url: Optional[str] = Field(None, description="GitHub PR URL")
    owner: Optional[str] = Field(None, description="Repository owner")
    repo: Optional[str] = Field(None, description="Repository name")
    pull_number: Optional[int] = Field(None, description="Pull request number")
    post_comment: Optional[bool] = Field(False, description="Whether to post comment to GitHub")

    @model_validator(mode='after')
    def validate_pr_params(self):
        """Validate PR parameters - either pr_url or owner/repo/pull_number must be provided"""
        if self.pr_url is None:
            # Check if owner/repo/pull_number are provided
            if not all([self.owner, self.repo, self.pull_number is not None]):
                raise ValueError('Must provide pr_url OR owner + repo + pull_number')
        else:
            # Validate pr_url format
            match = PR_URL_REGEX.match(str(self.pr_url))
            if not match:
                raise ValueError('Invalid pr_url format. Expected: https://github.com/owner/repo/pull/123')

        # Validate individual fields
        if self.owner is not None and not str(self.owner).strip():
            raise ValueError('owner must be a non-empty string')
        if self.repo is not None and not str(self.repo).strip():
            raise ValueError('repo must be a non-empty string')
        if self.pull_number is not None and (not isinstance(self.pull_number, int) or self.pull_number <= 0):
            raise ValueError('pull_number must be a positive integer')

        return self

    @field_validator('anthropic_api_key')
    @classmethod
    def validate_anthropic_api_key(cls, v):
        """Validate anthropic_api_key is not empty"""
        if not v or not str(v).strip():
            raise ValueError('anthropic_api_key must be a non-empty string')
        return v

@router.post("/api/review")
async def review_pr(
    request: ReviewRequest,
    user: Dict[str, str] = Depends(authenticate_user)
) -> Dict[str, Any]:
    """
    Review a GitHub pull request using Claude AI

    Returns review results and optionally posts comments to GitHub
    """
    start_time = time.time()

    # Extract PR parameters
    owner: Optional[str] = None
    repo: Optional[str] = None
    pull_number: Optional[int] = None

    if request.pr_url:
        match = PR_URL_REGEX.match(request.pr_url)
        if match:
            owner, repo, pull_number = match.groups()[0], match.groups()[1], int(match.groups()[2])
    else:
        owner = str(request.owner).strip()
        repo = str(request.repo).strip()
        pull_number = request.pull_number

    pr = f"{owner}/{repo}#{pull_number}"
    logger.info(f"[review] start {pr} user={user['username']} post_comment={request.post_comment}")

    try:
        # 1. Fetch PR data (always needed — gives us headSha for the cache key + fresh metadata)
        logger.info(f"[review] fetching PR data for {pr}")
        pr_data = await github_service.get_pr_data(owner, repo, pull_number)
        logger.info(f"[review] fetched {pr_data['files_reviewed']} files, {pr_data['total_diff_chars']} chars sha={pr_data['headSha']}")

        # 2. Check cache — keyed by exact commit SHA so any new push is a cache miss
        review_text: str
        review_status: str
        inline_comments: list
        from_cache = False

        review_fingerprint = f"{pr_data['headSha']}/{REVIEW_MODEL}/{SYSTEM_PROMPT_HASH}"
        lock_key = f"{owner}/{repo}/{pull_number}/{review_fingerprint}"
        lock = _review_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            cached = cache_service.get(owner, repo, pull_number, review_fingerprint)
            if cached:
                logger.info(f"[review] cache hit for {pr} sha={pr_data['headSha']} model={REVIEW_MODEL} prompt={SYSTEM_PROMPT_HASH}")
                review_text = cached["reviewText"]
                review_status = cached["status"]
                inline_comments = cached["inlineComments"]
                from_cache = True
            else:
                # 3. Build prompt and call Claude
                user_message = build_user_prompt(pr_data)

                logger.info("[review] calling Claude")
                review_text = await claude_review(
                    system_prompt=SYSTEM_PROMPT,
                    user_message=user_message,
                    anthropic_api_key=request.anthropic_api_key
                )

                if not review_text:
                    review_text = FALLBACK_REVIEW

                logger.info("[review] Claude responded")

                # 4. Parse results
                review_status = parse_status(review_text)
                inline_comments = parse_inline_comments(review_text)

                # 5. Store in cache
                cache_service.set(owner, repo, pull_number, review_fingerprint, {
                    "reviewText": review_text,
                    "status": review_status,
                    "inlineComments": inline_comments
                })
                logger.info(f"[review] cached result ({cache_service.stats()['size']}/{cache_service.stats()['maxEntries']} entries)")

        logger.info(f"[review] status={review_status} inline_comments={len(inline_comments)}")

        # 6. Optionally post to GitHub (always performed even on a cache hit — caller may want the comment)
        comment_posted = False
        review_id = None
        inline_comments_posted = 0

        if request.post_comment:
            logger.info(f"[review] posting comment to {pr}")
            result = await github_service.post_review(
                owner, repo, pull_number, pr_data["headSha"],
                review_text, inline_comments, pr_data["commentable_lines"]
            )
            comment_posted = True
            review_id = result["review_id"]
            inline_comments_posted = result["inline_comments_posted"]
            logger.info(f"[review] posted review_id={review_id} inline_comments={inline_comments_posted}")

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[review] done {pr} duration={duration_ms}ms cached={from_cache}")

        return {
            "status": review_status,
            "review": review_text,
            "inline_comments": inline_comments,
            "metadata": {
                "pr_url": pr_data["pr_url"],
                "pr_title": pr_data["title"],
                "files_reviewed": pr_data["files_reviewed"],
                "files_truncated": pr_data["files_truncated"],
                "total_diff_chars": pr_data["total_diff_chars"],
                "comment_posted": comment_posted,
                "review_id": review_id,
                "inline_comments_posted": inline_comments_posted,
                "username": user["username"],
                "duration_ms": duration_ms,
                "cached": from_cache,
                "model": REVIEW_MODEL,
                "prompt_hash": SYSTEM_PROMPT_HASH,
            },
        }

    except (GitHubServiceError, ClaudeServiceError) as e:
        # Re-raise service errors to be handled by global error handler
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in review_pr: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
