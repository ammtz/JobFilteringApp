"""add structured requirements to jobs

Revision ID: 003_structured_requirements
Revises: 002_resume
Create Date: 2026-01-27 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_structured_requirements'
down_revision = '002_resume'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('structured_requirements', postgresql.JSON(), nullable=True))
    op.add_column('jobs', sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'parsed_at')
    op.drop_column('jobs', 'structured_requirements')
