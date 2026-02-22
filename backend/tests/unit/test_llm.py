"""Unit tests for LLM module (local URL detection, no network)."""
import pytest

from app.services.llm import _is_local_base_url


class TestIsLocalBaseUrl:
    def test_localhost_http(self):
        assert _is_local_base_url("http://localhost/") is True
        assert _is_local_base_url("http://localhost:8080/v1") is True
        assert _is_local_base_url("http://localhost:11434/v1") is True

    def test_127_0_0_1(self):
        assert _is_local_base_url("http://127.0.0.1/") is True
        assert _is_local_base_url("http://127.0.0.1:8000") is True

    def test_non_local(self):
        assert _is_local_base_url("https://api.openai.com/v1") is False
        assert _is_local_base_url("https://example.com") is False

    def test_empty_or_none(self):
        assert _is_local_base_url("") is False
        assert _is_local_base_url(None) is False
