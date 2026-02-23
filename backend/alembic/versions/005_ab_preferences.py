"""add A/B preference table and job preference/embedding columns

Revision ID: 005_ab_preferences
Revises: 004_jobs_v02
Create Date: 2026-02-22 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_ab_preferences"
down_revision = "004_jobs_v02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New columns on jobs
    op.add_column("jobs", sa.Column("preference_score", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("embedding", postgresql.JSON(), nullable=True))

    # Preference comparison log
    op.create_table(
        "user_ab_job_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chosen_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rejected_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_pref_job_a", "user_ab_job_preferences", ["job_a_id"])
    op.create_index("ix_pref_job_b", "user_ab_job_preferences", ["job_b_id"])


def downgrade() -> None:
    op.drop_index("ix_pref_job_b", table_name="user_ab_job_preferences")
    op.drop_index("ix_pref_job_a", table_name="user_ab_job_preferences")
    op.drop_table("user_ab_job_preferences")
    op.drop_column("jobs", "embedding")
    op.drop_column("jobs", "preference_score")
