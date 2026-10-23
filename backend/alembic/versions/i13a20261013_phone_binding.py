"""Persist verified phone binding without raw phone numbers."""
from alembic import op
import sqlalchemy as sa

revision = 'i13a20261013'
down_revision = 'h13a20261013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_phones', sa.Column('user_id', sa.String(64), primary_key=True),
        sa.Column('phone_hash', sa.String(64), nullable=False), sa.Column('masked_number', sa.String(30), nullable=False),
        sa.Column('verified_at', sa.String(40), nullable=False))


def downgrade():
    raise RuntimeError('Phone verification records require an explicit retention decision before removal')
