from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from uuid import UUID

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.job import Job
from app.services.job_parser import parse_job_description

bp = Blueprint("jobs", __name__)

REQUIRED_STRUCTURED_FIELDS = [
    "about_summary",
    "experience_requirements",
    "expertise_requirements",
    "business_cultural_requirements",
    "sponsorship_requirements",
    "work_location_requirements",
    "education_requirements",
]

PLACEHOLDER_TEXT = "x, y, z"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt(dt):
    return dt.isoformat() if dt else None


def _normalize_json_field(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"items": value}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"_raw": value}
    return {"_raw": str(value)}


def _is_incomplete_structured(structured) -> bool:
    if not structured or not isinstance(structured, dict):
        return True
    for field in REQUIRED_STRUCTURED_FIELDS:
        value = structured.get(field)
        if not value or not str(value).strip():
            return True
        if str(value).strip().lower() == PLACEHOLDER_TEXT:
            return True
    return False


def _fill_placeholder_fields(structured: dict) -> dict:
    filled = dict(structured or {})
    for field in REQUIRED_STRUCTURED_FIELDS:
        value = filled.get(field)
        if not value or not str(value).strip():
            filled[field] = PLACEHOLDER_TEXT
    return filled


def _job_base_fields(job: Job) -> dict:
    return {
        "id": str(job.id),
        "job_hash": job.job_hash,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "score": job.score,
        "resume_recommendation": job.resume_recommendation,
        "reasoning": job.reasoning,
        "downsides": job.downsides,
        "created_at": _dt(job.created_at),
        "analyzed_at": _dt(job.analyzed_at),
        "structured_requirements": _normalize_json_field(job.structured_requirements),
        "parsed_at": _dt(job.parsed_at),
    }


def _is_unique_url_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return "uq_jobs_url" in str(exc)
    if getattr(orig, "pgcode", None) != "23505":
        return False
    diag = getattr(orig, "diag", None)
    return diag is not None and getattr(diag, "constraint_name", None) == "uq_jobs_url"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.post("/ingest")
def ingest_job():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"detail": "Request body must be JSON"}), 400

    raw_text = data.get("raw_text", "")
    if not raw_text or not raw_text.strip():
        return jsonify({"detail": "raw_text must not be empty"}), 422
    raw_text = raw_text.strip()
    if len(raw_text) > 50000:
        return jsonify({"detail": "raw_text must be 50,000 characters or fewer"}), 422

    try:
        job_dict = {
            "title": data.get("title") or "",
            "company": data.get("company") or "",
            "location": data.get("location") or "",
            "url": data.get("url") or "",
            "raw_text": raw_text,
        }
        job_hash = Job.generate_hash(job_dict)

        with get_db() as db:
            existing = db.query(Job).filter(Job.job_hash == job_hash).first()
            if existing:
                resp = _job_base_fields(existing)
                resp["is_new"] = False
                return jsonify(resp)

            url = (data.get("url") or "").strip() or f"urn:job:{job_hash}"
            new_job = Job(
                job_hash=job_hash,
                raw_text=raw_text,
                raw_data=data.get("raw_data"),
                title=data.get("title"),
                company=data.get("company"),
                location=data.get("location"),
                url=url,
                captured_at=datetime.now(timezone.utc),
            )
            db.add(new_job)
            try:
                db.commit()
                db.refresh(new_job)
                resp = _job_base_fields(new_job)
                resp["is_new"] = True
                return jsonify(resp), 201
            except IntegrityError as exc:
                db.rollback()
                if _is_unique_url_violation(exc):
                    # URL collision — use URN fallback
                    new_job_retry = Job(
                        job_hash=job_hash,
                        raw_text=raw_text,
                        raw_data=data.get("raw_data"),
                        title=data.get("title"),
                        company=data.get("company"),
                        location=data.get("location"),
                        url=f"urn:job:{job_hash}",
                        captured_at=datetime.now(timezone.utc),
                    )
                    db.add(new_job_retry)
                    try:
                        db.commit()
                        db.refresh(new_job_retry)
                        resp = _job_base_fields(new_job_retry)
                        resp["is_new"] = True
                        return jsonify(resp), 201
                    except IntegrityError:
                        db.rollback()
                        existing = db.query(Job).filter(Job.job_hash == job_hash).first()
                        if existing:
                            resp = _job_base_fields(existing)
                            resp["is_new"] = False
                            return jsonify(resp)
                        raise
                existing = db.query(Job).filter(Job.job_hash == job_hash).first()
                if existing:
                    resp = _job_base_fields(existing)
                    resp["is_new"] = False
                    return jsonify(resp)
                raise
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"detail": f"Ingest failed: {type(exc).__name__}: {exc}"}), 500


@bp.get("/jobs")
def get_jobs():
    analyzed_only = request.args.get("analyzed_only", "false").lower() == "true"
    try:
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"detail": "limit and offset must be integers"}), 422
    if not (1 <= limit <= 500):
        return jsonify({"detail": "limit must be between 1 and 500"}), 422
    if offset < 0:
        return jsonify({"detail": "offset must be >= 0"}), 422

    with get_db() as db:
        query = db.query(Job)
        if analyzed_only:
            query = query.filter(Job.analyzed_at.isnot(None))
        jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
        return jsonify([_job_base_fields(j) for j in jobs])


