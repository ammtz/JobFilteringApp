"""v0.2 job fields and url dedupe

Revision ID: 004_jobs_v02
Revises: 003_structured_requirements
Create Date: 2026-02-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004_jobs_v02"
down_revision = "003_structured_requirements"
branch_labels = None
depends_on = None


JOBSTATUS = sa.Enum("new", "analyzed", "applied", name="jobstatus")


def upgrade() -> None:
    bind = op.get_bind()
    JOBSTATUS.create(bind, checkfirst=True)

    op.add_column("jobs", sa.Column("selected_text", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("status", JOBSTATUS, server_default="new", nullable=False),
    )
    op.add_column("jobs", sa.Column("guidance_3_sentences", sa.Text(), nullable=True))

    op.execute("UPDATE jobs SET captured_at = created_at WHERE captured_at IS NULL")
    op.execute("UPDATE jobs SET url = CONCAT('urn:job:', id) WHERE url IS NULL OR url = ''")
    op.execute(
        """
        DELETE FROM jobs a
        USING jobs b
        WHERE a.url = b.url
          AND a.ctid < b.ctid
          AND a.url IS NOT NULL
          AND a.url <> ''
        """
    )
    op.execute("UPDATE jobs SET status = 'analyzed' WHERE analyzed_at IS NOT NULL OR score IS NOT NULL")

    op.alter_column("jobs", "url", existing_type=sa.String(length=1000), nullable=False)
    op.create_unique_constraint("uq_jobs_url", "jobs", ["url"])

    op.alter_column(
        "jobs",
        "score",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        postgresql_using="CASE WHEN score IS NULL THEN NULL ELSE ROUND(score * 100)::integer END",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "jobs",
        "score",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        postgresql_using="CASE WHEN score IS NULL THEN NULL ELSE score / 100.0 END",
        existing_nullable=True,
    )
    op.drop_constraint("uq_jobs_url", "jobs", type_="unique")
    op.alter_column("jobs", "url", existing_type=sa.String(length=1000), nullable=True)

    op.drop_column("jobs", "guidance_3_sentences")
    op.drop_column("jobs", "status")
    op.drop_column("jobs", "captured_at")
    op.drop_column("jobs", "selected_text")

    bind = op.get_bind()
    JOBSTATUS.drop(bind, checkfirst=True)
