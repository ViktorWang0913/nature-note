"""Management, moderation and private chat records."""
from alembic import op
import sqlalchemy as sa

revision = 'f13a20261013'
down_revision = 'e13a20261013'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('deleted_at', sa.String(40), nullable=True))
        batch.add_column(sa.Column('last_seen_at', sa.String(40), nullable=True))
    print('[开始] 内容审核字段升级')
    for tableIndex, tableName in enumerate(('posts', 'comments'), 1):
        print(f'[开始] 审核表 {tableIndex}/2')
        with op.batch_alter_table(tableName) as batch:
            batch.add_column(sa.Column('review_status', sa.String(30), nullable=False, server_default='pending'))
            batch.add_column(sa.Column('review_reason', sa.String(300), nullable=False, server_default=''))
        print(f'[结束] 审核表 {tableIndex}/2')
    print('[结束] 内容审核字段升级')
    op.create_table('admin_accounts',
        sa.Column('id', sa.String(40), nullable=False, primary_key=True),
        sa.Column('username', sa.String(80), nullable=False),
        sa.Column('password_hash', sa.Text, nullable=False),
        sa.Column('must_change', sa.Boolean, nullable=False),
        sa.Column('failed_attempts', sa.Integer, nullable=False),
        sa.Column('locked_until', sa.String(40), nullable=True))
    op.create_table('admin_sessions',
        sa.Column('id', sa.String(64), nullable=False, primary_key=True),
        sa.Column('admin_id', sa.String(40), nullable=False),
        sa.Column('expires_at', sa.String(40), nullable=False),
        sa.Column('verified_at', sa.String(40), nullable=False))
    op.create_table('feedback',
        sa.Column('user_id', sa.String(64), nullable=False),
        sa.Column('category', sa.String(30), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('asset_ids', sa.JSON, nullable=False),
        sa.Column('task_id', sa.String(64), nullable=True),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('replies', sa.JSON, nullable=False),
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('announcements',
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('user_ids', sa.JSON, nullable=False),
        sa.Column('starts_at', sa.String(40), nullable=False),
        sa.Column('ends_at', sa.String(40), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('platform_controls',
        sa.Column('id', sa.String(40), nullable=False, primary_key=True),
        sa.Column('value', sa.JSON, nullable=False))
    op.create_table('species_corrections',
        sa.Column('user_id', sa.String(64), nullable=False),
        sa.Column('species_id', sa.String(64), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('scientific_name', sa.String(150), nullable=False),
        sa.Column('reason', sa.Text, nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('chat_sessions',
        sa.Column('user_id', sa.String(64), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('summary', sa.Text, nullable=False),
        sa.Column('summary_until', sa.String(40), nullable=True),
        sa.Column('deleted', sa.Boolean, nullable=False),
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('created_at', sa.String(40), nullable=False))
    op.create_table('chat_messages',
        sa.Column('user_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('task_id', sa.String(64), nullable=True),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('asset_id', sa.String(64), nullable=True),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('created_at', sa.String(40), nullable=False))


def downgrade():
    raise RuntimeError('管理记录与聊天不能通过降级丢弃，请恢复一致的备份')
