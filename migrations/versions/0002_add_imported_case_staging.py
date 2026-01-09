"""Add ImportedCaseStaging model with duplicate detection

Revision ID: 0002_imported_case_staging
Revises: 85465bd3e9d5
Create Date: 2026-01-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002_imported_case_staging'
down_revision = '85465bd3e9d5'
branch_labels = None
depends_on = None


def upgrade():
    # Create imported_case_staging table
    op.create_table(
        'imported_case_staging',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('original_id', sa.Integer(), nullable=True),
        sa.Column('case_number', sa.Integer(), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=False),
        sa.Column('questions', sa.Text(), nullable=False),
        sa.Column('answers', sa.Text(), nullable=False),
        sa.Column('discussion', sa.Text(), nullable=True),
        sa.Column('module', sa.Enum('Cardiothoracic and Vascular', 'Musculoskeletal and Trauma', 'Gastro-intestinal (incl. liver, biliary, pancreas, spleen)', 'Genito-urinary, Adrenal, O&G and Breast', 'Paediatric', 'CNS and Head & Neck (incl. spine, eyes, ENT, salivary, dental)', name='frcrmodule'), nullable=True),
        sa.Column('body_part', sa.Enum('Cardiovascular', 'Lung and Mediastinum', 'Chest Wall', 'Gastrointestinal', 'Hepatopancreaticobiliary', 'Adrenal', 'Thyroid and Parathyroid', 'Spleen', 'KUB', 'Gynaecology', 'Breast', 'Upper Limb', 'Lower Limb', 'Bones', 'Brain and Pituitary', 'Spine', 'Head and Neck', 'Multisystem', name='bodypart'), nullable=True),
        sa.Column('age_group', sa.Enum('Adult', 'Pediatric', name='agegroup'), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('enrichment_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('enriched_by_user_id', sa.Integer(), nullable=True),
        sa.Column('enriched_at', sa.DateTime(), nullable=True),
        sa.Column('enrichment_notes', sa.Text(), nullable=True),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('promoted_to_case_id', sa.Integer(), nullable=True),
        sa.Column('promoted_at', sa.DateTime(), nullable=True),
        sa.Column('previous_staging_id', sa.Integer(), nullable=True),
        sa.Column('is_replacement', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('import_batch_id', sa.String(length=50), nullable=False),
        sa.Column('source_system', sa.String(length=50), nullable=False, server_default='frcr_examiner'),
        sa.Column('import_timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enriched_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['promoted_to_case_id'], ['case.id'], ),
        sa.ForeignKeyConstraint(['previous_staging_id'], ['imported_case_staging.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_enrichment_status', 'imported_case_staging', ['enrichment_status'], unique=False)
    op.create_index('idx_original_id_batch', 'imported_case_staging', ['source_system', 'original_id', 'import_batch_id'], unique=False)
    op.create_index('idx_promoted_case', 'imported_case_staging', ['promoted_to_case_id'], unique=False)
    op.create_index('ix_imported_case_staging_import_batch_id', 'imported_case_staging', ['import_batch_id'], unique=False)
    op.create_index('ix_imported_case_staging_is_public', 'imported_case_staging', ['is_public'], unique=False)
    op.create_index('ix_imported_case_staging_original_id', 'imported_case_staging', ['original_id'], unique=False)
    op.create_index('ix_imported_case_staging_age_group', 'imported_case_staging', ['age_group'], unique=False)
    op.create_index('ix_imported_case_staging_body_part', 'imported_case_staging', ['body_part'], unique=False)
    op.create_index('ix_imported_case_staging_module', 'imported_case_staging', ['module'], unique=False)
    op.create_index('ix_imported_case_staging_source_system', 'imported_case_staging', ['source_system'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index('ix_imported_case_staging_source_system', table_name='imported_case_staging')
    op.drop_index('ix_imported_case_staging_module', table_name='imported_case_staging')
    op.drop_index('ix_imported_case_staging_body_part', table_name='imported_case_staging')
    op.drop_index('ix_imported_case_staging_age_group', table_name='imported_case_staging')
    op.drop_index('ix_imported_case_staging_original_id', table_name='imported_case_staging')
    op.drop_index('ix_imported_case_staging_is_public', table_name='imported_case_staging')
    op.drop_index('ix_imported_case_staging_import_batch_id', table_name='imported_case_staging')
    op.drop_index('idx_promoted_case', table_name='imported_case_staging')
    op.drop_index('idx_original_id_batch', table_name='imported_case_staging')
    op.drop_index('idx_enrichment_status', table_name='imported_case_staging')
    
    # Drop table
    op.drop_table('imported_case_staging')
