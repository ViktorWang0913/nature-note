import io
from urllib.parse import urlsplit
from PIL import Image
from app import storage, visual_ai


def picture(color='green'):
    buffer = io.BytesIO()
    exif = Image.Exif()
    exif[270] = 'private-location'
    Image.new('RGB', (100, 80), color).save(buffer, 'JPEG', exif=exif)
    return buffer.getvalue()


def request(client, method, url, headers, **kwargs):
    response = client.request(method, '/api/v1' + url, headers=headers, **kwargs)
    assert 200 <= response.status_code < 300, response.text
    return response.json()


def test_private_upload_version_and_track(client, users):
    _, a = users[0]
    _, b = users[1]
    upload = lambda op: request(client, 'POST', '/assets/upload', a, files={'file': ('bird.jpg', picture(), 'image/jpeg')}, data={'operation_id': op, 'category': 'birds'})
    photo = upload('photo-one')
    assert photo['id'] == upload('photo-one')['id'] == upload('photo-duplicate-content')['id']
    assert client.get('/api/v1/assets/' + photo['id'], headers=b).status_code == 404
    signed = urlsplit(photo['url'])
    assert client.get(signed.path + '?' + signed.query).status_code == 200
    assert client.get(signed.path + '?expires=1&signature=bad').status_code == 403
    project = request(client, 'POST', '/projects', a, json={'title': '记录一'})
    updated = request(client, 'PATCH', '/projects/' + project['id'], a, json={'base_version': 1, 'asset_ids': [photo['id']]})
    assert updated['version'] == 2
    assert client.patch('/api/v1/projects/' + project['id'], headers=a, json={'base_version': 1, 'title': 'stale'}).status_code == 409
    assert client.get('/api/v1/projects/' + project['id'], headers=b).status_code == 404
    assert client.patch('/api/v1/projects/' + project['id'], headers=b, json={'base_version': 2}).status_code == 404
    track = request(client, 'POST', '/tracks', a, json={'project_id': project['id'], 'title': '路线', 'operation_id': 'track-once'})
    assert track['id'] == request(client, 'POST', '/tracks', a, json={'project_id': project['id'], 'operation_id': 'track-once'})['id']
    point = {'sequence': 0, 'latitude': 31.3, 'longitude': 121.5, 'accuracy': 8, 'timestamp': '2026-10-02T08:00:00+08:00', 'segment': 0}
    assert request(client, 'POST', f"/tracks/{track['id']}/points", a, json={'points': [point]})['accepted'] == 1
    assert request(client, 'POST', f"/tracks/{track['id']}/points", a, json={'points': [point]})['accepted'] == 0
    node_data = {'latitude': 31.3, 'longitude': 121.5, 'asset_ids': [photo['id']], 'cover_asset_id': photo['id'], 'operation_id': 'node-once'}
    node = request(client, 'POST', f"/tracks/{track['id']}/nodes", a, json=node_data)
    assert node['id'] == request(client, 'POST', f"/tracks/{track['id']}/nodes", a, json=node_data)['id']
    assert client.get('/api/v1/nodes/' + node['id'], headers=b).status_code == 404
    request(client, 'PATCH', f"/tracks/{track['id']}", a, json={'status': 'ended'})
    point.update(sequence=1, segment=1)
    assert request(client, 'POST', f"/tracks/{track['id']}/points", a, json={'points': [point]})['accepted'] == 1
    edited = request(client, 'POST', '/assets/' + photo['id'] + '/edit', a, json={'crop': {'x': 0, 'y': 0, 'width': .5, 'height': .5}, 'save_as_copy': True})
    assert (edited['width'], edited['height']) == (50, 40)
    assert edited['original_asset_id'] == photo['id']


