"""Add BodyPart enum values: UPPER_GASTROINTESTINAL, LOWER_GASTROINTESTINAL, MALE_GENITAL, SOFT_TISSUE, BRAIN_SPINE

Revision ID: add_bodypart_5new
Revises: 8c81a73b2138
Create Date: 2026-01-24

Run this on Vercel/Neon Postgres so the edit-case body part dropdown and DB stay in sync.
After deploying, run: flask db upgrade (or your Vercel build step that runs migrations).
"""
from alembic import op


revision = 'add_bodypart_5new'
down_revision = '8c81a73b2138'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL: add new values to the bodypart enum (type name from existing migrations)
    # Each ADD VALUE is run separately; duplicate value would error on re-run.
    op.execute("ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'UPPER_GASTROINTESTINAL'")
    op.execute("ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'LOWER_GASTROINTESTINAL'")
    op.execute("ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'MALE_GENITAL'")
    op.execute("ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'SOFT_TISSUE'")
    op.execute("ALTER TYPE bodypart ADD VALUE IF NOT EXISTS 'BRAIN_SPINE'")


def downgrade():
    # PostgreSQL does not support removing enum values easily; leave as no-op.
    # To revert, you would need to recreate the type and column.
    pass
