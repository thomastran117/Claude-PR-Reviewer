"""
Claude AI service for PR reviews
"""

import anthropic
import asyncio

REVIEW_MODEL = "claude-sonnet-4-20250514"

class ClaudeServiceError(Exception):
    """Base exception for Claude service errors"""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

async def review(system_prompt: str, user_message: str, anthropic_api_key: str) -> str:
    """
    Call Claude API for PR review

    Args:
        system_prompt: System prompt for Claude
        user_message: User message with PR data
        anthropic_api_key: Anthropic API key

    Returns:
        Review text from Claude

    Raises:
        ClaudeServiceError: On API errors
    """
    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key, timeout=60.0)

    try:
        try:
            message = await _create_message_with_retries(client, system_prompt, user_message)
        except anthropic.AuthenticationError:
            raise ClaudeServiceError("ANTHROPIC_AUTH", "Anthropic API key is invalid or missing")
        except anthropic.RateLimitError:
            raise ClaudeServiceError("ANTHROPIC_RATE_LIMITED", "Anthropic rate limit hit. Try again shortly.")
        except anthropic.APIConnectionError:
            raise ClaudeServiceError("ANTHROPIC_NETWORK", "Cannot reach Anthropic API")
        except anthropic.APIError as e:
            raise ClaudeServiceError("ANTHROPIC_SERVER_ERROR", f"Anthropic API error: {e.status_code} {e.message}")
        except Exception as e:
            raise ClaudeServiceError("ANTHROPIC_NETWORK", f"Unexpected error calling Anthropic: {str(e)}")
    finally:
        await client.close()

    content = message.content
    if not content:
        raise ClaudeServiceError("ANTHROPIC_UNEXPECTED", "Anthropic returned an unexpected response shape")

    first_block = content[0]
    text = getattr(first_block, "text", None)
    if text is None and isinstance(first_block, dict):
        text = first_block.get("text")

    if not isinstance(text, str):
        raise ClaudeServiceError("ANTHROPIC_UNEXPECTED", "Anthropic returned an unexpected response shape")

    return text.strip()

async def _create_message_with_retries(client, system_prompt: str, user_message: str):
    """Retry transient Anthropic failures with a small bounded backoff."""
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            return await client.messages.create(
                model=REVIEW_MODEL,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APIError):
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(0.5 * (2 ** attempt))
