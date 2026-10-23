"""Private, user-confirmed atlas and deletion archives; preserves legacy records."""
import hashlib
import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = 'd13a20261013'
down_revision = 'c05f924aa6b1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('species') as batch:
        batch.add_column(sa.Column('user_id', sa.String(64), nullable=True))
        batch.add_column(sa.Column('group_key', sa.String(64), nullable=False, server_default=''))
        batch.add_column(sa.Column('cover_asset_id', sa.String(64), nullable=True))
        batch.create_index('ix_species_user_id', ['user_id'])
        batch.create_index('ix_species_group_key', ['group_key'])
    with op.batch_alter_table('observations') as batch:
        batch.add_column(sa.Column('evidence', sa.JSON(), nullable=False, server_default='{}'))
        batch.add_column(sa.Column('confirmed_by', sa.String(30), nullable=False, server_default='user'))
        batch.add_column(sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table('archives',
        sa.Column('id', sa.String(64), primary_key=True), sa.Column('created_at', sa.String(40), nullable=False),
        sa.Column('user_id', sa.String(64), nullable=False, index=True),
        sa.Column('resource_type', sa.String(40), nullable=False, index=True),
        sa.Column('resource_id', sa.String(64), nullable=False, index=True),
        sa.Column('snapshot', sa.JSON(), nullable=False), sa.Column('reason', sa.String(200), nullable=False),
        sa.Column('expires_at', sa.String(40), nullable=True))
    op.create_table('audit_events',
        sa.Column('id', sa.String(64), primary_key=True), sa.Column('created_at', sa.String(40), nullable=False),
        sa.Column('actor_id', sa.String(64), nullable=False, index=True),
        sa.Column('action', sa.String(80), nullable=False, index=True),
        sa.Column('target_id', sa.String(64), nullable=False), sa.Column('detail', sa.JSON(), nullable=False))
    connection = op.get_bind()
    metadata = sa.MetaData()
    speciesTable = sa.Table('species', metadata, autoload_with=connection)
    observationTable = sa.Table('observations', metadata, autoload_with=connection)
    archiveTable = sa.Table('archives', metadata, autoload_with=connection)
    records = connection.execute(sa.select(observationTable).order_by(observationTable.c.created_at.desc(), observationTable.c.id.desc())).mappings().all()
    seenPhotos = set()
    print(f'[开始] 迁移个人图鉴，共 {len(records)} 条')
    for recordIndex, record in enumerate(records, 1):
        print(f'[开始] 迁移观察 {recordIndex}/{len(records)}')
        photoKey = (record['user_id'], record['asset_id'])
        print('[开始] 重复观察检查')
        if photoKey in seenPhotos:
            print('[分支] 归档历史重复记录，保留最新记录')
            connection.execute(archiveTable.insert().values(id=record['id'], created_at=datetime.now(timezone.utc).isoformat(),
                user_id=record['user_id'], resource_type='observation', resource_id=record['id'],
                snapshot=dict(record), reason='迁移重复观察记录'))
            connection.execute(observationTable.delete().where(observationTable.c.id == record['id']))
            print('[结束] 重复观察检查')
            print(f'[结束] 迁移观察 {recordIndex}/{len(records)}；跳过已归档重复记录')
            continue
        else:
            print('[分支] 保留观察记录')
        print('[结束] 重复观察检查')
        seenPhotos.add(photoKey)
        source = connection.execute(sa.select(speciesTable).where(speciesTable.c.id == record['species_id'])).mappings().first()
        print('[开始] 旧物种转个人条目')
        if source:
            print('[分支] 按用户复制旧物种')
            groupKey = hashlib.sha256(('s:' + source['scientific_name'].strip().casefold() if source['scientific_name'].strip() else 'n:' + source['name'].strip()).encode()).hexdigest()
            privateId = hashlib.sha256((record['user_id'] + ':' + groupKey).encode()).hexdigest()
            existing = connection.execute(sa.select(speciesTable.c.id).where(speciesTable.c.id == privateId)).first()
            print('[开始] 个人物种存在检查')
            if not existing:
                print('[分支] 创建个人物种')
                values = dict(source)
                values.update(id=privateId, user_id=record['user_id'], group_key=groupKey, cover_asset_id=record['asset_id'])
                connection.execute(speciesTable.insert().values(**values))
            else:
                print('[分支] 复用个人物种')
            print('[结束] 个人物种存在检查')
            connection.execute(observationTable.update().where(observationTable.c.id == record['id']).values(species_id=privateId))
        else:
            print('[分支] 保留未归档记录')
        print('[结束] 旧物种转个人条目')
        print(f'[结束] 迁移观察 {recordIndex}/{len(records)}')
    print('[结束] 迁移个人图鉴')
    with op.batch_alter_table('observations') as batch:
        batch.create_unique_constraint('uq_observation_photo', ['user_id', 'asset_id'])


def downgrade():
    raise RuntimeError('个人图鉴迁移保留了归档数据；回退请恢复升级前备份，禁止自动丢弃记录')
