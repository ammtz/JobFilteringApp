"""
Integration tests for v1 API and app. Use rolling-back DB session (conftest); LLM calls are mocked.
Requires Postgres DATABASE_URL.
"""
from unittest.mock import patch

import pytest


class TestApp:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.get_json() == {"status": "healthy"}

    def test_root(self, client):
        r = client.get("/")
        assert r.status_code in (200, 404)  # 200 when frontend is mounted


class TestV1API:
    def test_v1_ingest_and_list(self, client):
        payload = {
            "raw_text": "Backend engineer role. Python and Flask.",
            "title": "Backend Engineer",
            "company": "TestCo",
            "url": "https://example.com/job/v1-test-1",
        }
        r = client.post("/api/v1/ingest", json=payload)
        assert r.status_code in (200, 201)
        data = r.get_json()
        assert data["title"] == payload["title"]
        assert data.get("is_new") in (True, False)

        r2 = client.get("/api/v1/jobs?limit=5")
        assert r2.status_code == 200
        jobs = r2.get_json()
        assert any(j.get("url") == payload["url"] for j in jobs)

    def test_v1_resume_set_and_get(self, client):
        text = "My resume text for testing."
        r = client.post("/api/v1/resume", json={"text": text})
        assert r.status_code == 200
        assert r.get_json()["length"] == len(text)

        r2 = client.get("/api/v1/resume")
        assert r2.status_code == 200
        assert r2.get_json()["length"] == len(text)

    @patch("app.api.v1.cull.openai_chat_json")
    def test_v1_cull_returns_top_jobs(self, mock_llm, client):
        # Setup: one resume, one job
        client.post("/api/v1/resume", json={"text": "Experienced Python developer."})
        client.post("/api/v1/ingest", json={
            "raw_text": "Python and Flask role.",
            "title": "Python Dev",
            "url": "https://example.com/cull-test-1",
        })

        # Get the saved job id
        r_jobs = client.get("/api/v1/jobs?limit=1")
        assert r_jobs.status_code == 200
        jobs = r_jobs.get_json()
        if not jobs:
            pytest.skip("No job to cull")
        job_id = jobs[0]["id"]

        mock_llm.return_value = {
            "ranked": [
                {"job_id": job_id, "fit_score": 85, "reasoning": "Good fit."},
            ],
        }

        r = client.post("/api/v1/cull", json={"job_ids": [job_id], "top_n": 5})
        assert r.status_code == 200
        data = r.get_json()
        assert "top_jobs" in data
        assert len(data["top_jobs"]) >= 1
        assert data["top_jobs"][0]["score"] == 85.0
        assert data["top_jobs"][0]["reasoning"] == "Good fit."

    def test_v1_cull_422_invalid_top_n(self, client):
        client.post("/api/v1/resume", json={"text": "Resume."})
        r = client.post("/api/v1/cull", json={"top_n": 0})
        assert r.status_code == 422
        r2 = client.post("/api/v1/cull", json={"top_n": 100})
        assert r2.status_code == 422
