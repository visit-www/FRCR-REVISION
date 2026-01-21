"""Add Notion and Anki integration fields to User model

Revision ID: add_notion_anki_fields
Revises: 
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_notion_anki_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add Notion and Anki fields to user table."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Notion fields
        batch_op.add_column(sa.Column('notion_access_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('notion_workspace_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('notion_connected_at', sa.DateTime(), nullable=True))
        
        # Anki fields
        batch_op.add_column(sa.Column('anki_api_key', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('anki_deck_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('anki_connected_at', sa.DateTime(), nullable=True))


def downgrade():
    """Remove Notion and Anki fields from user table."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        # Remove Anki fields
        batch_op.drop_column('anki_connected_at')
        batch_op.drop_column('anki_deck_name')
        batch_op.drop_column('anki_api_key')
        
        # Remove Notion fields
        batch_op.drop_column('notion_connected_at')
        batch_op.drop_column('notion_workspace_id')
        batch_op.drop_column('notion_access_token')
