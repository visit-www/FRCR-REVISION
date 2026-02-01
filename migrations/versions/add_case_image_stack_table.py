"""Add CaseImageStack table for OneDrive-linked DICOM-like image stacks

Revision ID: add_case_image_stack
Revises: add_case_ref_image
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_case_image_stack'
down_revision = 'add_case_ref_image'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import text
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        r = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'case_image_stack'"
        )).fetchone()
        if r:
            return
    elif conn.dialect.name == "sqlite":
        r = conn.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'case_image_stack'"
        )).fetchone()
        if r:
            return

    op.create_table('case_image_stack',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('onedrive_share_id', sa.String(length=500), nullable=False),
        sa.Column('onedrive_folder_path', sa.String(length=500), nullable=True),
        sa.Column('config_json', sa.Text(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_id', name='uq_case_image_stack_case_id')
    )
    op.create_index('ix_case_image_stack_case_id', 'case_image_stack', ['case_id'], unique=True)


def downgrade():
    op.drop_index('ix_case_image_stack_case_id', table_name='case_image_stack')
    op.drop_table('case_image_stack')
