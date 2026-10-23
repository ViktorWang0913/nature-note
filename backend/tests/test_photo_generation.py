"""Exercise real uploads, reference bytes and Python cutouts with a fake provider."""
import base64
import io
import json
import random
from unittest.mock import Mock

import httpx
import pytest
from PIL import Image, ImageDraw

from app import jobs, models as m, storage, visual_ai
from app.db import SessionLocal
from app.routers import ai
from test_management import NewUser


@pytest.mark.parametrize('imageFormat', ['JPEG', 'PNG', 'WEBP'])
def test_uploaded_photo_text_cutout_and_save(client, monkeypatch, imageFormat):
    _, headers = NewUser(client)
    photo = Image.new('RGB', (2400, 1800), '#7c9448')
    ImageDraw.Draw(photo).ellipse((500, 300, 1800, 1500), fill='#1e4829')
    sourceStream = io.BytesIO()
    photo.save(sourceStream, imageFormat)
    originalBytes = sourceStream.getvalue()
    upload = client.post('/api/v1/assets/upload', headers=headers,
        files={'file': ('leaf.' + imageFormat.lower(), originalBytes, 'image/' + imageFormat.lower())},
        data={'operation_id': m.uid()})
    assert upload.status_code == 200, upload.text
    assetId = upload.json()['id']
    outputPicture = Image.new('RGB', (128, 128), 'white')
    ImageDraw.Draw(outputPicture).ellipse((30, 20, 98, 108), fill='#1e4829')
    requests = []
    clientClass = httpx.Client

    def Respond(request):
        requests.append(request)
        print('[开始] 照片创作测试响应')
        if request.method == 'POST':
            print('[分支] 保存模拟任务编号')
            response = httpx.Response(200, json={'task_id': 'photo-test-' + imageFormat})
        else:
            print('[分支] 模拟上游返回普通白底图片')
            response = httpx.Response(200, json={'status': 'completed', 'data': [
                {'b64_json': base64.b64encode(storage.encode(outputPicture)).decode('ascii')}]})
        print('[结束] 照片创作测试响应')
        return response

    def CreateClient(**options):
        return clientClass(transport=httpx.MockTransport(Respond), **options)

    monkeypatch.setattr(ai, 'dispatch', Mock())
    monkeypatch.setattr(visual_ai.httpx, 'Client', CreateClient)
    monkeypatch.setattr(visual_ai, '_configuration', lambda kind, db, task:
        ('https://rightapi.ai', 'nano-banana-2-lite', 'test-photo-key'))
    created = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation',
        'input': {'asset_id': assetId, 'prompt': '保留叶片轮廓，改成水彩', 'style_id': 'watercolor'}})
    assert created.status_code == 200, created.text
    taskId = created.json()['id']
    jobs.run_task(taskId)
    result = client.get('/api/v1/tasks/' + taskId, headers=headers).json()
    assert result['status'] == 'succeeded', result
    assert [request.method for request in requests] == ['POST', 'GET']
    body = json.loads(requests[0].content)
    parts = body['contents'][0]['parts']
    assert len(parts) == 2 and body['async'] is True
    assert '保留叶片轮廓，改成水彩' in parts[0]['text']
    assert parts[0]['text'].startswith('保留参考照片中主体的物种特征与完整轮廓')
    assert '透明' not in parts[0]['text'] and 'transparent' not in parts[0]['text'].lower()
    assert parts[1]['inline_data']['mime_type'] == 'image/jpeg'
    referenceBytes = base64.b64decode(parts[1]['inline_data']['data'], validate=True)
    assert len(referenceBytes) <= visual_ai.referenceMaximumBytes
    with Image.open(io.BytesIO(referenceBytes)) as reference:
        assert reference.format == 'JPEG' and reference.mode == 'RGB'
        assert reference.size == (1600, 1200)
    saved = client.post('/api/v1/tasks/' + taskId + '/save', headers=headers)
    assert saved.status_code == 200, saved.text
    savedId = saved.json()['id']
    assert client.post('/api/v1/tasks/' + taskId + '/save', headers=headers).json()['id'] == savedId
    with SessionLocal() as db:
        original = db.get(m.Asset, assetId)
        assert storage.read(original.original_key) == originalBytes
        asset = db.get(m.Asset, savedId)
        assert asset.original_asset_id == assetId
        picture = storage.image_bytes(storage.read(asset.key))
        assert picture.getpixel((0, 0))[3] == 0
        assert picture.getpixel((64, 64))[3] == 255
        assert storage.image_bytes(storage.read(asset.thumbnail_key)).getchannel('A').getextrema() == (0, 255)
        assert db.get(m.Task, taskId).result['provider_task_id'] == 'photo-test-' + imageFormat
    jobs.run_task(taskId)
    assert len(requests) == 2


def test_reference_payload_bound_and_exif(monkeypatch):
    picture = Image.frombytes('RGB', (1800, 1600), random.Random(37).randbytes(1800 * 1600 * 3))
    exif = Image.Exif()
    exif[274] = 6
    stream = io.BytesIO()
    picture.save(stream, 'JPEG', quality=95, exif=exif)
    monkeypatch.setattr(storage, 'read', lambda key: stream.getvalue())
    monkeypatch.setattr(visual_ai, 'referenceMaximumBytes', 80 * 1024)
    dataUrl = visual_ai.ReadGenerationReference('test.jpg')
    raw = base64.b64decode(dataUrl.split(',', 1)[1], validate=True)
    assert len(raw) <= 80 * 1024
    with Image.open(io.BytesIO(raw)) as reference:
        assert reference.height > reference.width
        assert max(reference.size) <= 1600
        assert reference.getexif().get(274) is None


def test_transparent_reference_is_flattened_without_changing_original(monkeypatch):
    picture = Image.new('RGBA', (100, 100), (255, 0, 0, 0))
    ImageDraw.Draw(picture).rectangle((30, 30, 70, 70), fill=(0, 120, 0, 255))
    originalBytes = storage.encode(picture)
    monkeypatch.setattr(storage, 'read', lambda key: originalBytes)
    dataUrl = visual_ai.ReadGenerationReference('test.png')
    with Image.open(io.BytesIO(base64.b64decode(dataUrl.split(',', 1)[1]))) as reference:
        assert min(reference.getpixel((0, 0))) > 250
        assert reference.getpixel((50, 50))[1] > 110
    assert picture.getpixel((0, 0))[3] == 0
    assert storage.encode(picture) == originalBytes
