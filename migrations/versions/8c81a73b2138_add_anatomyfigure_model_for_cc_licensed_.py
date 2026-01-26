"""Add AnatomyFigure model for CC-licensed figures

Revision ID: 8c81a73b2138
Revises: 43891be57ccb
Create Date: 2026-01-26 22:21:52.674444

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c81a73b2138'
down_revision = '43891be57ccb'
branch_labels = None
depends_on = None


def upgrade():
    # Create AnatomyFigure table for CC-licensed anatomy and staging figures
    op.create_table('anatomy_figure',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('figure_id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('body_region', sa.String(length=100), nullable=True),
        sa.Column('figure_type', sa.String(length=50), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('modality', sa.String(length=50), nullable=True),
        sa.Column('cancer_type', sa.String(length=100), nullable=True),
        sa.Column('staging_category', sa.String(length=20), nullable=True),
        sa.Column('original_url', sa.String(length=500), nullable=True),
        sa.Column('cloudinary_url', sa.String(length=500), nullable=True),
        sa.Column('cloudinary_public_id', sa.String(length=300), nullable=True),
        sa.Column('thumbnail_url', sa.String(length=500), nullable=True),
        sa.Column('license', sa.String(length=100), nullable=True, default='CC BY 4.0'),
        sa.Column('attribution', sa.String(length=300), nullable=False),
        sa.Column('chapter', sa.Integer(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_anatomy_figure_figure_id'), 'anatomy_figure', ['figure_id'], unique=True)
    op.create_index(op.f('ix_anatomy_figure_source'), 'anatomy_figure', ['source'], unique=False)
    op.create_index(op.f('ix_anatomy_figure_body_region'), 'anatomy_figure', ['body_region'], unique=False)
    op.create_index(op.f('ix_anatomy_figure_cancer_type'), 'anatomy_figure', ['cancer_type'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_anatomy_figure_cancer_type'), table_name='anatomy_figure')
    op.drop_index(op.f('ix_anatomy_figure_body_region'), table_name='anatomy_figure')
    op.drop_index(op.f('ix_anatomy_figure_source'), table_name='anatomy_figure')
    op.drop_index(op.f('ix_anatomy_figure_figure_id'), table_name='anatomy_figure')
    
    # Drop table
    op.drop_table('anatomy_figure')
    # ### end Alembic commands ###
