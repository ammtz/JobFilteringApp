"""Unit tests for Job model (generate_hash, no DB)."""
import pytest

from app.models.job import Job


class TestJobGenerateHash:
    def test_url_string_deterministic(self):
        a = Job.generate_hash("https://example.com/job/1")
        b = Job.generate_hash("https://example.com/job/1")
        assert a == b
        assert len(a) == 64
        assert all(c in "0123456789abcdef" for c in a)

    def test_url_string_different_inputs_different_hashes(self):
        a = Job.generate_hash("https://example.com/job/1")
        b = Job.generate_hash("https://example.com/job/2")
        assert a != b

    def test_url_string_normalizes_lowercase(self):
        a = Job.generate_hash("https://Example.COM/job/1")
        b = Job.generate_hash("https://example.com/job/1")
        assert a == b

    def test_url_string_empty_uses_random(self):
        h = Job.generate_hash("")
        assert len(h) == 64
        h2 = Job.generate_hash("")
        assert h != h2  # empty should yield random

    def test_dict_deterministic(self):
        payload = {"title": "Dev", "company": "Acme", "url": "https://a.com", "raw_text": "desc"}
        a = Job.generate_hash(payload)
        b = Job.generate_hash(payload)
        assert a == b
        assert len(a) == 64

    def test_dict_key_order_independent(self):
        p1 = {"url": "https://a.com", "title": "Dev"}
        p2 = {"title": "Dev", "url": "https://a.com"}
        assert Job.generate_hash(p1) == Job.generate_hash(p2)

    def test_dict_empty_values_normalized(self):
        p1 = {"title": "", "url": "https://a.com"}
        p2 = {"title": None, "url": "https://a.com"}
        # Both should produce same hash (empty string vs None normalized)
        assert Job.generate_hash(p1) == Job.generate_hash(p2)
