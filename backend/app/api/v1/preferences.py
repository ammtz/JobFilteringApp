from __future__ import annotations

import random
from uuid import UUID

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app.core.database import get_db
from app.models.job import Job
from app.models.preference import UserABJobPreference
from app.services.preference_engine import ensure_embeddings, record_preference

bp = Blueprint("preferences", __name__)


def _job_summary(job: Job) -> dict:
    about = None
    if job.structured_requirements and isinstance(job.structured_requirements, dict):
        about = job.structured_requirements.get("about_summary")
    return {
        "id": str(job.id),
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "about_summary": about,
        "preference_score": job.preference_score,
    }


@bp.get("/preferences/pair")
def get_pair():
    """Return two jobs to compare, prioritising those with the fewest prior comparisons."""
    with get_db() as db:
        jobs = db.query(Job).all()
        if len(jobs) < 2:
            return jsonify({"detail": "Need at least 2 saved jobs to compare."}), 400

        # Count appearances per job in the preference table
        counts: dict[UUID, int] = {job.id: 0 for job in jobs}
        rows = db.query(
            UserABJobPreference.job_a_id,
            UserABJobPreference.job_b_id,
        ).all()
        for row in rows:
            if row.job_a_id in counts:
                counts[row.job_a_id] += 1
            if row.job_b_id in counts:
                counts[row.job_b_id] += 1

        # Sort by count ascending, break ties randomly
        shuffled = list(jobs)
        random.shuffle(shuffled)
        shuffled.sort(key=lambda j: counts[j.id])

        job_a, job_b = shuffled[0], shuffled[1]

        # Ensure both have embeddings (lazy compute on first use)
        ensure_embeddings([job_a, job_b], db)
        db.commit()

        return jsonify({
            "job_a": _job_summary(job_a),
            "job_b": _job_summary(job_b),
        })


@bp.post("/preferences")
def post_preference():
    """Record a choice and run ELO + vector spread across all jobs."""
    data = request.get_json(silent=True) or {}
    try:
        job_a_id = UUID(data["job_a_id"])
        job_b_id = UUID(data["job_b_id"])
        chosen_id = UUID(data["chosen_job_id"])
    except (KeyError, ValueError):
        return jsonify({"detail": "job_a_id, job_b_id, and chosen_job_id are required UUIDs."}), 400

    if chosen_id not in (job_a_id, job_b_id):
        return jsonify({"detail": "chosen_job_id must be one of job_a_id or job_b_id."}), 400

    rejected_id = job_b_id if chosen_id == job_a_id else job_a_id

    with get_db() as db:
        job_a = db.get(Job, job_a_id)
        job_b = db.get(Job, job_b_id)
        if not job_a or not job_b:
            return jsonify({"detail": "One or both jobs not found."}), 404

        # Ensure all jobs have embeddings before spreading
        all_jobs = db.query(Job).all()
        ensure_embeddings(all_jobs, db)

        winner = job_a if chosen_id == job_a_id else job_b
        loser = job_b if chosen_id == job_a_id else job_a

        # Log the choice
        pref = UserABJobPreference(
            job_a_id=job_a_id,
            job_b_id=job_b_id,
            chosen_job_id=chosen_id,
            rejected_job_id=rejected_id,
        )
        db.add(pref)

        # Run ELO + vector spread
        record_preference(winner, loser, all_jobs, db)
        db.commit()

        return jsonify({
            "preference_id": str(pref.id),
            "winner": {"id": str(winner.id), "preference_score": winner.preference_score},
            "loser": {"id": str(loser.id), "preference_score": loser.preference_score},
        })


@bp.get("/preferences")
def list_preferences():
    """Return the full preference history."""
    with get_db() as db:
        prefs = db.query(UserABJobPreference).order_by(
            UserABJobPreference.created_at.desc()
        ).all()
        return jsonify([
            {
                "id": str(p.id),
                "job_a_id": str(p.job_a_id),
                "job_b_id": str(p.job_b_id),
                "chosen_job_id": str(p.chosen_job_id),
                "rejected_job_id": str(p.rejected_job_id),
                "created_at": p.created_at.isoformat(),
            }
            for p in prefs
        ])
