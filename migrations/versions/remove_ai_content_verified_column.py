"""remove ai_content_verified column

Revision ID: remove_ai_content_verified
Revises: 167ef09c7b85
Create Date: 2026-01-17 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_ai_content_verified'
down_revision = '167ef09c7b85'
branch_labels = None
depends_on = None


def upgrade():
    # Check if the column exists before trying to drop it
    from sqlalchemy import inspect
    from sqlalchemy.engine import reflection
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get all columns in the 'case' table
    columns = [col['name'] for col in inspector.get_columns('case')]
    
    # Only drop the column and index if they exist
    if 'ai_content_verified' in columns:
        # Drop the index first
        try:
            op.drop_index('ix_case_ai_content_verified', table_name='case')
        except Exception:
            pass  # Index might not exist
        
        # Drop the column
        op.drop_column('case', 'ai_content_verified')


def downgrade():
    # Add the column back if needed
    # Use '0' as server_default to match the original migration (167ef09c7b85)
    # This ensures compatibility with both SQLite and PostgreSQL
    op.add_column('case', sa.Column('ai_content_verified', sa.Boolean(), nullable=False, server_default='0'))
    op.create_index('ix_case_ai_content_verified', 'case', ['ai_content_verified'], unique=False)
