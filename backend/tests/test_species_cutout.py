"""Photo-derived material contracts: alpha, provenance, recovery and actual billing."""
import base64
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import httpx
import pytest
from PIL import Image, ImageDraw

from app import billing, jobs, models as m, storage, visual_ai
from app.config import settings
from app.db import SessionLocal
from app.routers import ai
from test_management import NewUser


def CutoutPicture():
    picture = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
    ImageDraw.Draw(picture).ellipse((20, 15, 80, 85), fill=(80, 130, 50, 255))
    return picture


def OpaquePicture(background='white'):
    picture = Image.new('RGBA', (100, 100), background)
    picture.alpha_composite(CutoutPicture())
    return picture.convert('RGB')


def UploadPhoto(client, headers):
    result = client.post('/api/v1/assets/upload', headers=headers,
        files={'file': ('bird.png', storage.encode(Image.new('RGB', (100, 100), 'olive')), 'image/png')},
        data={'operation_id': m.uid()})
    assert result.status_code == 200, result.text
    return result.json()['id']


def MockImages(monkeypatch, picture):
    requests = []
    clientClass = httpx.Client

    def Respond(request):
        requests.append(request)
        print('[开始] 抠图测试上游响应')
        if request.method == 'POST':
            print('[分支] 接受单次生图')
            response = httpx.Response(200, json={'task_id': 'cutout-test-job'})
        else:
            print('[分支] 返回测试图片')
            response = httpx.Response(200, json={'status': 'completed', 'data': [
                {'b64_json': base64.b64encode(storage.encode(picture)).decode('ascii')}]})
        print('[结束] 抠图测试上游响应')
        return response

    def CreateClient(**options):
        return clientClass(transport=httpx.MockTransport(Respond), **options)

    monkeypatch.setattr(settings(), 'image_cny_per_call', 0.06)
    monkeypatch.setattr(visual_ai, '_configuration', lambda kind, db, task: ('https://rightapi.ai', 'gpt-image-2.5', 'test-key'))
    monkeypatch.setattr(visual_ai.httpx, 'Client', CreateClient)
    return requests


def test_photo_generation_save_and_continued_edit_keep_cutout(client, monkeypatch):
    _, headers = NewUser(client)
    photoId = UploadPhoto(client, headers)
    requests = MockImages(monkeypatch, CutoutPicture())
    result = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation',
        'input': {'asset_id': photoId, 'prompt': '水彩鸟，添加森林背景', 'style_id': 'watercolor'}})
    assert result.status_code == 200, result.text
    taskId = result.json()['id']
    task = client.get('/api/v1/tasks/' + taskId, headers=headers).json()
    assert task['status'] == 'succeeded' and task['result']['species_cutout'] is True
    body = json.loads(requests[0].content)
    assert body['image'][0].startswith('data:image/jpeg;base64,')
    assert body['prompt'].endswith(visual_ai.speciesCutoutPrompt)
    saved = client.post('/api/v1/tasks/' + taskId + '/save', headers=headers)
    assert saved.status_code == 200, saved.text
    reference = client.post('/api/v1/tasks/' + taskId + '/reference', headers=headers)
    assert reference.status_code == 200, reference.text
    with SessionLocal() as db:
        asset = db.get(m.Asset, saved.json()['id'])
        assert asset.original_asset_id == photoId
        assert storage.image_bytes(storage.read(asset.key)).getchannel('A').getextrema() == (0, 255)
        assert storage.image_bytes(storage.read(asset.thumbnail_key)).getchannel('A').getextrema() == (0, 255)
        hidden = db.get(m.Asset, reference.json()['id'])
        assert hidden.original_asset_id == photoId
        hidden.original_asset_id = None
        # A soft-deleted original must not remove the descendant's constraint.
        db.get(m.Asset, photoId).deleted = True
        db.commit()
        assert visual_ai.RequiresSpeciesCutout(db, m.Task(kind='image_generation', input={'asset_id': asset.id}))
    # Reopening an older hidden reference restores its server-known provenance.
    reopened = client.post('/api/v1/tasks/' + taskId + '/reference', headers=headers)
    assert reopened.json()['id'] == reference.json()['id']
    continued = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation',
        'input': {'asset_id': reference.json()['id'], 'prompt': '改成素描'}})
    continuedTask = client.get('/api/v1/tasks/' + continued.json()['id'], headers=headers).json()
    assert continuedTask['status'] == 'succeeded'
    assert json.loads(requests[2].content)['prompt'].endswith(visual_ai.speciesCutoutPrompt)
    assert [request.method for request in requests] == ['POST', 'GET', 'POST', 'GET']