@bp.get("/jobs/<uuid:job_id>")
def get_job(job_id):
    with get_db() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return jsonify({"detail": "Job not found"}), 404
        base = _job_base_fields(job)
        base.update({
            "raw_text": job.raw_text,
            "raw_data": _normalize_json_field(job.raw_data),
            "analysis": _normalize_json_field(job.analysis),
        })
        return jsonify(base)


@bp.patch("/jobs/<uuid:job_id>")
def update_job(job_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"detail": "Request body must be JSON"}), 400

    if "raw_text" in data and data["raw_text"] is not None:
        rt = data["raw_text"]
        if not rt.strip():
            return jsonify({"detail": "raw_text must not be empty when provided"}), 422
        if len(rt.strip()) > 50000:
            return jsonify({"detail": "raw_text must be 50,000 characters or fewer"}), 422
        data["raw_text"] = rt.strip()

    with get_db() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return jsonify({"detail": "Job not found"}), 404

        for field in ("title", "company", "location", "url", "raw_data"):
            if field in data and data[field] is not None:
                setattr(job, field, data[field])
        if "raw_text" in data and data["raw_text"] is not None:
            job.raw_text = data["raw_text"]
            job.structured_requirements = None
            job.parsed_at = None

        job.job_hash = Job.generate_hash({
            "title": job.title or "",
            "company": job.company or "",
            "location": job.location or "",
            "url": job.url or "",
            "raw_text": job.raw_text or "",
        })

        try:
            db.commit()
            db.refresh(job)
        except IntegrityError:
            db.rollback()
            return jsonify({"detail": "Update would duplicate an existing job."}), 409

        base = _job_base_fields(job)
        base.update({
            "raw_text": job.raw_text,
            "raw_data": _normalize_json_field(job.raw_data),
            "analysis": _normalize_json_field(job.analysis),
        })
        return jsonify(base)


@bp.delete("/jobs/<uuid:job_id>")
def delete_job(job_id):
    with get_db() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return jsonify({"detail": "Job not found"}), 404
        db.delete(job)
        db.commit()
        return jsonify({"deleted": True, "job_id": str(job_id)})


@bp.post("/parse")
def parse_jobs():
    data = request.get_json(silent=True) or {}
    job_ids = data.get("job_ids")
    force = data.get("force", False)

    try:
        with get_db() as db:
            total = db.query(Job).count()
            if total == 0:
                return jsonify({"message": "No jobs in database. Capture some jobs first.", "parsed_count": 0})

            query = db.query(Job)
            if job_ids is not None:
                if len(job_ids) == 0:
                    return jsonify({"message": "No job_ids provided; parsed 0 job(s)", "parsed_count": 0})
                query = query.filter(Job.id.in_([UUID(j) for j in job_ids]))
            jobs = query.all()

            if not jobs:
                return jsonify({"message": "No jobs found.", "parsed_count": 0})

            to_parse = [j for j in jobs if force or _is_incomplete_structured(j.structured_requirements)]
            if not to_parse:
                return jsonify({"message": "All jobs already have structured requirements.", "parsed_count": 0})

            parsed_count = 0
            errors = []
            for job in to_parse:
                try:
                    structured = parse_job_description(
                        raw_text=job.raw_text, title=job.title, company=job.company
                    )
                    structured = _fill_placeholder_fields(structured)
                    job.structured_requirements = structured
                    job.parsed_at = datetime.now(timezone.utc)
                    parsed_count += 1
                except Exception as exc:
                    errors.append(f"Error parsing job {job.id}: {exc}")

            db.commit()
            msg = f"Parsed {parsed_count} job(s)"
            if errors:
                msg += f". {len(errors)} error(s) occurred."
            return jsonify({"message": msg, "parsed_count": parsed_count})

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"detail": f"Parse failed: {exc}"}), 500


@bp.post("/analyze")
def analyze_jobs():
    from app.models.job import JobStatus
    from app.services.analyzer import get_analyzer
    from app.services.llm import LLMError

    data = request.get_json(silent=True) or {}
    job_ids = data.get("job_ids")

    with get_db() as db:
        query = db.query(Job)
        if job_ids is not None:
            if len(job_ids) == 0:
                return jsonify({"message": "No job_ids provided; analyzed 0 job(s)", "analyzed_count": 0})
            query = query.filter(Job.id.in_([UUID(j) for j in job_ids]))
        else:
            query = query.filter(Job.analyzed_at.is_(None))

        jobs = query.all()
        if not jobs:
            return jsonify({"message": "No jobs to analyze", "analyzed_count": 0})

        analyzer = get_analyzer()
        now = datetime.now(timezone.utc)
        analyzed_count = 0
        for job in jobs:
            try:
                result = analyzer.analyze(job)
            except LLMError as exc:
                return jsonify({"detail": str(exc)}), 502
            job.score = result.score
            job.resume_recommendation = result.recommended_resume
            job.guidance_3_sentences = result.guidance_3_sentences
            job.analysis = result.analysis_raw
            job.status = JobStatus.analyzed
            job.analyzed_at = now
            analyzed_count += 1

        db.commit()
        return jsonify({"message": f"Analyzed {analyzed_count} job(s)", "analyzed_count": analyzed_count})
