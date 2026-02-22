"""initial jobs table

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('raw_data', postgresql.JSON(), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('company', sa.String(500), nullable=True),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('url', sa.String(1000), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('analysis', postgresql.JSON(), nullable=True),
        sa.Column('resume_recommendation', sa.String(500), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('downsides', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_jobs_job_hash', 'jobs', ['job_hash'])


def downgrade() -> None:
    op.drop_index('ix_jobs_job_hash', table_name='jobs')
    op.drop_table('jobs')
