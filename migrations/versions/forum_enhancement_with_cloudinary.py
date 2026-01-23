"""
Alembic migration for forum enhancement features:
- Add flag_count and Cloudinary image fields to forum_message
- Create forum_message_flag table for moderation

Revision ID: forum_enhancement_cloudinary
Revises: student_case_flag
Create Date: 2026-01-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'forum_enhancement_cloudinary'
down_revision = 'student_case_flag'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to forum_message table (check if they exist first for SQLite)
    from sqlalchemy import inspect
    from sqlalchemy.engine import reflection
    
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('forum_message')]
    
    # Add flag_count only if it doesn't exist
    if 'flag_count' not in existing_columns:
        op.add_column('forum_message', sa.Column('flag_count', sa.Integer(), nullable=True, server_default='0'))
    
    # Add image columns only if they don't exist
    if 'image_url' not in existing_columns:
        op.add_column('forum_message', sa.Column('image_url', sa.String(500), nullable=True))
    if 'image_public_id' not in existing_columns:
        op.add_column('forum_message', sa.Column('image_public_id', sa.String(255), nullable=True))
    if 'image_thumbnail_url' not in existing_columns:
        op.add_column('forum_message', sa.Column('image_thumbnail_url', sa.String(500), nullable=True))
    
    # Create index on flag_count for efficient queries (check if it exists)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('forum_message')]
    if 'idx_forum_flagged' not in existing_indexes:
        op.create_index('idx_forum_flagged', 'forum_message', ['flag_count'])
    
    # Create forum_message_flag table (check if it exists first)
    existing_tables = inspector.get_table_names()
    if 'forum_message_flag' not in existing_tables:
        op.create_table(
            'forum_message_flag',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('message_id', sa.Integer(), sa.ForeignKey('forum_message.id'), nullable=False, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
            sa.Column('reason', sa.String(50), nullable=False),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('resolved_by_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('resolution_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('message_id', 'user_id', name='uq_message_user_flag')
        )
        
        # Create composite index for unresolved flags
        op.create_index('idx_unresolved_flags', 'forum_message_flag', ['is_resolved', 'created_at'])
    else:
        # Table exists, just check if index exists
        flag_table_indexes = [idx['name'] for idx in inspector.get_indexes('forum_message_flag')]
        if 'idx_unresolved_flags' not in flag_table_indexes:
            op.create_index('idx_unresolved_flags', 'forum_message_flag', ['is_resolved', 'created_at'])


def downgrade():
    # Drop forum_message_flag table
    op.drop_index('idx_unresolved_flags', table_name='forum_message_flag')
    op.drop_table('forum_message_flag')
    
    # Remove columns from forum_message
    op.drop_index('idx_forum_flagged', table_name='forum_message')
    op.drop_column('forum_message', 'image_thumbnail_url')
    op.drop_column('forum_message', 'image_public_id')
    op.drop_column('forum_message', 'image_url')
    op.drop_column('forum_message', 'flag_count')
