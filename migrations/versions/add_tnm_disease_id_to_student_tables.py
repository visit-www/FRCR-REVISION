"""Add tnm_disease_id column to CandidateNote, TextHighlight, and ForumMessage

Revision ID: add_tnm_disease_columns
Revises: 
Create Date: 2026-01-28

This migration adds tnm_disease_id columns to support TNM-specific:
- Student notes (CandidateNote)
- Text highlights (TextHighlight)  
- Forum messages (ForumMessage)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'add_tnm_disease_columns'
down_revision = None  # Set to latest migration revision if needed
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name, index_name):
    """Check if an index exists on a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    # Add tnm_disease_id to candidate_note (if not exists)
    if not column_exists('candidate_note', 'tnm_disease_id'):
        op.add_column('candidate_note', 
            sa.Column('tnm_disease_id', sa.Integer(), nullable=True)
        )
        # Only add FK for PostgreSQL (SQLite has limited FK support)
        bind = op.get_bind()
        if bind.dialect.name == 'postgresql':
            op.create_foreign_key(
                'fk_candidate_note_tnm_disease', 
                'candidate_note', 
                'ajcc_disease_site', 
                ['tnm_disease_id'], 
                ['id']
            )
    
    if not index_exists('candidate_note', 'idx_tnm_user'):
        op.create_index(
            'idx_tnm_user', 
            'candidate_note', 
            ['tnm_disease_id', 'user_id']
        )
    
    # Add tnm_disease_id to text_highlight (if not exists)
    if not column_exists('text_highlight', 'tnm_disease_id'):
        op.add_column('text_highlight', 
            sa.Column('tnm_disease_id', sa.Integer(), nullable=True)
        )
        bind = op.get_bind()
        if bind.dialect.name == 'postgresql':
            op.create_foreign_key(
                'fk_text_highlight_tnm_disease', 
                'text_highlight', 
                'ajcc_disease_site', 
                ['tnm_disease_id'], 
                ['id']
            )
    
    if not index_exists('text_highlight', 'idx_tnm_user_highlight'):
        op.create_index(
            'idx_tnm_user_highlight', 
            'text_highlight', 
            ['tnm_disease_id', 'user_id']
        )
    
    # Add tnm_disease_id to forum_message (if not exists)
    if not column_exists('forum_message', 'tnm_disease_id'):
        op.add_column('forum_message', 
            sa.Column('tnm_disease_id', sa.Integer(), nullable=True)
        )
        bind = op.get_bind()
        if bind.dialect.name == 'postgresql':
            op.create_foreign_key(
                'fk_forum_message_tnm_disease', 
                'forum_message', 
                'ajcc_disease_site', 
                ['tnm_disease_id'], 
                ['id']
            )
    
    if not index_exists('forum_message', 'idx_forum_tnm_disease'):
        op.create_index(
            'idx_forum_tnm_disease', 
            'forum_message', 
            ['tnm_disease_id']
        )


def downgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'
    
    # Remove from forum_message
    if index_exists('forum_message', 'idx_forum_tnm_disease'):
        op.drop_index('idx_forum_tnm_disease', table_name='forum_message')
    if is_postgres:
        try:
            op.drop_constraint('fk_forum_message_tnm_disease', 'forum_message', type_='foreignkey')
        except Exception:
            pass
    if column_exists('forum_message', 'tnm_disease_id'):
        op.drop_column('forum_message', 'tnm_disease_id')
    
    # Remove from text_highlight
    if index_exists('text_highlight', 'idx_tnm_user_highlight'):
        op.drop_index('idx_tnm_user_highlight', table_name='text_highlight')
    if is_postgres:
        try:
            op.drop_constraint('fk_text_highlight_tnm_disease', 'text_highlight', type_='foreignkey')
        except Exception:
            pass
    if column_exists('text_highlight', 'tnm_disease_id'):
        op.drop_column('text_highlight', 'tnm_disease_id')
    
    # Remove from candidate_note
    if index_exists('candidate_note', 'idx_tnm_user'):
        op.drop_index('idx_tnm_user', table_name='candidate_note')
    if is_postgres:
        try:
            op.drop_constraint('fk_candidate_note_tnm_disease', 'candidate_note', type_='foreignkey')
        except Exception:
            pass
    if column_exists('candidate_note', 'tnm_disease_id'):
        op.drop_column('candidate_note', 'tnm_disease_id')
