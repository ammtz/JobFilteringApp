from __future__ import annotations

import enum
import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Float, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class JobStatus(str, enum.Enum):
    new = "new"
    analyzed = "analyzed"
    applied = "applied"


class Job(Base):
    """Single source of truth for jobs table; schema matches migrations 001-004."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Core capture (v1 / extension style)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Bookmarklet / public style extras
    selected_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Analysis (score 0-100 in DB)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="jobstatus"), nullable=False, default=JobStatus.new)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    resume_recommendation: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    downsides: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guidance_3_sentences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Structured parsing
    structured_requirements: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Preference scoring (Embeddings + Vector ELO)
    preference_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @staticmethod
    def generate_hash(url_or_payload: str | dict[str, Any]) -> str:
        """Deterministic hash for dedupe. Accepts URL string (public) or payload dict (v1)."""
        if isinstance(url_or_payload, dict):
            normalized = {k: (v or "") for k, v in sorted(url_or_payload.items())}
            key = json.dumps(normalized, sort_keys=True)
        else:
            key = (url_or_payload or "").strip().lower()
            if not key:
                key = str(uuid.uuid4())
        return hashlib.sha256(key.encode()).hexdigest()
