"""Add display_order to ajcc_disease_site

Revision ID: add_display_order_ajcc_site
Revises: c26b2d9bfc6b
Create Date: 2026-01-30

Adds display_order column so sections can order disease sites. Idempotent:
skips add if column already exists (e.g. from add_display_order_column.sql).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'add_display_order_ajcc_site'
down_revision = 'c26b2d9bfc6b'
branch_labels = None
depends_on = None


def _column_exists(connection, table_name, column_name):
    inspector = inspect(connection)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    conn = op.get_bind()
    if _column_exists(conn, 'ajcc_disease_site', 'display_order'):
        return
    with op.batch_alter_table('ajcc_disease_site', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_order', sa.Integer(), nullable=True, server_default=sa.text('0')))


def downgrade():
    with op.batch_alter_table('ajcc_disease_site', schema=None) as batch_op:
        batch_op.drop_column('display_order')
