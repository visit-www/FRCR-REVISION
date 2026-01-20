"""merge_forum_enhancement

Revision ID: 7cde52816eaa
Revises: forum_enhancement_cloudinary, remove_ai_content_verified
Create Date: 2026-01-20 15:58:27.063302

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7cde52816eaa'
down_revision = ('forum_enhancement_cloudinary', 'remove_ai_content_verified')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
