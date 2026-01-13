"""Add missing columns to case_image table

Revision ID: add_case_image_columns
Revises: d931b239391e
Create Date: 2026-01-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_case_image_columns'
down_revision = 'd931b239391e'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to case_image table
    with op.batch_alter_table('case_image', schema=None) as batch_op:
        # Add image_filename column
        batch_op.add_column(sa.Column('image_filename', sa.String(length=255), nullable=True))
        
        # Add image_description column
        batch_op.add_column(sa.Column('image_description', sa.Text(), nullable=True))
        
        # Add created_at column
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        
        # Make image_data and image_type NOT NULL (they should be required)
        batch_op.alter_column('image_data',
               existing_type=sa.LargeBinary(),
               nullable=False)
        batch_op.alter_column('image_type',
               existing_type=sa.String(length=50),
               nullable=False)
        
        # Set default values for existing rows
        op.execute("UPDATE case_image SET image_filename = 'image.jpg' WHERE image_filename IS NULL")
        op.execute("UPDATE case_image SET image_description = '' WHERE image_description IS NULL")
        op.execute("UPDATE case_image SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        
        # Now make columns NOT NULL
        batch_op.alter_column('image_filename',
               existing_type=sa.String(length=255),
               nullable=False)
        batch_op.alter_column('image_description',
               existing_type=sa.Text(),
               nullable=False,
               server_default='')
        batch_op.alter_column('created_at',
               existing_type=sa.DateTime(),
               nullable=False)


def downgrade():
    # Remove the added columns
    with op.batch_alter_table('case_image', schema=None) as batch_op:
        batch_op.drop_column('created_at')
        batch_op.drop_column('image_description')
        batch_op.drop_column('image_filename')
        
        # Revert to nullable
        batch_op.alter_column('image_data',
               existing_type=sa.LargeBinary(),
               nullable=True)
        batch_op.alter_column('image_type',
               existing_type=sa.String(length=50),
               nullable=True)
