"""
OpenAI-compatible chat API client. Works with OpenAI or any open-source/local
server that exposes the same API (e.g. Ollama, LiteLLM, vLLM). For local servers,
OPENAI_API_KEY can be empty if the endpoint does not require auth.
"""
import json
from typing import Any, Dict, List

import httpx

from app.core.config import settings


class LLMError(Exception):
    """Raised when the LLM API request or response is invalid."""


def _is_local_base_url(url: str) -> bool:
    if not url:
        return False
    u = url.strip().lower()
    return u.startswith("http://localhost/") or u.startswith("http://127.0.0.1/") or u.startswith("http://localhost:") or u.startswith("http://127.0.0.1:")


def _chat_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OPENAI_API_KEY}"
    elif not _is_local_base_url(settings.OPENAI_BASE_URL):
        raise LLMError("OPENAI_API_KEY is required when using a non-local API base URL")
    return headers


def openai_chat_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(url, headers=_chat_headers(), json=payload, timeout=60)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response format unexpected") from exc

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError("LLM response was not valid JSON") from exc
