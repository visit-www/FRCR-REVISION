"""Add TNMImage table for disease-linked images

Revision ID: add_tnm_image_table
Revises: 8c81a73b2138
Create Date: 2025-01-28

This migration creates the tnm_image table for storing images
uploaded for specific TNM disease sites with Cloudinary URLs.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_tnm_image_table'
down_revision = '8c81a73b2138'  # After AnatomyFigure model
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import text
    conn = op.get_bind()
    # Idempotent: skip if table already exists (Neon may have it from a partial run).
    if conn.dialect.name == "postgresql":
        r = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'tnm_image'"
        )).fetchone()
        if r:
            return
    elif conn.dialect.name == "sqlite":
        r = conn.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tnm_image'"
        )).fetchone()
        if r:
            return

    # Create tnm_image table
    op.create_table(
        'tnm_image',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('disease_site_id', sa.Integer(), sa.ForeignKey('ajcc_disease_site.id'), nullable=False, index=True),
        sa.Column('diagnosis_year_id', sa.Integer(), sa.ForeignKey('ajcc_diagnosis_year.id'), nullable=True, index=True),
        sa.Column('title', sa.String(300), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('alt_text', sa.String(500), nullable=True),
        sa.Column('cloudinary_url', sa.String(500), nullable=False),
        sa.Column('cloudinary_public_id', sa.String(300), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('image_type', sa.String(50), default='reference'),
        sa.Column('uploaded_by_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create composite index for efficient queries
    op.create_index('idx_tnm_image_disease', 'tnm_image', ['disease_site_id', 'is_active'])


def downgrade():
    # Drop index first
    op.drop_index('idx_tnm_image_disease', table_name='tnm_image')
    
    # Drop table
    op.drop_table('tnm_image')
