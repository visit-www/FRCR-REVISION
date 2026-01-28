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

# revision identifiers, used by Alembic.
revision = 'add_tnm_disease_columns'
down_revision = None  # Set to latest migration revision if needed
branch_labels = None
depends_on = None


def upgrade():
    # Add tnm_disease_id to candidate_note
    op.add_column('candidate_note', 
        sa.Column('tnm_disease_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_candidate_note_tnm_disease', 
        'candidate_note', 
        'ajcc_disease_site', 
        ['tnm_disease_id'], 
        ['id']
    )
    op.create_index(
        'idx_tnm_user', 
        'candidate_note', 
        ['tnm_disease_id', 'user_id']
    )
    
    # Add tnm_disease_id to text_highlight
    op.add_column('text_highlight', 
        sa.Column('tnm_disease_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_text_highlight_tnm_disease', 
        'text_highlight', 
        'ajcc_disease_site', 
        ['tnm_disease_id'], 
        ['id']
    )
    op.create_index(
        'idx_tnm_user_highlight', 
        'text_highlight', 
        ['tnm_disease_id', 'user_id']
    )
    
    # Add tnm_disease_id to forum_message
    op.add_column('forum_message', 
        sa.Column('tnm_disease_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_forum_message_tnm_disease', 
        'forum_message', 
        'ajcc_disease_site', 
        ['tnm_disease_id'], 
        ['id']
    )
    op.create_index(
        'idx_forum_tnm_disease', 
        'forum_message', 
        ['tnm_disease_id']
    )


def downgrade():
    # Remove from forum_message
    op.drop_index('idx_forum_tnm_disease', table_name='forum_message')
    op.drop_constraint('fk_forum_message_tnm_disease', 'forum_message', type_='foreignkey')
    op.drop_column('forum_message', 'tnm_disease_id')
    
    # Remove from text_highlight
    op.drop_index('idx_tnm_user_highlight', table_name='text_highlight')
    op.drop_constraint('fk_text_highlight_tnm_disease', 'text_highlight', type_='foreignkey')
    op.drop_column('text_highlight', 'tnm_disease_id')
    
    # Remove from candidate_note
    op.drop_index('idx_tnm_user', table_name='candidate_note')
    op.drop_constraint('fk_candidate_note_tnm_disease', 'candidate_note', type_='foreignkey')
    op.drop_column('candidate_note', 'tnm_disease_id')
