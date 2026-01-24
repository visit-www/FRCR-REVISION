"""Add IntelligentTNMData table for AI-generated TNM intelligence

Revision ID: add_intelligent_tnm_data
Revises: add_ajcc_json_cols
Create Date: 2026-01-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_intelligent_tnm_data'
down_revision = 'add_ajcc_json_cols'
branch_labels = None
depends_on = None


def upgrade():
    """Create intelligent_tnm_data table for storing verified AI-generated TNM intelligence."""
    
    # Create the intelligent_tnm_data table
    op.create_table('intelligent_tnm_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('disease_site_id', sa.Integer(), nullable=False),
        sa.Column('diagnosis_year_id', sa.Integer(), nullable=True),
        
        # TNM Memory Aid - Easy-to-remember staging summaries
        sa.Column('tnm_memory_aid_t', sa.Text(), nullable=True),
        sa.Column('tnm_memory_aid_n', sa.Text(), nullable=True),
        sa.Column('tnm_memory_aid_m', sa.Text(), nullable=True),
        
        # JSON fields for structured data
        sa.Column('radiologist_key_points_json', sa.Text(), nullable=True),
        sa.Column('upstaging_triggers_json', sa.Text(), nullable=True),
        sa.Column('mdt_critical_findings_json', sa.Text(), nullable=True),
        sa.Column('copy_blocks_json', sa.Text(), nullable=True),
        sa.Column('imaging_checklist_json', sa.Text(), nullable=True),
        sa.Column('reference_images_json', sa.Text(), nullable=True),
        sa.Column('warnings_json', sa.Text(), nullable=True),
        
        # Verification metadata
        sa.Column('verified_by_user_id', sa.Integer(), nullable=True),
        sa.Column('source_case_id', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        # Version tracking
        sa.Column('version', sa.Integer(), nullable=True, default=1),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['disease_site_id'], ['ajcc_disease_site.id'], ),
        sa.ForeignKeyConstraint(['diagnosis_year_id'], ['ajcc_diagnosis_year.id'], ),
        sa.ForeignKeyConstraint(['verified_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['source_case_id'], ['case.id'], ),
        
        # Unique constraint
        sa.UniqueConstraint('disease_site_id', 'diagnosis_year_id', name='uq_disease_year_intelligence'),
    )
    
    # Create indexes
    op.create_index('idx_disease_intelligence', 'intelligent_tnm_data', ['disease_site_id', 'diagnosis_year_id'])
    op.create_index(op.f('ix_intelligent_tnm_data_disease_site_id'), 'intelligent_tnm_data', ['disease_site_id'])
    op.create_index(op.f('ix_intelligent_tnm_data_diagnosis_year_id'), 'intelligent_tnm_data', ['diagnosis_year_id'])


def downgrade():
    """Drop intelligent_tnm_data table."""
    op.drop_index('idx_disease_intelligence', table_name='intelligent_tnm_data')
    op.drop_index(op.f('ix_intelligent_tnm_data_diagnosis_year_id'), table_name='intelligent_tnm_data')
    op.drop_index(op.f('ix_intelligent_tnm_data_disease_site_id'), table_name='intelligent_tnm_data')
    op.drop_table('intelligent_tnm_data')
