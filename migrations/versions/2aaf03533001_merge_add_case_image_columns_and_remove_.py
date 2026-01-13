"""merge add_case_image_columns and remove_legacy_qa

Revision ID: 2aaf03533001
Revises: add_case_image_columns, remove_legacy_qa
Create Date: 2026-01-14 00:56:30.489961

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2aaf03533001'
down_revision = ('add_case_image_columns', 'remove_legacy_qa')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
