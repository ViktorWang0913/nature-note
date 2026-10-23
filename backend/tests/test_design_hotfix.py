from copy import deepcopy
import io
import pytest
from PIL import Image
from app import models as models, storage
from app.db import SessionLocal

# 参数设置
blankLayout = {'schema_version': 1, 'notebookVersion': 1, 'designMode': 'manual',
    'width': 1024, 'height': 1536, 'background': '#ffffff', 'elements': []}


# 自编函数
def UploadMaterial(client, headers):
    imageBuffer = io.BytesIO()
    Image.new('RGB', (24, 24), '#448866').save(imageBuffer, format='PNG')
    response = client.post('/api/v1/assets/upload', headers=headers,
        files={'file': ('leaf.png', imageBuffer.getvalue(), 'image/png')}, data={'operation_id': models.uid()})
    assert response.status_code == 200, response.text
    return response.json()


def ImageLayout(assetId):
    return {**deepcopy(blankLayout), 'elements': [{'id': 'leaf', 'type': 'image', 'asset_id': assetId,
        'x': 80, 'y': 120, 'width': 240, 'height': 240, 'rotation': 35, 'z': 1,
        'flipX': True, 'flipY': False, 'locked': True}]}


def test_ManualSaveReloadRetryAndIsolation(client, users):
    _, headers = users[0]
    _, otherHeaders = users[1]
    asset = UploadMaterial(client, headers)
    payload = {'title': '独立自然笔记', 'layout': ImageLayout(asset['id']), 'operation_id': models.uid()}
    response = client.post('/api/v1/projects', headers=headers, json=payload)
    assert response.status_code == 200, response.text
    project = response.json()
    assert client.post('/api/v1/projects', headers=headers, json=payload).json()['id'] == project['id']
    endpoint = '/api/v1/projects/' + project['id']
    loaded = client.get(endpoint, headers=headers).json()
    assert loaded['layout']['elements'][0]['flipX'] is True
    assert client.get(loaded['layout']['elements'][0]['url']).status_code == 200
    assert client.get(endpoint, headers=otherHeaders).status_code == 404
    assert client.patch(endpoint, headers=headers, json={'base_version': 1, 'layout': blankLayout}).status_code == 200
    assert client.patch(endpoint, headers=headers, json={'base_version': 1, 'layout': blankLayout}).status_code == 409
    assert client.get(endpoint, headers=headers).json()['layout']['elements'] == []


def test_DeletedMaterialKeepsSavedDesignAndCannotBeReused(client, users):
    _, headers = users[0]
    asset = UploadMaterial(client, headers)
    layout = ImageLayout(asset['id'])
    project = client.post('/api/v1/projects', headers=headers, json={'layout': layout}).json()
    endpoint = '/api/v1/assets/' + asset['id']
    assert client.delete(endpoint, headers=headers).status_code == 200
    assert client.delete(endpoint, headers=headers).status_code == 200
    assert client.get(endpoint, headers=headers).status_code == 404
    assert client.get(asset['url']).status_code == 404
    assert asset['id'] not in {item['id'] for item in client.get('/api/v1/assets', headers=headers).json()['items']}
    restored = client.get('/api/v1/projects/' + project['id'], headers=headers).json()
    assert client.get(restored['layout']['elements'][0]['url']).status_code == 200
    assert client.patch('/api/v1/projects/' + project['id'], headers=headers,
        json={'base_version': 1, 'layout': layout}).status_code == 200
    assert client.post('/api/v1/projects', headers=headers, json={'layout': layout}).status_code == 404


