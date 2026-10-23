"""Read-only admin browsing must preserve authentication and content ownership."""
from PIL import Image
import pytest
from app import models as models, storage, billing
from app.db import SessionLocal
from test_management import AdminHeaders, NewUser


@pytest.fixture(autouse=True)
def IsolateAdminCookie(client):
    client.cookies.clear()
    yield
    client.cookies.clear()


def PrepareContent(client):
    user, userHeaders = NewUser(client)
    other, otherHeaders = NewUser(client)
    with SessionLocal() as database:
        imageData = storage.store_image(storage.encode(Image.new('RGBA', (40, 60), '#477954')))
        asset = models.Asset(user_id=user['id'], title='容量观察照片', source='photo', **imageData)
        foreign = models.Asset(user_id=other['id'], title='他人照片', source='photo', **imageData)
        database.add_all([asset, foreign])
        database.flush()
        project = models.Project(user_id=user['id'], title='完整设计验证', asset_ids=[asset.id],
            layout={'schema_version': 1, 'designMode': 'manual', 'width': 400, 'height': 600, 'background': '#ffffff',
                    'elements': [{'id': 'image', 'type': 'image', 'asset_id': asset.id,
                                  'url': 'https://untrusted.invalid/tracker', 'x': 0, 'y': 0, 'width': 40,
                                  'height': 60, 'rotation': 0, 'z': 1}]})
        task = models.Task(user_id=user['id'], kind='image_generation', status='succeeded', is_mock=True,
                           input={'prompt': '观察植物', 'asset_id': asset.id},
                           result={'image_key': asset.key, '_upstream_task_id': 'fixture-upstream', '_secret': 'do-not-expose'})
        database.add_all([project, task])
        database.commit()
        return {'user': user, 'headers': userHeaders, 'other': other, 'asset': asset.id,
                'foreign': foreign.id, 'project': project.id, 'task': task.id}


def test_admin_content_requires_separate_admin_session(client):
    data = PrepareContent(client)
    client.cookies.clear()
    assert client.get('/api/admin/explorer/generated', headers=data['headers']).status_code == 401
    assert client.get('/api/admin/content-media/task/' + data['task'], headers=data['headers']).status_code == 401


def test_generated_unsaved_result_and_saved_result_are_not_duplicated(client):
    data = PrepareContent(client)
    AdminHeaders(client)
    response = client.get('/api/admin/explorer/generated', params={'user_id': data['user']['id']})
    assert response.status_code == 200
    assert len(response.json()['items']) == 1
    assert response.json()['items'][0]['saved_asset_id'] is None
    detail = client.get('/api/admin/explorer/generated/' + data['task']).json()
    assert detail['upstream_id'] == 'fixture-upstream'
    assert '_secret' not in str(detail) and 'do-not-expose' not in str(detail)
    assert len(detail['references']) == 1
    assert client.get(detail['image_url']).status_code == 200
    thumbnail = client.get(response.json()['items'][0]['thumbnail_url'])
    assert thumbnail.status_code == 200 and thumbnail.headers['content-type'] == 'image/webp'
    assert 'no-store' in thumbnail.headers['cache-control']
    with SessionLocal() as database:
        database.get(models.Task, data['task']).saved_asset_id = data['asset']
        database.commit()
    assert len(client.get('/api/admin/explorer/generated', params={'user_id': data['user']['id']}).json()['items']) == 1


def test_project_preview_uses_saved_layout_and_scoped_media(client):
    data = PrepareContent(client)
    AdminHeaders(client)
    detail = client.get('/api/admin/explorer/projects/' + data['project']).json()
    imageUrl = detail['layout']['elements'][0]['url']
    assert imageUrl.startswith('/api/admin/content-media/project/')
    assert 'untrusted.invalid' not in str(detail)
    assert client.get(imageUrl).status_code == 200
    with SessionLocal() as database:
        database.get(models.Asset, data['asset']).deleted = True
        database.commit()
    # Deleted standalone files can still be retained by a valid saved project.
    assert client.get('/api/admin/content-media/asset/' + data['asset']).status_code == 404
    assert client.get(imageUrl).status_code == 200
    assert client.get('/api/admin/content-media/project/' + data['project'],
                      params={'asset_id': data['foreign'], 'version': 1}).status_code == 404
    with SessionLocal() as database:
        database.get(models.Project, data['project']).version = 2
        database.commit()
    assert client.get(imageUrl).status_code == 404


