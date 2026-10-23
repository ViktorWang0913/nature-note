"""Allow full account cleanup control identifiers on PostgreSQL."""
from alembic import op
import sqlalchemy as sa

revision = 'h13a20261013'
down_revision = 'g13a20261013'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('platform_controls') as batch:
        batch.alter_column('id', existing_type=sa.String(40), type_=sa.String(100), existing_nullable=False)


def downgrade():
    raise RuntimeError('Control identifiers cannot be truncated safely')