def test_PublicRemovalIsPrivateAndRetainsSavedReferences(client, users):
    _, headers = users[0]
    _, otherHeaders = users[1]
    with SessionLocal() as database:
        asset = models.Asset(title='公共叶片隔离验收', source='public',
            **storage.store_image(storage.encode(Image.new('RGBA', (24, 24), '#338855'))))
        database.add(asset)
        database.commit()
        assetId = asset.id
    layout = ImageLayout(assetId)
    project = client.post('/api/v1/projects', headers=headers, json={'layout': layout}).json()
    endpoint = '/api/v1/assets/' + assetId
    assert client.delete(endpoint, headers=headers).json()['scope'] == 'library'
    assert client.delete(endpoint, headers=headers).status_code == 200
    assert client.get(endpoint, headers=headers).status_code == 404
    assert client.get(endpoint, headers=otherHeaders).status_code == 200
    assert assetId not in {item['id'] for item in client.get('/api/v1/assets?source=public', headers=headers).json()['items']}
    assert assetId in {item['id'] for item in client.get('/api/v1/assets?source=public', headers=otherHeaders).json()['items']}
    assert client.patch('/api/v1/projects/' + project['id'], headers=headers,
        json={'base_version': 1, 'layout': layout}).status_code == 200
    assert client.post('/api/v1/projects', headers=headers, json={'layout': layout}).status_code == 404


def test_ManualModeCannotBypassBackgroundOrForeignAssetChecks(client, users):
    _, headers = users[0]
    _, otherHeaders = users[1]
    asset = UploadMaterial(client, otherHeaders)
    assert client.post('/api/v1/projects', headers=headers, json={'layout': ImageLayout(asset['id'])}).status_code == 404
    assert client.delete('/api/v1/assets/' + asset['id'], headers=headers).status_code == 404
    project = client.post('/api/v1/projects', headers=headers, json={'title': 'GPS 笔记'}).json()
    assert client.patch('/api/v1/projects/' + project['id'], headers=headers,
        json={'base_version': 1, 'layout': blankLayout}).status_code == 422
    invalid = {**blankLayout, 'backgroundTaskId': 'forged-task'}
    assert client.post('/api/v1/projects', headers=headers, json={'layout': invalid}).status_code == 422


@pytest.mark.parametrize('fieldName,fieldValue', [('background', 'url(evil)'), ('width', 0), ('notebookVersion', 2)])
def test_InvalidManualLayoutsRejected(client, users, fieldName, fieldValue):
    _, headers = users[0]
    response = client.post('/api/v1/projects', headers=headers, json={'layout': {**blankLayout, fieldName: fieldValue}})
    assert response.status_code == 422


@pytest.mark.parametrize('method,path,payload', [
    ('GET', '/posts', None), ('GET', '/posts/old-post', None),
    ('POST', '/posts', {'title': '旧入口', 'text': '', 'asset_ids': []}),
    ('PUT', '/posts/old-post/like', {'liked': True}),
    ('GET', '/posts/old-post/comments', None),
    ('POST', '/posts/old-post/comments', {'text': '评论'}),
    ('DELETE', '/comments/old-comment', None),
    ('PUT', '/users/another-user/follow', {'following': True}),
    ('GET', '/users', None)])
def test_CommunityLocked(client, users, method, path, payload):
    _, headers = users[0]
    response = client.request(method, '/api/v1' + path, headers=headers, json=payload)
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'community_testing'


def test_CommunityOldFileLinksLocked(client, users):
    user, headers = users[0]
    with SessionLocal() as database:
        fileKey = storage.put(storage.encode(Image.new('RGB', (24, 24), '#224466')))
        post = models.Post(user_id=user['id'], title='旧帖子', text='', images=[fileKey])
        database.add(post)
        database.commit()
        oldUrl = storage.url(fileKey, 'post', post.id)
    assert client.get(oldUrl).status_code == 404
    assert client.get('/api/v1/notifications', headers=headers).status_code == 200


def test_MigrationReinstallKeepsAccountRemoval(client, users):
    from alembic import command
    from alembic.config import Config
    user, headers = users[0]
    asset = UploadMaterial(client, headers)
    with SessionLocal() as database:
        database.add(models.HiddenAsset(user_id=user['id'], asset_id=asset['id']))
        database.commit()
    command.stamp(Config('alembic.ini'), 'l15a20261015')
    command.upgrade(Config('alembic.ini'), 'head')
    with SessionLocal() as database:
        assert database.get(models.HiddenAsset, (user['id'], asset['id'])) is not None