def test_deleted_and_closed_content_cannot_be_browsed(client):
    data = PrepareContent(client)
    AdminHeaders(client)
    with SessionLocal() as database:
        database.get(models.Task, data['task']).deleted = True
        database.get(models.Project, data['project']).deleted = True
        database.commit()
    assert client.get('/api/admin/explorer/tasks/' + data['task']).status_code == 404
    assert client.get('/api/admin/content-media/task/' + data['task']).status_code == 404
    assert client.get('/api/admin/explorer/projects/' + data['project']).status_code == 404
    with SessionLocal() as database:
        database.get(models.User, data['user']['id']).deleted_at = models.now()
        database.commit()
    assert client.get('/api/admin/content-media/asset/' + data['asset']).status_code == 404
    assert client.get('/api/admin/explorer/assets', params={'user_id': data['user']['id']}).json()['items'] == []


def test_user_detail_is_readonly_and_filters_search_and_pagination(client):
    data = PrepareContent(client)
    AdminHeaders(client)
    with SessionLocal() as database:
        user = database.get(models.User, data['user']['id'])
        budget = billing.Budget(database, user, 'image')
        database.commit()
        expectedLimit = budget.limit_micros
    detail = client.get('/api/admin/explorer/users/' + data['user']['id'])
    assert detail.status_code == 200, detail.text
    assert detail.json()['budgets'][0]['limit_micros'] == expectedLimit
    assert detail.json()['counts']['projects'] == 1
    assert client.get('/api/admin/explorer/projects', params={'q': '完整设计验证', 'user_id': data['user']['id']}).json()['items'][0]['id'] == data['project']
    assert client.get('/api/admin/explorer/projects', params={'q': '%', 'user_id': data['user']['id']}).json()['items'] == []
    assert client.get('/api/admin/explorer/tasks', params={'status': 'failed', 'user_id': data['user']['id']}).json()['items'] == []
    assert client.get('/api/admin/explorer/projects', params={'start': '2100-01-01'}).json()['items'] == []
    assert client.get('/api/admin/explorer/projects', params={'cursor': 'invalid'}).status_code == 422
    client.cookies.clear()


def test_saved_generated_asset_survives_deleted_history_and_is_deduplicated(client):
    data = PrepareContent(client)
    AdminHeaders(client)
    with SessionLocal() as database:
        asset = database.get(models.Asset, data['asset'])
        asset.source = 'generated'
        database.get(models.Task, data['task']).saved_asset_id = asset.id
        database.commit()
    query = {'user_id': data['user']['id']}
    before = client.get('/api/admin/explorer/generated', params=query).json()['items']
    assert len(before) == 1 and before[0]['record_section'] == 'tasks'
    with SessionLocal() as database:
        database.get(models.Task, data['task']).deleted = True
        database.commit()
    after = client.get('/api/admin/explorer/generated', params=query).json()['items']
    assert len(after) == 1 and after[0]['record_section'] == 'assets'
    assert client.get(after[0]['image_url']).status_code == 200
    assert client.get('/api/admin/explorer/assets/' + after[0]['id']).status_code == 200


def test_content_pagination_has_no_repeated_rows_for_unchanged_data(client):
    data = PrepareContent(client)
    AdminHeaders(client)
    with SessionLocal() as database:
        print('[开始] 分页作品准备，共 20 项')
        for itemIndex in range(20):
            print(f'[开始] 分页作品 {itemIndex+1}/20')
            database.add(models.Project(user_id=data['user']['id'], title='分页作品 ' + str(itemIndex)))
            print(f'[结束] 分页作品 {itemIndex+1}/20')
        print('[结束] 分页作品准备')
        database.commit()
    firstPage = client.get('/api/admin/explorer/projects', params={'user_id': data['user']['id']}).json()
    nextPage = client.get('/api/admin/explorer/projects',
                         params={'user_id': data['user']['id'], 'cursor': firstPage['next_cursor']}).json()
    firstIds = set(map(lambda record: record['id'], firstPage['items']))
    nextIds = set(map(lambda record: record['id'], nextPage['items']))
    assert len(firstIds) == 18 and len(nextIds) == 3 and not firstIds.intersection(nextIds)
