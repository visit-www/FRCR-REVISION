"""Add ScienceDirect integration fields to user table

Revision ID: add_sciencedirect_fields
Revises: 
Create Date: 2026-01-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_sciencedirect_fields'
down_revision = 'add_notion_anki_fields'  # Comes after Notion/Anki migration
branch_labels = None
depends_on = None


def upgrade():
    """Add ScienceDirect fields to user table."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sciencedirect_session_cookies', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('sciencedirect_connected_at', sa.DateTime(), nullable=True))


def downgrade():
    """Remove ScienceDirect fields from user table."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('sciencedirect_connected_at')
        batch_op.drop_column('sciencedirect_session_cookies')
