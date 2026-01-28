"""merge_bodypart_and_tnm_image

Revision ID: c26b2d9bfc6b
Revises: add_bodypart_5new, add_tnm_image_table
Create Date: 2026-01-28 23:30:58.655817

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c26b2d9bfc6b'
down_revision = ('add_bodypart_5new', 'add_tnm_image_table')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
