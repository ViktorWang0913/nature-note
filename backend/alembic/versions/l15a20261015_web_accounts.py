"""Independent browser credentials and revocable sessions."""
from alembic import op
from app.models import WebCredential, WebSession, WebLoginAttempt

revision = 'l15a20261015'
down_revision = 'k14a20261014'
branch_labels = None
depends_on = None


def upgrade():
    WebCredential.__table__.create(op.get_bind(), checkfirst=True)
    WebSession.__table__.create(op.get_bind(), checkfirst=True)
    WebLoginAttempt.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('账户迁移不可直接回退，请恢复一致的备份')
