from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from app.core.config import settings
from app.models.job import Job
from app.services.llm import LLMError, openai_chat_json
from app.services.prompts import build_analyzer_messages

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
BULLET_PREFIX = re.compile(r"^[\s\-*•]+")
WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class AnalyzerResult:
    score: int
    recommended_resume: str
    guidance_3_sentences: str
    analysis_raw: Optional[dict]


class Analyzer(Protocol):
    def analyze(self, job: Job) -> AnalyzerResult:
        ...


def _normalize_text(text: str) -> str:
    lines = [BULLET_PREFIX.sub("", line).strip() for line in text.splitlines()]
    cleaned = " ".join(line for line in lines if line)
    cleaned = WHITESPACE.sub(" ", cleaned).strip()
    return cleaned


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    cleaned = _normalize_text(text)
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return [sentence.strip() for sentence in SENTENCE_SPLIT.split(cleaned) if sentence.strip()]


def _fallback_guidance(job: Job) -> str:
    role = (job.title or "this role").strip()
    return (
        f"Good bet if you want {role}; use the general resume. "
        "It beats other options because you can compare it directly against similar roles with the same criteria. "
        "Downside: the posting is light on specifics, so verify scope before applying."
    )


def _guidance_meets_rules(sentences: list[str]) -> bool:
    if len(sentences) != 3:
        return False
    first, second, third = (s.lower() for s in sentences)
    if "resume" not in first or "use" not in first:
        return False
    if "compare" not in second and "comparison" not in second:
        return False
    if "downside" not in third and "tradeoff" not in third:
        return False
    return True


def ensure_guidance(text: str, job: Job) -> str:
    sentences = _split_sentences(text)
    if _guidance_meets_rules(sentences):
        return " ".join(sentences)
    return _fallback_guidance(job)


def _normalize_score(value: object) -> int:
    try:
        score = int(round(float(value)))
    except Exception:
        score = 0
    return max(0, min(100, score))


def _normalize_resume(value: object) -> str:
    text = str(value or "general").strip().lower()
    text = WHITESPACE.sub(" ", text)
    if not text:
        return "general"
    key = text.replace(" ", "-")
    return key[:32]


def _deterministic_score(seed: str) -> int:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return int(digest[:2], 16) % 101


class StubAnalyzer:
    def analyze(self, job: Job) -> AnalyzerResult:
        score = _deterministic_score(job.url or job.title or "job")
        guidance = _fallback_guidance(job)
        return AnalyzerResult(
            score=score,
            recommended_resume="general",
            guidance_3_sentences=guidance,
            analysis_raw={
                "source": "stub",
                "generated_at": datetime.utcnow().isoformat() + "Z",
            },
        )


class OpenAIAnalyzer:
    def analyze(self, job: Job) -> AnalyzerResult:
        messages = build_analyzer_messages(job)
        result = openai_chat_json(messages)
        if not isinstance(result, dict):
            raise LLMError("OpenAI response missing JSON object")
        score = _normalize_score(result.get("score"))
        recommended_resume = _normalize_resume(result.get("recommended_resume"))
        guidance_text = str(result.get("guidance_3_sentences", ""))
        guidance = ensure_guidance(guidance_text, job)
        return AnalyzerResult(
            score=score,
            recommended_resume=recommended_resume,
            guidance_3_sentences=guidance,
            analysis_raw=result,
        )


def get_analyzer() -> Analyzer:
    if settings.OPENAI_API_KEY:
        return OpenAIAnalyzer()
    return StubAnalyzer()
