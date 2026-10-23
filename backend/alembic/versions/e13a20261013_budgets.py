"""Persistent monetary reservations, provider limits, and per-identity task slots."""
from alembic import op
import sqlalchemy as sa

revision = 'e13a20261013'
down_revision = 'd13a20261013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('providers',
        sa.Column('id', sa.String(20), primary_key=True), sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('message', sa.String(200), nullable=False), sa.Column('concurrency', sa.Integer(), nullable=False),
        sa.Column('daily_micros', sa.BigInteger(), nullable=False), sa.Column('next_daily_micros', sa.BigInteger()),
        sa.Column('effective_day', sa.String(10)), sa.Column('reserve_micros', sa.BigInteger(), nullable=False),
        sa.Column('context_limit', sa.Integer(), nullable=False), sa.Column('output_limit', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.String(40), nullable=False))
    op.create_table('daily_budgets',
        sa.Column('id', sa.String(100), primary_key=True), sa.Column('identity_key', sa.String(64), nullable=False, index=True),
        sa.Column('provider_id', sa.String(20), nullable=False, index=True), sa.Column('day', sa.String(10), nullable=False, index=True),
        sa.Column('limit_micros', sa.BigInteger(), nullable=False), sa.Column('held_micros', sa.BigInteger(), nullable=False),
        sa.Column('spent_micros', sa.BigInteger(), nullable=False))
    op.create_table('quota_overrides',
        sa.Column('id', sa.String(90), primary_key=True), sa.Column('identity_key', sa.String(64), nullable=False, index=True),
        sa.Column('provider_id', sa.String(20), nullable=False), sa.Column('amount_micros', sa.BigInteger()),
        sa.Column('next_amount_micros', sa.BigInteger()), sa.Column('effective_day', sa.String(10)))
    op.create_table('user_task_slots', sa.Column('id', sa.String(90), primary_key=True), sa.Column('task_id', sa.String(64)))
    op.create_table('charges',
        sa.Column('task_id', sa.String(64), primary_key=True), sa.Column('user_id', sa.String(64), nullable=False, index=True),
        sa.Column('budget_id', sa.String(100), nullable=False), sa.Column('slot_id', sa.String(90), nullable=False),
        sa.Column('provider_id', sa.String(20), nullable=False, index=True), sa.Column('reserved_micros', sa.BigInteger(), nullable=False),
        sa.Column('actual_micros', sa.BigInteger()), sa.Column('state', sa.String(30), nullable=False),
        sa.Column('usage', sa.JSON(), nullable=False), sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('created_at', sa.String(40), nullable=False), sa.Column('updated_at', sa.String(40), nullable=False))
    providerTable = sa.table('providers', sa.column('id'), sa.column('enabled'), sa.column('message'), sa.column('concurrency'),
        sa.column('daily_micros'), sa.column('reserve_micros'), sa.column('context_limit'), sa.column('output_limit'), sa.column('updated_at'))
    op.bulk_insert(providerTable, [dict(id='qwen', enabled=True, message='识别与问答服务维护中，请稍后再试', concurrency=1,
        daily_micros=5000000, reserve_micros=5000000, context_limit=16000, output_limit=2000, updated_at='2026-10-13T00:00:00+00:00'),
        dict(id='image', enabled=True, message='生图与润色服务维护中，请稍后再试', concurrency=1,
        daily_micros=5000000, reserve_micros=5000000, context_limit=16000, output_limit=2000, updated_at='2026-10-13T00:00:00+00:00')])


def downgrade():
    raise RuntimeError('费用账本不可通过降级丢弃，请恢复一致的数据库备份')
