"""Revoke deleted generation sessions without deleting separately saved assets."""
from alembic import op
import sqlalchemy as sa
revision = 'g13a20261013'
down_revision = 'f13a20261013'
branch_labels = None
depends_on = None


def upgrade():
    print('[开始] 会话删除标记升级')
    for tableIndex, tableName in enumerate(('generation_sessions', 'tasks'), 1):
        print(f'[开始] 会话删除字段 {tableIndex}/2')
        with op.batch_alter_table(tableName) as batch:
            batch.add_column(sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
        print(f'[结束] 会话删除字段 {tableIndex}/2')
    print('[结束] 会话删除标记升级')


def downgrade():
    raise RuntimeError('删除标记不能通过降级撤销，请恢复一致备份')
