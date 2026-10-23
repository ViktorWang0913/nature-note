"""Bound query count and preserve private media when accelerating page loads."""
from unittest.mock import Mock
from sqlalchemy import event
from app import models as m, storage
from app.db import SessionLocal


def test_asset_list_queries_do_not_grow_per_item(client, users):
    user, headers = users[0]
    with SessionLocal() as db:
        print('[开始] 准备百张素材')
        for assetIndex in range(100):
            print(f'[开始] 素材 {assetIndex+1}/100')
            db.add(m.Asset(id='perf-asset-'+str(assetIndex), user_id=user['id'], title='perf-list-'+str(assetIndex),
                source='generated', key='private/perf-'+str(assetIndex)+'.png',
                original_key='private/original.png', thumbnail_key='private/thumb.png', width=1254, height=1254))
            print(f'[结束] 素材 {assetIndex+1}/100')
        print('[结束] 准备百张素材')
        db.add(m.Favorite(user_id=user['id'], asset_id='perf-asset-0'))
        db.commit()
    statements = []

    def RecordQuery(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = SessionLocal.kw['bind']
    event.listen(engine, 'before_cursor_execute', RecordQuery)
    response = client.get('/api/v1/assets?q=perf-list-&limit=100', headers=headers)
    event.remove(engine, 'before_cursor_execute', RecordQuery)
    assert response.status_code == 200
    assert len(response.json()['items']) == 100
    assert sum('favorites' in statement.lower() for statement in statements) == 1
    assert [asset['id'] for asset in response.json()['items'] if asset['favorite']] == ['perf-asset-0']
    assert client.get('/api/v1/assets?q=perf-list-&limit=100', headers=users[1][1]).json()['items'] == []


def test_featured_assets_only_returns_two_preview_urls(client, users):
    user, headers = users[0]
    with SessionLocal() as db:
        db.add(m.Asset(id='perf-photo', user_id=user['id'], title='首页照片', source='photo',
            key='private/perf-photo.png', original_key='private/perf-photo.png', thumbnail_key='private/perf-thumb.png',
            width=1254, height=1254, created_at='2099-01-01'))
        db.commit()
    response = client.get('/api/v1/assets/featured', headers=headers)
    assert response.status_code == 200
    assert set(response.json()) == {'photo', 'illustration'}
    assert 'private/perf-thumb.png' in response.json()['photo']
    assert 'preview=1' in response.json()['photo']
    assert 'private/perf-thumb.png' not in client.get('/api/v1/assets/featured', headers=users[1][1]).json()['photo']


def test_warm_preview_does_not_wait_for_cold_encoders(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, 'local_path', lambda key: tmp_path / 'warm.webp')
    (tmp_path / 'warm.webp').write_bytes(b'already-encoded')
    blockedSlots = Mock()
    monkeypatch.setattr(storage, 'previewSlots', blockedSlots)
    assert storage.PreviewPath('private/old.png').read_bytes() == b'already-encoded'
    assert not blockedSlots.mock_calls
