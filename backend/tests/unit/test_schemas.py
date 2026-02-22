"""Unit tests for API request/response schemas (validation)."""
import pytest
from pydantic import ValidationError

from app.api.v1.cull import CullRequest


class TestCullRequest:
    def test_top_n_default(self):
        r = CullRequest()
        assert r.top_n == 10

    def test_top_n_valid_range(self):
        r = CullRequest(top_n=1)
        assert r.top_n == 1
        r = CullRequest(top_n=50)
        assert r.top_n == 50

    def test_top_n_below_one_raises(self):
        with pytest.raises(ValidationError):
            CullRequest(top_n=0)
        with pytest.raises(ValidationError):
            CullRequest(top_n=-1)

    def test_top_n_above_50_raises(self):
        with pytest.raises(ValidationError):
            CullRequest(top_n=51)
