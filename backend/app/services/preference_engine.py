"""
Embeddings + Vector ELO preference engine.

On each A/B choice:
  1. Direct ELO update on the two compared jobs (K=32).
  2. Indirect weighted update on all other embedded jobs:
       delta = K * (cosine_sim(job, winner) - cosine_sim(job, loser)) * SPREAD_FACTOR
     This generalises the user's preference to similar-but-uncompared jobs.

Embeddings use sentence-transformers/all-MiniLM-L6-v2 (384-dim, runs on CPU).
Vectors are stored as JSON arrays in jobs.embedding.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.models.job import Job

_MODEL = None  # lazy-loaded singleton


def _embedder():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def _job_text(job: "Job") -> str:
    about = None
    if job.structured_requirements and isinstance(job.structured_requirements, dict):
        about = job.structured_requirements.get("about_summary")
    snippet = about or (job.raw_text or "")[:500]
    return f"{job.title or ''} at {job.company or ''} — {snippet}"


def get_embedding(text: str) -> List[float]:
    vec = _embedder().encode(text, normalize_embeddings=True)
    return vec.tolist()


def cosine_sim(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def ensure_embeddings(jobs: List["Job"], db) -> None:
    """Embed any jobs that are missing an embedding vector, then flush."""
    for job in jobs:
        if job.embedding is None:
            job.embedding = get_embedding(_job_text(job))
    db.flush()


_ELO_START = 1000.0
_K = 32.0
_SPREAD = 0.3  # dampening for indirect updates


def _elo_expected(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def record_preference(
    winner: "Job",
    loser: "Job",
    all_jobs: List["Job"],
    db,
) -> None:
    """
    Run ELO + vector spread for one preference choice, then flush.

    winner / loser must already have embeddings.
    all_jobs is the full list (including winner & loser) to spread to.
    """
    elo_w = winner.preference_score if winner.preference_score is not None else _ELO_START
    elo_l = loser.preference_score if loser.preference_score is not None else _ELO_START

    expected_w = _elo_expected(elo_w, elo_l)
    expected_l = 1.0 - expected_w

    # Direct update
    winner.preference_score = elo_w + _K * (1.0 - expected_w)
    loser.preference_score = elo_l + _K * (0.0 - expected_l)

    # Indirect update — spread to all other embedded jobs
    winner_vec: Optional[List[float]] = winner.embedding
    loser_vec: Optional[List[float]] = loser.embedding

    if winner_vec and loser_vec:
        for job in all_jobs:
            if job.id in (winner.id, loser.id):
                continue
            if job.embedding is None:
                continue
            sim_w = cosine_sim(job.embedding, winner_vec)
            sim_l = cosine_sim(job.embedding, loser_vec)
            delta = _K * (sim_w - sim_l) * _SPREAD
            base = job.preference_score if job.preference_score is not None else _ELO_START
            job.preference_score = base + delta

    db.flush()
