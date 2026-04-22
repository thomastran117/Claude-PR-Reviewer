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
from app.services.review import (
    STRUCTURED_SYSTEM_PROMPT,
    STRUCTURED_SYSTEM_PROMPT_HASH,
    build_review_batches,
    build_user_prompt,
    merge_structured_reviews,
    parse_structured_review,
    render_review_markdown,
    should_split_review,
)
from app.services.cache import cache_service

logger = logging.getLogger(__name__)

router = APIRouter()
_review_locks: Dict[str, asyncio.Lock] = {}

# Regex for PR URL validation
PR_URL_REGEX = re.compile(r'github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)')

def review_print(message: str) -> None:
    """Print review progress to stdout so hosted logs show the review flow."""
    print(f"[review] {message}", flush=True)

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
        source = "pr_url" if self.pr_url is not None else "owner/repo/pull_number"
        review_print(f"validating request params source={source}")
        if self.pr_url is None:
            # Check if owner/repo/pull_number are provided
            if not all([self.owner, self.repo, self.pull_number is not None]):
                review_print("validation failed: missing pr_url or owner/repo/pull_number")
                raise ValueError('Must provide pr_url OR owner + repo + pull_number')
        else:
            # Validate pr_url format
            match = PR_URL_REGEX.match(str(self.pr_url))
            if not match:
                review_print(f"validation failed: invalid pr_url format value={self.pr_url}")
                raise ValueError('Invalid pr_url format. Expected: https://github.com/owner/repo/pull/123')

        # Validate individual fields
        if self.owner is not None and not str(self.owner).strip():
            review_print("validation failed: owner is empty")
            raise ValueError('owner must be a non-empty string')
        if self.repo is not None and not str(self.repo).strip():
            review_print("validation failed: repo is empty")
            raise ValueError('repo must be a non-empty string')
        if self.pull_number is not None and (not isinstance(self.pull_number, int) or self.pull_number <= 0):
            review_print(f"validation failed: pull_number is invalid value={self.pull_number}")
            raise ValueError('pull_number must be a positive integer')

        review_print("request params validated")
        return self

    @field_validator('anthropic_api_key')
    @classmethod
    def validate_anthropic_api_key(cls, v):
        """Validate anthropic_api_key is not empty"""
        if not v or not str(v).strip():
            review_print("validation failed: anthropic_api_key is empty")
            raise ValueError('anthropic_api_key must be a non-empty string')
        review_print("anthropic_api_key present")
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
    request_source = "pr_url" if request.pr_url else "owner/repo/pull_number"
    review_print(f"start pr={pr} user={user['username']} post_comment={request.post_comment} source={request_source}")
    logger.info(f"[review] start {pr} user={user['username']} post_comment={request.post_comment}")

    try:
        # 1. Fetch PR data (always needed — gives us headSha for the cache key + fresh metadata)
        review_print(f"fetching GitHub PR data pr={pr}")
        logger.info(f"[review] fetching PR data for {pr}")
        pr_data = await github_service.get_pr_data(owner, repo, pull_number)
        review_print(
            f"fetched GitHub PR data pr={pr} files={pr_data['files_reviewed']} "
            f"diff_chars={pr_data['total_diff_chars']} head_sha={pr_data['headSha']}"
        )
        logger.info(f"[review] fetched {pr_data['files_reviewed']} files, {pr_data['total_diff_chars']} chars sha={pr_data['headSha']}")

        # 2. Check cache — keyed by exact commit SHA so any new push is a cache miss
        review_text: str
        review_status: str
        inline_comments: list
        from_cache = False

        review_fingerprint = f"{pr_data['headSha']}/{REVIEW_MODEL}/{STRUCTURED_SYSTEM_PROMPT_HASH}"
        lock_key = f"{owner}/{repo}/{pull_number}/{review_fingerprint}"
        review_print(f"checking cache pr={pr} fingerprint={review_fingerprint}")
        lock = _review_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            cached = cache_service.get(owner, repo, pull_number, review_fingerprint)
            if cached:
                review_print(f"cache hit pr={pr} status={cached['status']} inline_comments={len(cached['inlineComments'])}")
                logger.info(f"[review] cache hit for {pr} sha={pr_data['headSha']} model={REVIEW_MODEL} prompt={STRUCTURED_SYSTEM_PROMPT_HASH}")
                review_text = cached["reviewText"]
                review_status = cached["status"]
                inline_comments = cached["inlineComments"]
                from_cache = True
            else:
                review_print(f"cache miss pr={pr}")
                # 3. Build prompt(s), call Claude, and parse structured results.
                if should_split_review(pr_data):
                    review_print(f"calling Claude split-review mode pr={pr} model={REVIEW_MODEL}")
                    logger.info("[review] calling Claude in split-review mode")
                    batch_reviews = []
                    for index, batch in enumerate(build_review_batches(pr_data), start=1):
                        filename = batch[0]["filename"]
                        review_print(f"Claude batch start pr={pr} batch={index} file={filename} files={len(batch)}")
                        user_message = build_user_prompt(pr_data, files=batch, scope=f"file:{filename}")
                        response_text = await claude_review(
                            system_prompt=STRUCTURED_SYSTEM_PROMPT,
                            user_message=user_message,
                            anthropic_api_key=request.anthropic_api_key
                        )
                        batch_reviews.append(parse_structured_review(response_text))
                        review_print(f"Claude batch done pr={pr} batch={index} file={filename}")
                    structured_review = merge_structured_reviews(batch_reviews)
                else:
                    user_message = build_user_prompt(pr_data)

                    review_print(f"calling Claude pr={pr} model={REVIEW_MODEL} prompt_chars={len(user_message)}")
                    logger.info("[review] calling Claude")
                    response_text = await claude_review(
                        system_prompt=STRUCTURED_SYSTEM_PROMPT,
                        user_message=user_message,
                        anthropic_api_key=request.anthropic_api_key
                    )
                    review_print(f"Claude response received pr={pr} response_chars={len(response_text)}")
                    structured_review = parse_structured_review(response_text)

                review_text = render_review_markdown(structured_review)
                review_status = structured_review["status"]
                inline_comments = structured_review["inline_annotations"]

                review_print(f"review parsed pr={pr} status={review_status} inline_comments={len(inline_comments)}")
                logger.info("[review] Claude responded")

                # 5. Store in cache
                cache_service.set(owner, repo, pull_number, review_fingerprint, {
                    "reviewText": review_text,
                    "status": review_status,
                    "inlineComments": inline_comments
                })
                cache_stats = cache_service.stats()
                review_print(f"cached result pr={pr} cache_size={cache_stats['size']}/{cache_stats['maxEntries']}")
                logger.info(f"[review] cached result ({cache_service.stats()['size']}/{cache_service.stats()['maxEntries']} entries)")

        review_print(f"review result pr={pr} status={review_status} inline_comments={len(inline_comments)} cached={from_cache}")
        logger.info(f"[review] status={review_status} inline_comments={len(inline_comments)}")

        # 6. Optionally post to GitHub (always performed even on a cache hit — caller may want the comment)
        comment_posted = False
        review_id = None
        inline_comments_posted = 0

        if request.post_comment:
            review_print(f"posting GitHub review pr={pr} inline_comments={len(inline_comments)}")
            logger.info(f"[review] posting comment to {pr}")
            result = await github_service.post_review(
                owner, repo, pull_number, pr_data["headSha"],
                review_text, inline_comments, pr_data["commentable_lines"]
            )
            comment_posted = True
            review_id = result["review_id"]
            inline_comments_posted = result["inline_comments_posted"]
            review_print(f"posted GitHub review pr={pr} review_id={review_id} inline_comments_posted={inline_comments_posted}")
            logger.info(f"[review] posted review_id={review_id} inline_comments={inline_comments_posted}")
        else:
            review_print(f"skipping GitHub review post pr={pr} post_comment=false")

        duration_ms = int((time.time() - start_time) * 1000)
        review_print(f"done pr={pr} status={review_status} duration_ms={duration_ms} cached={from_cache}")
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
                "context_files": len(pr_data.get("context_files", [])),
                "comment_posted": comment_posted,
                "review_id": review_id,
                "inline_comments_posted": inline_comments_posted,
                "username": user["username"],
                "duration_ms": duration_ms,
                "cached": from_cache,
                "model": REVIEW_MODEL,
                "prompt_hash": STRUCTURED_SYSTEM_PROMPT_HASH,
                "split_review": should_split_review(pr_data),
            },
        }

    except (GitHubServiceError, ClaudeServiceError) as e:
        # Re-raise service errors to be handled by global error handler
        review_print(f"service error pr={pr} code={getattr(e, 'code', 'UNKNOWN')} message={e}")
        raise e
    except Exception as e:
        review_print(f"unexpected error pr={pr} type={type(e).__name__} message={e}")
        logger.error(f"Unexpected error in review_pr: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
