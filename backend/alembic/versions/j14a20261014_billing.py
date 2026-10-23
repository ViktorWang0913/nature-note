"""Freeze task prices and persist individual upstream call accounting."""
from alembic import op
import sqlalchemy as sa

revision = 'j14a20261014'
down_revision = 'i13a20261013'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('charges', sa.Column('pricing', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('charges', sa.Column('metering', sa.JSON(), nullable=False, server_default='{}'))
    # Only replace the original blanket reservation; existing charges retain their holds.
    op.execute("UPDATE providers SET reserve_micros=100000 WHERE id='qwen' AND reserve_micros=5000000")
    op.execute("UPDATE providers SET reserve_micros=1000000 WHERE id='image' AND reserve_micros=5000000")


def downgrade():
    raise RuntimeError('计费快照和调用账本不能通过降级丢弃，请恢复一致的备份')
