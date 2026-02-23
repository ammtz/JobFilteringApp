"""
Anthropic Claude API client.

Requires ANTHROPIC_API_KEY set in environment (or .env file).
Optionally set ANTHROPIC_MODEL to override the default (claude-opus-4-6).
"""
import json
import re
from typing import Any, Dict, List

import anthropic

from app.core.config import settings

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


class LLMError(Exception):
    """Raised when the LLM API request or response is invalid."""


def _strip_code_fence(text: str) -> str:
    """Remove markdown code fences if Claude wraps JSON in them."""
    match = _CODE_FENCE_RE.match(text.strip())
    return match.group(1).strip() if match else text.strip()


def claude_chat_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Send a list of messages to Claude and return the parsed JSON response.

    A message with role "system" is lifted to Claude's top-level system param.
    Uses streaming with get_final_message() to avoid timeout issues on large inputs.

    Args:
        messages: List of {"role": "system"|"user"|"assistant", "content": str}

    Returns:
        Parsed JSON dict from Claude's text response.

    Raises:
        LLMError: API call failed, or response was not valid JSON.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY is required for LLM features")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    system: str | None = None
    api_messages: List[Dict[str, str]] = []
    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
        else:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    create_kwargs: Dict[str, Any] = {
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "messages": api_messages,
    }
    if system:
        create_kwargs["system"] = system

    try:
        with client.messages.stream(**create_kwargs) as stream:
            response = stream.get_final_message()
    except anthropic.APIError as exc:
        raise LLMError(f"Claude API request failed: {exc}") from exc
    except UnicodeEncodeError as exc:
        raise LLMError(
            f"ANTHROPIC_API_KEY contains non-ASCII characters (e.g. an em dash instead of a hyphen). "
            f"Re-copy it from console.anthropic.com. Detail: {exc}"
        ) from exc

    text_content: str | None = None
    for block in response.content:
        if block.type == "text":
            text_content = block.text
            break

    if text_content is None:
        raise LLMError("Claude response contained no text block")

    cleaned = _strip_code_fence(text_content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Claude response was not valid JSON: {cleaned[:300]}") from exc