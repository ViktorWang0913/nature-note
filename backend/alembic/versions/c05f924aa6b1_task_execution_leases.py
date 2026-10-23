"""Durable task leases for worker-loss recovery."""
from alembic import op
import sqlalchemy as sa

revision = 'c05f924aa6b1'
down_revision = 'b9661c71856e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks') as batch:
        batch.add_column(sa.Column('lease_owner', sa.String(64), nullable=True))
        batch.add_column(sa.Column('lease_until', sa.String(40), nullable=True))
        batch.create_index('ix_tasks_lease_until', ['lease_until'])


def downgrade():
    with op.batch_alter_table('tasks') as batch:
        batch.drop_index('ix_tasks_lease_until')
        batch.drop_column('lease_until')
        batch.drop_column('lease_owner')
