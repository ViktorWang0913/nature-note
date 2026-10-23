from copy import deepcopy
from types import SimpleNamespace
from app import route_notes, models as m, visual_ai, storage
from app.db import SessionLocal
from PIL import Image


def test_background_input_contains_no_photos_and_preserves_breaks(monkeypatch):
    source = {'id': 'track', 'points': [
        {'latitude': 31, 'longitude': 121, 'timestamp': '2026-10-14T00:00:00+00:00', 'sequence': 0, 'segment': 0},
        {'latitude': 31.001, 'longitude': 121.001, 'timestamp': '2026-10-14T00:01:00+00:00', 'sequence': 1, 'segment': 0},
        {'latitude': 31.003, 'longitude': 121.002, 'timestamp': '2026-10-14T00:02:00+00:00', 'sequence': 2, 'segment': 1}],
        'nodes': [{'id': 'node', 'latitude': 31, 'longitude': 121, 'time': '2026-10-14T00:00:00+00:00', 'place_name': '公园', 'text': '草地'}]}
    graph = route_notes.BuildGraph(source, SimpleNamespace(id='style', cover_key='style.png'))
    assert (graph['width'], graph['height']) == (1024, 1536)
    assert len(graph['edges']) == 1
    assert graph['edges'][0]['endSequence'] == 1
    assert not any('image_key' in node or 'asset_ids' in node for node in graph['nodes'])
    assert storage.image_bytes(route_notes.Render(graph)).size == (1024, 1536)
    graph['description'] = '公园草地'
    calls = []
    monkeypatch.setattr(visual_ai, '_reference', lambda key: 'style-reference')
    monkeypatch.setattr(visual_ai, 'GenerateImage', lambda *args: calls.append(args) or {'image_key': 'result'})
    task = SimpleNamespace(input={'snapshot': graph, 'draftVersion': 2})
    result = route_notes.Generate(None, task)
    assert result['mode'] == 'background-v1'
    assert len(calls[0][3]) == 2 and calls[0][4] == '1024x1536'
    assert '严禁任何文字' in calls[0][2]


def test_saved_notebook_ownership_delete_reload_and_concurrency(client, users):
    user, headers = users[0]
    otherUser, otherHeaders = users[1]
    project = client.post('/api/v1/projects', headers=headers, json={'title': '新版笔记验收'}).json()
    with SessionLocal() as db:
        background = m.Asset(user_id=user['id'], title='背景', source='notebook_background', category='environment',
            **storage.store_image(storage.encode(Image.new('RGB', (1024, 1536))), keep_original=False))
        photo = m.Asset(user_id=user['id'], title='原图', source='photo', category='unclassified',
            **storage.store_image(storage.encode(Image.new('RGB', (40, 40))), keep_original=False))
        foreign = m.Asset(user_id=otherUser['id'], title='其他用户', source='generated', category='unclassified',
            **storage.store_image(storage.encode(Image.new('RGB', (40, 40))), keep_original=False))
        db.add_all([background, photo, foreign]);db.flush()
        task = m.Task(user_id=user['id'], kind='image_polish', status='succeeded',
            input={'project_id': project['id'], 'mode': 'background-v1'}, saved_asset_id=background.id)
        db.add(task);db.commit()
        backgroundId, photoId, foreignId, taskId = background.id, photo.id, foreign.id, task.id
    layout = {'schema_version': 1, 'notebookVersion': 1, 'backgroundTaskId': taskId,
        'width': 1024, 'height': 1536, 'background': '#ffffff', 'elements': [
            {'id': 'background', 'type': 'image', 'asset_id': backgroundId, 'x': 0, 'y': 0, 'width': 1024, 'height': 1536, 'rotation': 0, 'z': 0},
            {'id': 'text', 'type': 'text', 'text': '公园发现', 'x': 50, 'y': 50, 'width': 500, 'height': 200, 'rotation': 15, 'z': 1,
             'fontSize': 42, 'fontFamily': 'serif', 'fontWeight': 'bold', 'textAlign': 'center', 'color': '#253d32', 'textBackground': '#ffffff'}]}
    endpoint = '/api/v1/projects/' + project['id']
    saved = client.patch(endpoint, headers=headers, json={'base_version': 1, 'layout': layout})
    assert saved.status_code == 200, saved.text
    assert client.get(endpoint, headers=headers).json()['layout']['elements'][1]['textAlign'] == 'center'
    assert client.get(endpoint, headers=otherHeaders).status_code == 404
    assert client.patch(endpoint, headers=headers, json={'base_version': 1, 'layout': layout}).status_code == 409
    print('[开始] 非法图片来源校验，共 2 项')
    for caseIndex, (assetId, status) in enumerate([(photoId, 422), (foreignId, 404)], 1):
        print(f'[开始] 来源 {caseIndex}/2')
        invalid = deepcopy(layout)
        invalid['elements'][1] = {'id': 'material', 'type': 'image', 'asset_id': assetId, 'x': 50, 'y': 50, 'width': 100, 'height': 100, 'rotation': 0, 'z': 1}
        response = client.patch(endpoint, headers=headers, json={'base_version': 2, 'layout': invalid})
        assert response.status_code == status, response.text
        print(f'[结束] 来源 {caseIndex}/2')
    print('[结束] 非法图片来源校验')
    layout['elements'].pop()
    assert client.patch(endpoint, headers=headers, json={'base_version': 2, 'layout': layout}).status_code == 200
    assert len(client.get(endpoint, headers=headers).json()['layout']['elements']) == 1
    assert backgroundId not in {item['id'] for item in client.get('/api/v1/assets?source=generated', headers=headers).json()['items']}


def test_old_layout_and_summary_rejected(client, users):
    _, headers = users[0]
    project = client.post('/api/v1/projects', headers=headers, json={'title': '旧流程拒绝'}).json()
    response = client.patch('/api/v1/projects/' + project['id'], headers=headers,
        json={'base_version': 1, 'layout': project['layout']})
    assert response.status_code == 422
    response = client.post('/api/v1/tasks', headers=headers, json={'kind': 'route_summary', 'input': {'project_id': project['id']}})
    assert response.status_code == 422
