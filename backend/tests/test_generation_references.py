from app import models as m
from app.db import SessionLocal


def test_history_reference_is_visible_only_when_accessible(client, users):
    user, headers = users[0]
    otherUser, otherHeaders = users[1]
    with SessionLocal() as db:
        ownAsset = m.Asset(user_id=user['id'], key='own.png', original_key='own.png', thumbnail_key='own.png', width=10, height=10)
        otherAsset = m.Asset(user_id=otherUser['id'], key='other.png', original_key='other.png', thumbnail_key='other.png', width=10, height=10)
        db.add_all([ownAsset, otherAsset])
        db.flush()
        session = m.GenerationSession(user_id=user['id'], title='参考图归属', messages=[
            {'role': 'user', 'text': '我的参考图', 'asset_id': ownAsset.id},
            {'role': 'user', 'text': '不可访问的素材', 'asset_id': otherAsset.id},
            {'role': 'user', 'text': '纯文字'},
        ])
        db.add(session)
        db.commit()
        sessionId, assetId = session.id, ownAsset.id
    response = client.get('/api/v1/sessions/' + sessionId, headers=headers)
    assert response.status_code == 200
    messages = response.json()['messages']
    assert messages[0]['asset_url']
    assert 'asset_url' not in messages[1]
    assert 'asset_url' not in messages[2]
    assert client.get('/api/v1/sessions/' + sessionId, headers=otherHeaders).status_code == 404
    with SessionLocal() as db:
        db.get(m.Asset, assetId).deleted = True
        db.commit()
    assert 'asset_url' not in client.get('/api/v1/sessions/' + sessionId, headers=headers).json()['messages'][0]
