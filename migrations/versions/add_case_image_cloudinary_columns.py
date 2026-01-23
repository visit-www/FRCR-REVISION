"""Add Cloudinary columns to case_image and user tables

Revision ID: cloudinary_case_images
Revises: 7cde52816eaa
Create Date: 2026-01-20
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cloudinary_case_images'
down_revision = '7cde52816eaa'
branch_labels = None
depends_on = None


def upgrade():
    # Check existing columns before adding
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Add Cloudinary storage columns to case_image table (check if they exist first)
    case_image_columns = [col['name'] for col in inspector.get_columns('case_image')]
    with op.batch_alter_table('case_image', schema=None) as batch_op:
        if 'image_url' not in case_image_columns:
            batch_op.add_column(sa.Column('image_url', sa.String(length=500), nullable=True))
        if 'image_public_id' not in case_image_columns:
            batch_op.add_column(sa.Column('image_public_id', sa.String(length=255), nullable=True))
        if 'image_thumbnail_url' not in case_image_columns:
            batch_op.add_column(sa.Column('image_thumbnail_url', sa.String(length=500), nullable=True))
    
    # Make image_data nullable for new Cloudinary uploads (only if not already nullable)
    image_data_col = next((col for col in inspector.get_columns('case_image') if col['name'] == 'image_data'), None)
    if image_data_col and not image_data_col.get('nullable', False):
        with op.batch_alter_table('case_image', schema=None) as batch_op:
            batch_op.alter_column('image_data',
                                  existing_type=sa.LargeBinary(),
                                  nullable=True)
    
    # Add profile picture public_id to user table for Cloudinary cleanup
    user_columns = [col['name'] for col in inspector.get_columns('user')]
    if 'profile_picture_public_id' not in user_columns:
        with op.batch_alter_table('user', schema=None) as batch_op:
            batch_op.add_column(sa.Column('profile_picture_public_id', sa.String(length=255), nullable=True))


def downgrade():
    # Remove profile picture public_id from user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('profile_picture_public_id')
    
    # Remove Cloudinary columns from case_image table
    with op.batch_alter_table('case_image', schema=None) as batch_op:
        batch_op.drop_column('image_thumbnail_url')
        batch_op.drop_column('image_public_id')
        batch_op.drop_column('image_url')
        batch_op.alter_column('image_data',
                              existing_type=sa.LargeBinary(),
                              nullable=False)
