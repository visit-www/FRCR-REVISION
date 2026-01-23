"""Add JSON columns to AJCCStagingData

Revision ID: add_ajcc_json_cols
Revises: add_ajcc_tnm_models
Create Date: 2026-01-23

This migration adds JSON columns to store structured TNM data
alongside the existing HTML columns for backward compatibility.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_ajcc_json_cols'
down_revision = 'add_ajcc_tnm_models'
branch_labels = None
depends_on = None


def upgrade():
    # Add JSON columns to ajcc_staging_data table
    with op.batch_alter_table('ajcc_staging_data', schema=None) as batch_op:
        # Core TNM staging data as clean JSON
        batch_op.add_column(sa.Column('tnm_data_json', sa.Text(), nullable=True))
        
        # Additional structured sections as JSON
        batch_op.add_column(sa.Column('cancers_staged_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('cancers_not_staged_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('summary_changes_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('primary_sites_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('histopathologic_types_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('imaging_workup_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('staging_rules_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('common_scenarios_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('notes_json', sa.Text(), nullable=True))
        
        # Data version flag
        batch_op.add_column(sa.Column('data_version', sa.Integer(), nullable=True, server_default='1'))


def downgrade():
    with op.batch_alter_table('ajcc_staging_data', schema=None) as batch_op:
        batch_op.drop_column('tnm_data_json')
        batch_op.drop_column('cancers_staged_json')
        batch_op.drop_column('cancers_not_staged_json')
        batch_op.drop_column('summary_changes_json')
        batch_op.drop_column('primary_sites_json')
        batch_op.drop_column('histopathologic_types_json')
        batch_op.drop_column('imaging_workup_json')
        batch_op.drop_column('staging_rules_json')
        batch_op.drop_column('common_scenarios_json')
        batch_op.drop_column('notes_json')
        batch_op.drop_column('data_version')
