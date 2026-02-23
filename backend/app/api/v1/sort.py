from __future__ import annotations

import traceback
from datetime import datetime, timezone
from uuid import UUID

from flask import Blueprint, jsonify, request

from app.core.config import settings
from app.core.database import get_db
from app.models.job import Job, JobStatus
from app.models.resume import Resume
from app.services.llm import LLMError, claude_chat_json
from app.services.prompts import build_batch_sort_messages

bp = Blueprint("sort", __name__)

_BATCH_SIZE = 20  # max jobs per Claude call regardless of MAX_BATCH_JOBS


def _get_latest_resume(db):
    resume = db.query(Resume).order_by(Resume.updated_at.desc()).first()
    if not resume:
        return None, (jsonify({"detail": "No resume found. Upload a resume first."}), 400)
    return resume, None


def _normalize_score(value) -> int:
    try:
        s = int(round(float(value)))
    except Exception:
        s = 0
    return max(0, min(100, s))


# ---------------------------------------------------------------------------
# POST /api/v1/sort
# ---------------------------------------------------------------------------

@bp.post("/sort")
def sort_jobs():
    """Batch parse + score up to MAX_BATCH_JOBS jobs in one Claude call per batch."""
    data = request.get_json(silent=True) or {}
    job_ids = data.get("job_ids")

    try:
        with get_db() as db:
            resume, err = _get_latest_resume(db)
            if err:
                return err

            query = db.query(Job)
            if job_ids is not None:
                if len(job_ids) == 0:
                    return jsonify({"message": "No job_ids provided; sorted 0 job(s)", "sorted_count": 0})
                query = query.filter(Job.id.in_([UUID(j) for j in job_ids]))

            # Only process jobs not yet analysed
            jobs = query.filter(Job.analyzed_at.is_(None)).all()

            if not jobs:
                return jsonify({"message": "All jobs already sorted.", "sorted_count": 0})

            if len(jobs) > settings.MAX_BATCH_JOBS:
                return jsonify({
                    "detail": (
                        f"Batch too large: {len(jobs)} unsorted jobs. "
                        f"Select ≤{settings.MAX_BATCH_JOBS} at a time, or raise MAX_BATCH_JOBS in .env."
                    )
                }), 422

            now = datetime.now(timezone.utc)
            sorted_count = 0
            errors = []

            # Process in sub-batches of up to _BATCH_SIZE
            for batch_start in range(0, len(jobs), _BATCH_SIZE):
                batch = jobs[batch_start: batch_start + _BATCH_SIZE]
                job_payloads = [
                    {
                        "job_id": str(job.id),
                        "title": job.title or "",
                        "company": job.company or "",
                        "raw_text": (job.raw_text or "")[:3000],
                    }
                    for job in batch
                ]

                try:
                    messages = build_batch_sort_messages(resume.raw_text, job_payloads)
                    results = claude_chat_json(messages)
                except LLMError as exc:
                    return jsonify({"detail": str(exc)}), 502

                if not isinstance(results, list):
                    return jsonify({"detail": "Claude returned unexpected format (expected JSON array)"}), 502

                # Index results by job_id for fast lookup
                result_map = {}
                for item in results:
                    if isinstance(item, dict) and "job_id" in item:
                        result_map[item["job_id"]] = item

                for job in batch:
                    item = result_map.get(str(job.id))
                    if not item:
                        errors.append(f"No result returned for job {job.id}")
                        continue

                    structured = {
                        "about_summary": item.get("about_summary"),
                        "experience_requirements": item.get("experience_requirements"),
                        "expertise_requirements": item.get("expertise_requirements"),
                        "business_cultural_requirements": item.get("business_cultural_requirements"),
                        "sponsorship_requirements": item.get("sponsorship_requirements"),
                        "work_location_requirements": item.get("work_location_requirements"),
                        "education_requirements": item.get("education_requirements"),
                    }
                    job.structured_requirements = structured
                    job.parsed_at = now
                    job.score = _normalize_score(item.get("score", 0))
                    job.resume_recommendation = str(item.get("resume_key") or "general")[:32]
                    job.guidance_3_sentences = str(item.get("guidance_3_sentences") or "")
                    job.analysis = {"source": "batch_sort", "raw": item}
                    job.status = JobStatus.analyzed
                    job.analyzed_at = now
                    sorted_count += 1

            db.commit()

            msg = f"Sorted {sorted_count} job(s)."
            if errors:
                msg += f" {len(errors)} job(s) had no result from Claude."
            return jsonify({"message": msg, "sorted_count": sorted_count})

    except Exception:
        traceback.print_exc()
        return jsonify({"detail": "Sort failed. Check server logs."}), 500


# ---------------------------------------------------------------------------
# GET /api/v1/rank
# ---------------------------------------------------------------------------

@bp.get("/rank")
def rank_jobs():
    """Pure-backend ranking: blend LLM score + ELO preference_score, return 1,2,3... list."""
    with get_db() as db:
        jobs = db.query(Job).filter(Job.analyzed_at.isnot(None)).all()

        if not jobs:
            return jsonify({"detail": "No sorted jobs yet. Run Sort Things first."}), 400

        # Normalise ELO to 0-100
        elo_scores = [j.preference_score for j in jobs if j.preference_score is not None]
        if len(elo_scores) >= 2:
            elo_min, elo_max = min(elo_scores), max(elo_scores)
            elo_range = elo_max - elo_min
        else:
            elo_min, elo_max, elo_range = 0.0, 0.0, 0.0

        def _elo_norm(ps) -> float:
            if ps is None or elo_range == 0:
                return 50.0
            return (ps - elo_min) / elo_range * 100.0

        ranked_jobs = []
        for job in jobs:
            llm = job.score if job.score is not None else None
            elo = _elo_norm(job.preference_score) if job.preference_score is not None else None

            if llm is not None and elo is not None:
                combined = 0.6 * llm + 0.4 * elo
            elif llm is not None:
                combined = float(llm)
            elif elo is not None:
                combined = elo
            else:
                combined = 0.0

            ranked_jobs.append({
                "job_id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "score": job.score,
                "preference_score": job.preference_score,
                "combined_score": round(combined, 2),
                "guidance_3_sentences": job.guidance_3_sentences,
                "resume_recommendation": job.resume_recommendation,
                "url": job.url,
            })

        ranked_jobs.sort(key=lambda x: x["combined_score"], reverse=True)
        for i, entry in enumerate(ranked_jobs, start=1):
            entry["rank"] = i

        return jsonify({"ranked": ranked_jobs})
