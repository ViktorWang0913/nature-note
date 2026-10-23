"""Separate GPS generation drafts from historical manual layouts."""
from alembic import op
import sqlalchemy as sa

revision = 'k14a20261014'
down_revision = 'j14a20261014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('projects', sa.Column('route_draft', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('nodes', sa.Column('place_name', sa.String(120), nullable=False, server_default=''))


def downgrade():
    raise RuntimeError('观察框架及地点名称不可直接丢弃，请恢复一致的备份')
