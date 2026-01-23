"""Add AJCC TNM staging system models

Revision ID: add_ajcc_tnm_models
Revises: add_sciencedirect_fields
Create Date: 2026-01-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_ajcc_tnm_models'
down_revision = 'add_sciencedirect_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Create AJCC TNM staging tables."""
    
    # Create ajcc_body_section table
    op.create_table('ajcc_body_section',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section_name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('section_name'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_ajcc_body_section_slug'), 'ajcc_body_section', ['slug'], unique=False)
    
    # Create ajcc_diagnosis_year table
    op.create_table('ajcc_diagnosis_year',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year')
    )
    op.create_index(op.f('ix_ajcc_diagnosis_year_is_default'), 'ajcc_diagnosis_year', ['is_default'], unique=False)
    
    # Create ajcc_disease_site table
    op.create_table('ajcc_disease_site',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('body_section_id', sa.Integer(), nullable=False),
        sa.Column('disease_name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=200), nullable=False),
        sa.Column('ajcc_url_path', sa.String(length=300), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['body_section_id'], ['ajcc_body_section.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('body_section_id', 'slug', name='uq_body_section_disease_slug')
    )
    op.create_index(op.f('ix_ajcc_disease_site_body_section_id'), 'ajcc_disease_site', ['body_section_id'], unique=False)
    op.create_index(op.f('ix_ajcc_disease_site_slug'), 'ajcc_disease_site', ['slug'], unique=False)
    op.create_index('idx_disease_slug', 'ajcc_disease_site', ['slug'], unique=False)
    
    # Create ajcc_disease_mapping table
    op.create_table('ajcc_disease_mapping',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('disease_site_id', sa.Integer(), nullable=False),
        sa.Column('frcr_module', sa.Enum('Cardiothoracic and Vascular', 'Musculoskeletal and Trauma', 'Gastro-intestinal (incl. liver, biliary, pancreas, spleen)', 'Genito-urinary, Adrenal, O&G and Breast', 'Paediatric', 'CNS and Head & Neck (incl. spine, eyes, ENT, salivary, dental)', name='frcrmodule'), nullable=True),
        sa.Column('body_part', sa.Enum('Cardiovascular', 'Lung and Mediastinum', 'Chest Wall', 'Gastrointestinal', 'Hepatopancreaticobiliary', 'Adrenal', 'Thyroid and Parathyroid', 'Spleen', 'KUB', 'Gynaecology', 'Breast', 'Upper Limb', 'Lower Limb', 'Bones', 'Brain and Pituitary', 'Spine', 'Head and Neck', 'Multisystem', name='bodypart'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['disease_site_id'], ['ajcc_disease_site.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ajcc_disease_mapping_body_part'), 'ajcc_disease_mapping', ['body_part'], unique=False)
    op.create_index(op.f('ix_ajcc_disease_mapping_disease_site_id'), 'ajcc_disease_mapping', ['disease_site_id'], unique=False)
    op.create_index(op.f('ix_ajcc_disease_mapping_frcr_module'), 'ajcc_disease_mapping', ['frcr_module'], unique=False)
    op.create_index('idx_disease_frcr_module', 'ajcc_disease_mapping', ['disease_site_id', 'frcr_module'], unique=False)
    op.create_index('idx_disease_body_part', 'ajcc_disease_mapping', ['disease_site_id', 'body_part'], unique=False)
    
    # Create ajcc_staging_data table
    op.create_table('ajcc_staging_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('disease_site_id', sa.Integer(), nullable=False),
        sa.Column('diagnosis_year_id', sa.Integer(), nullable=False),
        sa.Column('section_1_quick_reference_html', sa.Text(), nullable=True),
        sa.Column('section_2_cancers_staged_html', sa.Text(), nullable=True),
        sa.Column('section_3_cancers_not_staged_html', sa.Text(), nullable=True),
        sa.Column('section_4_summary_changes_html', sa.Text(), nullable=True),
        sa.Column('section_5_primary_site_html', sa.Text(), nullable=True),
        sa.Column('section_6_histopathologic_type_html', sa.Text(), nullable=True),
        sa.Column('section_7_clinical_staging_workup_html', sa.Text(), nullable=True),
        sa.Column('section_8_staging_rules_html', sa.Text(), nullable=True),
        sa.Column('section_9_common_scenarios_html', sa.Text(), nullable=True),
        sa.Column('section_10_explanatory_notes_html', sa.Text(), nullable=True),
        sa.Column('raw_html_content', sa.Text(), nullable=True),
        sa.Column('extracted_at', sa.DateTime(), nullable=True),
        sa.Column('extracted_by_user_id', sa.Integer(), nullable=True),
        sa.Column('last_updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['diagnosis_year_id'], ['ajcc_diagnosis_year.id'], ),
        sa.ForeignKeyConstraint(['disease_site_id'], ['ajcc_disease_site.id'], ),
        sa.ForeignKeyConstraint(['extracted_by_user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('disease_site_id', 'diagnosis_year_id', name='uq_disease_year_staging')
    )
    op.create_index(op.f('ix_ajcc_staging_data_diagnosis_year_id'), 'ajcc_staging_data', ['diagnosis_year_id'], unique=False)
    op.create_index(op.f('ix_ajcc_staging_data_disease_site_id'), 'ajcc_staging_data', ['disease_site_id'], unique=False)
    op.create_index('idx_disease_year', 'ajcc_staging_data', ['disease_site_id', 'diagnosis_year_id'], unique=False)


def downgrade():
    """Drop AJCC TNM staging tables."""
    op.drop_index('idx_disease_year', table_name='ajcc_staging_data')
    op.drop_index(op.f('ix_ajcc_staging_data_disease_site_id'), table_name='ajcc_staging_data')
    op.drop_index(op.f('ix_ajcc_staging_data_diagnosis_year_id'), table_name='ajcc_staging_data')
    op.drop_table('ajcc_staging_data')
    
    op.drop_index('idx_disease_body_part', table_name='ajcc_disease_mapping')
    op.drop_index('idx_disease_frcr_module', table_name='ajcc_disease_mapping')
    op.drop_index(op.f('ix_ajcc_disease_mapping_frcr_module'), table_name='ajcc_disease_mapping')
    op.drop_index(op.f('ix_ajcc_disease_mapping_disease_site_id'), table_name='ajcc_disease_mapping')
    op.drop_index(op.f('ix_ajcc_disease_mapping_body_part'), table_name='ajcc_disease_mapping')
    op.drop_table('ajcc_disease_mapping')
    
    op.drop_index('idx_disease_slug', table_name='ajcc_disease_site')
    op.drop_index(op.f('ix_ajcc_disease_site_slug'), table_name='ajcc_disease_site')
    op.drop_index(op.f('ix_ajcc_disease_site_body_section_id'), table_name='ajcc_disease_site')
    op.drop_table('ajcc_disease_site')
    
    op.drop_index(op.f('ix_ajcc_diagnosis_year_is_default'), table_name='ajcc_diagnosis_year')
    op.drop_table('ajcc_diagnosis_year')
    
    op.drop_index(op.f('ix_ajcc_body_section_slug'), table_name='ajcc_body_section')
    op.drop_table('ajcc_body_section')