@pytest.mark.parametrize('background', ['white', '#cccccc'])
def test_opaque_photo_generation_saves_once_and_settles_actual_cost(client, monkeypatch, background):
    _, headers = NewUser(client)
    photoId = UploadPhoto(client, headers)
    requests = MockImages(monkeypatch, OpaquePicture(background))
    task = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation',
        'input': {'asset_id': photoId, 'species_cutout': False}}).json()
    task = client.get('/api/v1/tasks/' + task['id'], headers=headers).json()
    assert task['status'] == 'succeeded'
    assert client.post('/api/v1/tasks/' + task['id'] + '/save', headers=headers).status_code == 200
    assert client.post('/api/v1/tasks/' + task['id'] + '/reference', headers=headers).status_code == 200
    with SessionLocal() as db:
        charge = db.get(m.Charge, task['id'])
        assert charge.state == 'settled' and charge.actual_micros == 60000
        assert db.get(m.DailyBudget, charge.budget_id).held_micros == 0
        picture = storage.image_bytes(storage.read(db.get(m.Task, task['id']).result['image_key']))
        assert picture.getchannel('A').getextrema() == (0, 255)
        assert picture.getpixel((50, 50))[3] == 255
    assert jobs.run_task(task['id']) == 0
    assert [request.method for request in requests] == ['POST', 'GET']


def test_recovered_opaque_generation_saves_without_resubmission(client, monkeypatch):
    _, headers = NewUser(client)
    photoId = UploadPhoto(client, headers)
    monkeypatch.setattr(ai, 'dispatch', Mock())
    requests = MockImages(monkeypatch, OpaquePicture())
    task = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation',
        'input': {'asset_id': photoId}}).json()
    with SessionLocal() as db:
        saved = db.get(m.Task, task['id'])
        saved.status = 'running'
        saved.lease_owner = 'expired-worker'
        saved.lease_until = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        saved.result = {'_upstream_task_id': 'resume-cutout', '_submitted_at': time.time(), '_species_cutout': True}
        # Test the persisted contract even after its reference is no longer attached.
        saved.input = {}
        billing.MarkSubmitted(db, saved)
        billing.BeginCall(db, saved, 'image')
        db.commit()
    jobs.run_task(task['id'])
    with SessionLocal() as db:
        assert db.get(m.Task, task['id']).status == 'succeeded'
        assert db.get(m.Charge, task['id']).actual_micros == 60000
    assert [request.method for request in requests] == ['GET']


def test_text_material_is_cutout_and_polish_preserves_background(client, monkeypatch):
    _, headers = NewUser(client)
    requests = MockImages(monkeypatch, OpaquePicture())
    task = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation',
        'input': {'prompt': '一片银杏叶'}}).json()
    task = client.get('/api/v1/tasks/' + task['id'], headers=headers).json()
    assert task['status'] == 'succeeded' and task['result']['species_cutout'] is True
    assert visual_ai.speciesCutoutPrompt in json.loads(requests[0].content)['prompt']
    with SessionLocal() as db:
        picture = storage.image_bytes(storage.read(db.get(m.Task, task['id']).result['image_key']))
        assert picture.getchannel('A').getextrema() == (0, 255)
    project = client.post('/api/v1/projects', headers=headers, json={'title': '整页笔记'}).json()
    track = client.post('/api/v1/tracks', headers=headers, json={'project_id': project['id']}).json()
    client.post('/api/v1/tracks/' + track['id'] + '/nodes', headers=headers,
        json={'latitude': 31, 'longitude': 121, 'place_name': '草地', 'text': '树荫'})
    client.post('/api/v1/tracks/' + track['id'] + '/points', headers=headers, json={'points': [
        {'latitude': 31, 'longitude': 121, 'accuracy': 10, 'sequence': 0, 'segment': 0, 'timestamp': '2026-10-14T00:00:00+00:00'}]})
    client.patch('/api/v1/tracks/' + track['id'], headers=headers, json={'status': 'ended'})
    template = client.get('/api/v1/templates', headers=headers).json()['items'][0]
    draft = client.put('/api/v1/projects/' + project['id'] + '/route', headers=headers,
        json={'baseVersion': project['version'], 'trackId': track['id'], 'templateId': template['id'], 'description': '草地和树荫'})
    assert draft.status_code == 200, draft.text
    polished = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_polish', 'input': {
        'project_id': project['id'], 'draftVersion': draft.json()['draft']['version'], 'confirmed': True}}).json()
    polished = client.get('/api/v1/tasks/' + polished['id'], headers=headers).json()
    assert polished['status'] == 'succeeded' and polished['result']['species_cutout'] is False
    assert visual_ai.speciesCutoutPrompt not in json.loads(requests[2].content)['prompt']
