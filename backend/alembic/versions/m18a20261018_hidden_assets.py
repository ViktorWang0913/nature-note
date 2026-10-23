"""Keep public material removal private to each account."""
from alembic import op
from app.models import HiddenAsset

revision = 'm18a20261018'
down_revision = 'l15a20261015'
branch_labels = None
depends_on = None


def upgrade():
    # 回退只还原版本标记，保留账号移除记录；再次安装复用该表。
    HiddenAsset.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table('hidden_assets')
