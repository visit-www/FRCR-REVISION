"""
Alembic migration for CaseFlag table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'student_case_flag'
down_revision = 'd931b239391e'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'case_flag',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('case_id', sa.Integer(), sa.ForeignKey('case.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'case_id', name='uq_user_case_flag')
    )

def downgrade():
    op.drop_table('case_flag')
