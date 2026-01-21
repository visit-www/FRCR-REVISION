"""Add Evernote integration fields to User model

Revision ID: add_evernote_fields
Revises: 
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_evernote_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add Evernote fields to user table."""
    # Add evernote_access_token column
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evernote_access_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('evernote_connected_at', sa.DateTime(), nullable=True))


def downgrade():
    """Remove Evernote fields from user table."""
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('evernote_connected_at')
        batch_op.drop_column('evernote_access_token')
