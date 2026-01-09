"""Initial schema with Sprint 1 fields

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-01-09 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### Create user table ###
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(120), nullable=False, unique=True),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('full_name', sa.String(120), nullable=False),
        sa.Column('profile_picture', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, server_default='student'),
        sa.Column('subscription_status', sa.String(50), nullable=False, server_default='free'),
        sa.Column('payment_status', sa.String(50), nullable=False, server_default='no_subscription'),
        sa.Column('subscription_start_date', sa.DateTime(), nullable=True),
        sa.Column('subscription_end_date', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by_user_id', sa.Integer(), nullable=True),
        sa.Column('last_case_viewed', sa.DateTime(), nullable=True),
        sa.Column('last_case_viewed_id', sa.Integer(), nullable=True),
        sa.Column('recovery_token', sa.String(255), nullable=True, unique=True),
        sa.Column('recovery_token_expires', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_index(op.f('ix_user_is_deleted'), 'user', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_user_role'), 'user', ['role'], unique=False)
    op.create_index(op.f('ix_user_subscription_status'), 'user', ['subscription_status'], unique=False)
    
    # ### Create packet table ###
    op.create_table(
        'packet',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('packet_num', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create exam_session table ###
    op.create_table(
        'exam_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create candidate table ###
    op.create_table(
        'candidate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True, unique=True),
        sa.Column('exam_session_id', sa.Integer(), nullable=True),
        sa.Column('is_locked', sa.Boolean(), default=False),
        sa.ForeignKeyConstraint(['exam_session_id'], ['exam_session.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create case table ###
    op.create_table(
        'case',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('packet_id', sa.Integer(), nullable=True),
        sa.Column('case_number', sa.Integer(), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('questions', sa.Text(), nullable=True),
        sa.Column('answers', sa.Text(), nullable=True),
        sa.Column('discussion', sa.Text(), nullable=True),
        sa.Column('module', sa.String(50), nullable=True),
        sa.Column('body_part', sa.String(50), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['packet_id'], ['packet.id'], ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_body_part'), 'case', ['body_part'], unique=False)
    op.create_index(op.f('ix_case_is_public'), 'case', ['is_public'], unique=False)
    op.create_index(op.f('ix_case_module'), 'case', ['module'], unique=False)
    op.create_index(op.f('ix_case_status'), 'case', ['status'], unique=False)
    
    # ### Create case_image table ###
    op.create_table(
        'case_image',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('image_data', sa.LargeBinary(), nullable=True),
        sa.Column('image_type', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create question table ###
    op.create_table(
        'question',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=True),
        sa.Column('question_type', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create answer table ###
    op.create_table(
        'answer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['question_id'], ['question.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create candidate_note table ###
    op.create_table(
        'candidate_note',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidate.id'], ),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create case_audit_log table ###
    op.create_table(
        'case_audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_audit_log_case_id'), 'case_audit_log', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_audit_log_user_id'), 'case_audit_log', ['user_id'], unique=False)
    op.create_index(op.f('ix_case_audit_log_created_at'), 'case_audit_log', ['created_at'], unique=False)
    
    # ### Create case_view_log table ###
    op.create_table(
        'case_view_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('viewed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_view_log_case_id'), 'case_view_log', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_view_log_user_id'), 'case_view_log', ['user_id'], unique=False)
    op.create_index(op.f('ix_case_view_log_viewed_at'), 'case_view_log', ['viewed_at'], unique=False)
    op.create_index('ix_user_case_view', 'case_view_log', ['user_id', 'case_id', 'viewed_at'])
    
    # ### Create case_approval_queue table ###
    op.create_table(
        'case_approval_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('submitted_by_user_id', sa.Integer(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.ForeignKeyConstraint(['submitted_by_user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_approval_queue_case_id'), 'case_approval_queue', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_approval_queue_submitted_at'), 'case_approval_queue', ['submitted_at'], unique=False)
    
    # ### Create revision_session table ###
    op.create_table(
        'revision_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('module', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create revision_history table ###
    op.create_table(
        'revision_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('revision_session_id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['revision_session_id'], ['revision_session.id'], ),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # ### Create text_highlight table ###
    op.create_table(
        'text_highlight',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('highlight_text', sa.Text(), nullable=True),
        sa.Column('color', sa.String(10), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidate.id'], ),
        sa.ForeignKeyConstraint(['case_id'], ['case.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add foreign key for deleted_by_user_id
    op.create_foreign_key('fk_user_deleted_by', 'user', 'user', ['deleted_by_user_id'], ['id'])


def downgrade():
    # Drop all tables in reverse order of creation
    op.drop_table('text_highlight')
    op.drop_table('revision_history')
    op.drop_table('revision_session')
    op.drop_index(op.f('ix_case_approval_queue_submitted_at'), table_name='case_approval_queue')
    op.drop_index(op.f('ix_case_approval_queue_case_id'), table_name='case_approval_queue')
    op.drop_table('case_approval_queue')
    op.drop_index('ix_user_case_view', table_name='case_view_log')
    op.drop_index(op.f('ix_case_view_log_viewed_at'), table_name='case_view_log')
    op.drop_index(op.f('ix_case_view_log_user_id'), table_name='case_view_log')
    op.drop_index(op.f('ix_case_view_log_case_id'), table_name='case_view_log')
    op.drop_table('case_view_log')
    op.drop_index(op.f('ix_case_audit_log_created_at'), table_name='case_audit_log')
    op.drop_index(op.f('ix_case_audit_log_user_id'), table_name='case_audit_log')
    op.drop_index(op.f('ix_case_audit_log_case_id'), table_name='case_audit_log')
    op.drop_table('case_audit_log')
    op.drop_table('candidate_note')
    op.drop_table('answer')
    op.drop_table('question')
    op.drop_table('case_image')
    op.drop_index(op.f('ix_case_status'), table_name='case')
    op.drop_index(op.f('ix_case_module'), table_name='case')
    op.drop_index(op.f('ix_case_is_public'), table_name='case')
    op.drop_index(op.f('ix_case_body_part'), table_name='case')
    op.drop_table('case')
    op.drop_table('candidate')
    op.drop_table('exam_session')
    op.drop_table('packet')
    op.drop_index(op.f('ix_user_subscription_status'), table_name='user')
    op.drop_index(op.f('ix_user_role'), table_name='user')
    op.drop_index(op.f('ix_user_is_deleted'), table_name='user')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
