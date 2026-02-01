"""Add CaseReferenceImage table for CC-licensed reference images

Revision ID: add_case_ref_image
Revises: seed_head_neck_display_order
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_case_ref_image'
down_revision = 'seed_head_neck_display_order'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import text
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        r = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'case_reference_image'"
        )).fetchone()
        if r:
            return
    elif conn.dialect.name == "sqlite":
        r = conn.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'case_reference_image'"
        )).fetchone()
        if r:
            return

    op.create_table('case_reference_image',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=False),
        sa.Column('source_domain', sa.String(length=255), nullable=False),
        sa.Column('thumbnail_url', sa.String(length=500), nullable=True),
        sa.Column('image_type', sa.String(length=50), nullable=False, server_default='ct_mri'),
        sa.Column('modality', sa.String(length=50), nullable=True),
        sa.Column('ai_description', sa.Text(), nullable=True),
        sa.Column('ai_relevance_score', sa.Float(), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('added_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('license', sa.String(length=100), nullable=False, server_default='CC BY 4.0'),
        sa.Column('attribution', sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(['added_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_reference_image_case_id'), 'case_reference_image', ['case_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_case_reference_image_case_id'), table_name='case_reference_image')
    op.drop_table('case_reference_image')
