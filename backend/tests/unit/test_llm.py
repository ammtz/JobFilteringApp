"""Unit tests for the LLM module (no network calls)."""
import pytest

from app.services.llm import LLMError, _strip_code_fence


class TestStripCodeFence:
    def test_plain_json_unchanged(self):
        raw = '{"key": "value"}'
        assert _strip_code_fence(raw) == raw

    def test_strips_json_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        assert _strip_code_fence(raw) == '{"key": "value"}'

    def test_strips_generic_fence(self):
        raw = '```\n{"key": "value"}\n```'
        assert _strip_code_fence(raw) == '{"key": "value"}'

    def test_leading_trailing_whitespace(self):
        raw = '  ```json\n{"key": 1}\n```  '
        assert _strip_code_fence(raw) == '{"key": 1}'


class TestClaudeChatJsonNoKey:
    def test_raises_when_no_api_key(self, monkeypatch):
        from app.core import config
        monkeypatch.setattr(config.settings, "ANTHROPIC_API_KEY", None)

        from app.services.llm import claude_chat_json
        with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
            claude_chat_json([{"role": "user", "content": "hello"}])
