from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from flask import Blueprint, jsonify, request

from app.core.database import get_db
from app.models.job import Job
from app.models.resume import Resume
from app.services.llm import LLMError, openai_chat_json

bp = Blueprint("cull", __name__)


def _get_latest_resume(db):
    resume = db.query(Resume).order_by(Resume.updated_at.desc()).first()
    if not resume:
        return None, (jsonify({"detail": "No resume found. Upload a resume first."}), 400)
    return resume, None


@bp.post("/resume")
def set_resume():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"detail": "Request body must be JSON"}), 400

    text = data.get("text", "")
    if not text or not text.strip():
        return jsonify({"detail": "resume text must not be empty"}), 422
    text = text.strip()
    if len(text) > 200000:
        return jsonify({"detail": "resume text must be 200,000 characters or fewer"}), 422

    with get_db() as db:
        resume = db.query(Resume).order_by(Resume.updated_at.desc()).first()
        if resume:
            resume.raw_text = text
        else:
            resume = Resume(raw_text=text)
            db.add(resume)
        db.commit()
        db.refresh(resume)
        return jsonify({
            "id": str(resume.id),
            "updated_at": resume.updated_at.isoformat(),
            "length": len(resume.raw_text),
        })


@bp.get("/resume")
def get_resume():
    with get_db() as db:
        resume, err = _get_latest_resume(db)
        if err:
            return err
        return jsonify({
            "id": str(resume.id),
            "updated_at": resume.updated_at.isoformat(),
            "length": len(resume.raw_text),
        })


@bp.post("/cull")
def begin_cull():
    data = request.get_json(silent=True) or {}
    job_ids = data.get("job_ids")
    top_n = data.get("top_n", 10)

    if not isinstance(top_n, int) or top_n < 1 or top_n > 50:
        return jsonify({"detail": "top_n must be between 1 and 50"}), 422

    with get_db() as db:
        resume, err = _get_latest_resume(db)
        if err:
            return err

        query = db.query(Job)
        if job_ids is not None:
            if len(job_ids) == 0:
                return jsonify({"top_jobs": []})
            query = query.filter(Job.id.in_([UUID(j) for j in job_ids]))
        jobs = query.order_by(Job.created_at.desc()).all()
        if not jobs:
            return jsonify({"top_jobs": []})

        job_payload = [
            {
                "job_id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "url": job.url,
                "raw_text": (job.raw_text or "")[:3000],
            }
            for job in jobs
        ]

        system_prompt = (
            "You are ranking jobs for FIT only. Ignore location, salary, and prestige. "
            "Given a resume and job postings, score fit from 0-100 and provide 1-2 sentence reasoning per job. "
            "Return ONLY valid JSON."
        )
        user_prompt = {
            "resume": resume.raw_text,
            "jobs": job_payload,
            "top_n": top_n,
            "output_format": {
                "ranked": [{"job_id": "uuid", "fit_score": 0, "reasoning": "short rationale"}],
                "top_10": ["uuid"],
            },
        }

        try:
            result = openai_chat_json([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"JSON input:\n{json.dumps(user_prompt)}"},
            ])
        except LLMError as exc:
            return jsonify({"detail": str(exc)}), 502

        ranked = result.get("ranked", []) if isinstance(result, dict) else []
        if not isinstance(ranked, list):
            return jsonify({"detail": "LLM response missing 'ranked' list"}), 502

        scored: dict[UUID, dict] = {}
        for item in ranked:
            try:
                job_id = UUID(item.get("job_id"))
                score = float(item.get("fit_score", 0))
                reasoning = str(item.get("reasoning", ""))
            except Exception:
                continue
            scored[job_id] = {"score": score, "reasoning": reasoning}

        now = datetime.now(timezone.utc)
        for job in jobs:
            if job.id in scored:
                raw_score = scored[job.id]["score"]
                job.score = max(0, min(100, int(round(raw_score))))
                job.reasoning = scored[job.id]["reasoning"]
                job.resume_recommendation = "Primary resume"
                job.analysis = {"fit_score": raw_score, "reasoning": scored[job.id]["reasoning"]}
                job.analyzed_at = now

        db.commit()

        top_sorted = sorted(
            [
                {
                    "job_id": str(job.id),
                    "score": scored[job.id]["score"],
                    "reasoning": scored[job.id]["reasoning"],
                }
                for job in jobs
                if job.id in scored
            ],
            key=lambda x: x["score"],
            reverse=True,
        )
        return jsonify({"top_jobs": top_sorted[:max(1, min(top_n, 50))]})
