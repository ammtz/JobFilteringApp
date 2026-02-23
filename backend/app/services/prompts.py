from __future__ import annotations

import json
from typing import Dict, List

from app.models.job import Job

ANALYZER_SYSTEM_PROMPT = (
    "You are a job hunt analyst. You must return strict JSON with the exact keys: "
    "score, recommended_resume, guidance_3_sentences."
)

ANALYZER_USER_TEMPLATE = (
    "Given the job data below, respond with JSON only. "
    "Constraints: "
    "score must be an integer 0-100. "
    "recommended_resume must be a short key string (no spaces, 1-3 words max). "
    "guidance_3_sentences must be exactly three sentences, no bullets. "
    "Sentence 1: Good bet + which resume variant to use. "
    "Sentence 2: Why it beats other options, explicitly mention comparison capability. "
    "Sentence 3: One clear downside/tradeoff (the 'shit sandwich').\n\n"
    "Job JSON:\n{job_json}"
)


BATCH_SORT_SYSTEM_PROMPT = (
    "You are a job analyst. The candidate's resume is provided. "
    "Given a JSON array of job postings, return a JSON array (same length, same job_ids) "
    "with one object per job. Each object must have exactly these keys: "
    "job_id, about_summary, experience_requirements, expertise_requirements, "
    "business_cultural_requirements, sponsorship_requirements, work_location_requirements, "
    "education_requirements (all strings or null), "
    "score (integer 0-100: how well the candidate's resume fits this specific role), "
    "resume_key (short lowercase slug, 1-3 words, no spaces), "
    "guidance_3_sentences (exactly 3 sentences: "
    "#1 good bet + which resume variant to use; "
    "#2 why it beats other options, mention comparison; "
    "#3 one clear downside or tradeoff). "
    "Return ONLY the JSON array, no other text."
)


def build_batch_sort_messages(
    resume_text: str, jobs: List[Dict]
) -> List[Dict[str, str]]:
    """Build messages for a batch sort+score call covering up to 20 jobs at once."""
    import json as _json
    user_content = (
        f"Candidate resume (use this to score fit for each job):\n{resume_text[:5000]}\n\n"
        f"Jobs to analyse:\n{_json.dumps(jobs, ensure_ascii=True)}"
    )
    return [
        {"role": "system", "content": BATCH_SORT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_analyzer_messages(job: Job) -> List[Dict[str, str]]:
    job_payload = {
        "url": job.url,
        "title": job.title,
        "selected_text": job.selected_text,
        "raw_text": job.raw_text,
        "captured_at": job.captured_at.isoformat(),
    }
    return [
        {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": ANALYZER_USER_TEMPLATE.format(job_json=json.dumps(job_payload, ensure_ascii=True)),
        },
    ]
