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