def test_generation_confirm_and_moderated_share(client, users, monkeypatch):
    def FakeExecute(db, task, user):
        print('[开始] 隔离服务商模拟分派')
        if task.kind == 'image_recognition':
            print('[分支] 返回模型候选')
            result = {'is_mock':False, 'candidates':[{'name':'白头鹎','scientific_name':'Pycnonotus sinensis','confidence':80}], '_actual_micros':0}
        else:
            print('[分支] 返回图片结果')
            stored = storage.store_image(picture('orange'), keep_original=False)
            result = {'is_mock':False, 'image_key':stored['key'], 'text':'测试图片', '_actual_micros':0}
        print('[结束] 隔离服务商模拟分派')
        return result
    monkeypatch.setattr(visual_ai, 'execute', FakeExecute)
    person_a, a = users[0]
    person_b, b = users[1]
    photo = request(client, 'POST', '/assets/upload', a, files={'file': ('bulbul.jpg', picture('olive'), 'image/jpeg')}, data={'operation_id': 'flow-photo'})
    session = request(client, 'POST', '/sessions', a, json={'title': '白头鹎'})
    task = request(client, 'POST', '/tasks', a, json={'kind': 'image_generation', 'input': {'asset_id': photo['id'], 'style_id': 'cartoon', 'prompt': '保留白头鹎', 'session_id': session['id']}})
    result = request(client, 'GET', '/tasks/' + task['id'], a)
    assert result['status'] == 'succeeded' and result['result']['is_mock'] is False
    assert client.get('/api/v1/tasks/' + task['id'], headers=b).status_code == 404
    generated = request(client, 'POST', '/tasks/' + task['id'] + '/save', a)
    assert not generated['is_mock'] and generated['source'] == 'generated'
    assert generated['id'] == request(client, 'POST', '/tasks/' + task['id'] + '/save', a)['id']
    recognition = request(client, 'POST', '/tasks', a, json={'kind': 'image_recognition', 'input': {'asset_id': photo['id']}})
    candidate = request(client, 'GET', '/tasks/' + recognition['id'], a)['result']['candidates'][0]
    assert candidate['confidence'] == 80
    observation = request(client, 'POST', '/observations', a, json={'asset_id': photo['id'], 'species_name': candidate['name'], 'scientific_name':candidate['scientific_name'], 'text': '只有我知道的庭院记录', 'is_mock': True})
    assert observation['confirmation'] == 'confirmed'
    assert request(client, 'GET', '/species/'+observation['species_id'], a)['photo_count'] == 1
    assert client.get('/api/v1/species/'+observation['species_id'], headers=b).status_code == 404
    assert len(request(client, 'GET', '/observations?asset_id=' + photo['id'], a)['items']) == 1
    assert request(client, 'GET', '/knowledge/search?q=只有我知道&scope=mine', a)['items']
    assert not request(client, 'GET', '/knowledge/search?q=只有我知道&scope=mine', b)['items']
    response = client.post('/api/v1/posts', headers=a, json={'title': '观察笔记',
        'text': '分享', 'asset_ids': [photo['id'], generated['id']], 'operation_id': 'post-once'})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'community_testing'
    assert client.get('/api/v1/assets/' + generated['id'], headers=a).status_code == 200
    assert client.get('/api/v1/posts?feed=following', headers=b).status_code == 503
    notificationKinds = {item['type'] for item in request(client, 'GET', '/notifications', a)['items']}
    assert not notificationKinds.intersection({'like', 'follow', 'comment'})
    assert 'ai' in notificationKinds


def test_export_and_layout_reference_authorization(client, users):
    _, a = users[0]
    _, b = users[1]
    asset = request(client, 'POST', '/assets/upload', b, files={'file': ('private.jpg', picture('blue'), 'image/jpeg')}, data={'operation_id': 'private-blue'})
    project = request(client, 'POST', '/projects', a, json={'title': '导出项目'})
    layout = {'schema_version': 1, 'width': 3600, 'height': 2400, 'background': '#ffffff', 'elements': [{'id': 'image', 'type': 'image', 'asset_id': asset['id'], 'x': 0, 'y': 0, 'width': 100, 'height': 80, 'z': 0, 'rotation': 0}]}
    assert client.patch('/api/v1/projects/' + project['id'], headers=a, json={'base_version': 1, 'layout': layout}).status_code == 404
    exported = request(client, 'POST', '/exports', a, files={'file': ('note.jpg', picture(), 'image/jpeg')}, data={'project_id': project['id'], 'operation_id': 'export-jpeg'})
    assert '.jpg?' in exported['url']
    assert exported['source'] == 'export'
    assert client.post('/api/v1/exports', headers=b, files={'file': ('note.jpg', picture(), 'image/jpeg')}, data={'project_id': project['id'], 'operation_id': 'steal'}).status_code == 404
