"""Remove legacy questions and answers columns from case table

This migration removes the deprecated questions and answers JSON columns
from the case table. All Q&A data is now stored in the Question and Answer
tables only.

IMPORTANT: Before running this migration, ensure all data has been migrated
from the legacy JSON fields to the Question/Answer tables.

Revision ID: remove_legacy_qa
Revises: student_case_flag
Create Date: 2026-01-08 15:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_legacy_qa'
down_revision = 'student_case_flag'
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove legacy questions and answers columns from case table.
    
    WARNING: This is a destructive operation. Make sure all data has been
    migrated to Question/Answer tables before running this migration.
    """
    # Drop the legacy columns
    with op.batch_alter_table('case', schema=None) as batch_op:
        batch_op.drop_column('questions')
        batch_op.drop_column('answers')


def downgrade():
    """
    Restore legacy questions and answers columns (for rollback if needed).
    Note: Data will be lost - only structure is restored.
    """
    with op.batch_alter_table('case', schema=None) as batch_op:
        batch_op.add_column(sa.Column('questions', sa.Text(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('answers', sa.Text(), nullable=False, server_default='[]'))
