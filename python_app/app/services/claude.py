"""
Claude AI service for PR reviews
"""

import anthropic
from typing import Optional

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
    client = anthropic.Anthropic(api_key=anthropic_api_key)

    try:
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
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

    content = message.content
    if not content or not isinstance(content[0], anthropic.TextBlock):
        raise ClaudeServiceError("ANTHROPIC_UNEXPECTED", "Anthropic returned an unexpected response shape")

    text = content[0].text
    if not isinstance(text, str):
        raise ClaudeServiceError("ANTHROPIC_UNEXPECTED", "Anthropic returned an unexpected response shape")

    return text.strip()