"""Gemini wire contract, persistence, failure evidence and manual editing."""
import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import httpx
import pytest
from PIL import Image, ImageDraw

from app import jobs, models as m, storage, visual_ai
from app.config import settings
from app.db import SessionLocal
from app.routers import ai
from test_management import NewUser


@pytest.mark.parametrize('base', ['https://www.rightapi.ai', 'https://rightapi.ai/v1', 'https://rightapi.ai/draw/v1'])
def test_gemini_reference_order_and_portrait(base):
    references = ['data:image/png;base64,Zmlyc3Q=', 'data:image/jpeg;base64,c2Vjb25k']
    endpoint, body = visual_ai.BuildImageRequest(base, 'nano-banana-2-lite', '路线与模板', references, '1024x1536')
    assert endpoint.endswith('/v1beta/models/nano-banana-2-lite:generateContent')
    assert '/draw/' not in endpoint
    assert body['async'] is True
    assert body['generationConfig']['imageConfig'] == {'aspectRatio': '2:3', 'imageSize': '1K'}
    assert body['contents'][0]['parts'] == [{'text': '路线与模板'},
        {'inline_data': {'mime_type': 'image/png', 'data': 'Zmlyc3Q='}},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': 'c2Vjb25k'}}]


@pytest.mark.parametrize('references,operation', [([], 'generations'), (['data:image/png;base64,Zm9v'], 'edits')])
def test_gpt_interface_compatibility(references, operation):
    endpoint, body = visual_ai.BuildImageRequest('https://rightapi.ai', 'gpt-image-2', '叶片', references, '1024x1024')
    assert endpoint == 'https://rightapi.ai/v1/images/' + operation
    assert body.get('image', []) == references


@pytest.mark.parametrize('scenario', ['text', 'reference', 'resume', 'failed', 'expired', 'canceled', 'cancelled', 'empty'])
def test_nano_task_flow(client, monkeypatch, scenario):
    user, headers = NewUser(client)
    calls = []
    clientClass = httpx.Client
    picture = Image.new('RGB', (32, 24), 'white')
    ImageDraw.Draw(picture).ellipse((8, 6, 24, 18), fill='gold')
    pictureBytes = storage.encode(picture)
    monkeypatch.setattr(ai, 'dispatch', Mock())
    monkeypatch.setattr(settings(), 'image_cny_per_call', 0.05)
    monkeypatch.setattr(visual_ai, '_configuration', lambda kind, db, task: ('https://www.rightapi.ai', 'nano-banana-2-lite', 'sk-test-secret'))
    failureStates = {'failed', 'expired', 'canceled', 'cancelled'}

    def Respond(request):
        calls.append(request)
        print('[开始] 模拟上游请求分派')
        if request.method == 'POST':
            print('[分支] 提交响应')
            print('[开始] 提交失败场景')
            if scenario in failureStates:
                print('[分支] HTTP 200 内明确失败')
                response = httpx.Response(200, json={'task_id': 'nano-test', 'status': scenario,
                    'error': {'message': 'provider sk-test-secret https://private.invalid/image', 'code': 'upstream_failed'}})
            else:
                print('[分支] 异步受理')
                response = httpx.Response(200, json={'task_id': 'nano-test', 'status': 'processing'})
            print('[结束] 提交失败场景')
        elif request.url.host == 'cdn.invalid':
            print('[分支] 下载真实格式图片字节')
            response = httpx.Response(200, content=pictureBytes, headers={'Content-Type': 'image/png'})
        else:
            print('[分支] 查询原任务')
            print('[开始] 查询中断场景')
            if scenario == 'resume' and len(calls) == 2:
                print('[分支] 一次查询超时；[结束] 查询中断场景；[结束] 模拟上游请求分派，读取失败')
                raise httpx.ReadTimeout('test timeout', request=request)
            else:
                print('[分支] 返回完成结果')
            print('[结束] 查询中断场景')
            print('[开始] 图片内容场景')
            if scenario == 'empty':
                print('[分支] 无图片候选')
                response = httpx.Response(200, json={'candidates': []})
            else:
                print('[分支] 无 status 的 Gemini URL 响应')
                response = httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': 'https://cdn.invalid/leaf.png'}]}}]})
            print('[结束] 图片内容场景')
        print('[结束] 模拟上游请求分派')
        return response

    transport = httpx.MockTransport(Respond)

    def CreateClient(**options):
        return clientClass(transport=transport, **options)

    taskInput = {'prompt': '叶片'}
    print('[开始] 参考素材准备')
    if scenario == 'reference':
        print('[分支] 已生成素材作为参考')
        with SessionLocal() as db:
            asset = m.Asset(user_id=user['id'], title='叶片', source='generated', category='environment',
                **storage.store_image(pictureBytes))
            db.add(asset)
            db.commit()
            taskInput['asset_id'] = asset.id
    else:
        print('[分支] 纯文字任务')
    print('[结束] 参考素材准备')
    with clientClass(transport=transport) as downloadClient:
        monkeypatch.setattr(visual_ai.httpx, 'Client', CreateClient)
        monkeypatch.setattr(visual_ai.httpx, 'stream', downloadClient.stream)
        created = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation', 'input': taskInput})
        assert created.status_code == 200, created.text
        taskId = created.json()['id']
        jobs.run_task(taskId)
        print('[开始] 原任务恢复场景')
        if scenario == 'resume':
            print('[分支] 过期租约后只读恢复')
            with SessionLocal() as db:
                task = db.get(m.Task, taskId)
                assert task.status == 'running'
                task.lease_until = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
                db.commit()
            jobs.run_task(taskId)
        else:
            print('[分支] 无需恢复')
        print('[结束] 原任务恢复场景')
    result = client.get('/api/v1/tasks/' + taskId, headers=headers).json()
    assert sum(request.method == 'POST' for request in calls) == 1
    requestBody = json.loads(calls[0].content)
    assert calls[0].url.path == '/v1beta/models/nano-banana-2-lite:generateContent'
    print('[开始] 结果验收')
    if scenario in failureStates or scenario == 'empty':
        print('[分支] 失败不保存或伪造费用')
        assert result['status'] == 'failed'
        assert len(calls) <= 2
        with SessionLocal() as db:
            task = db.get(m.Task, taskId)
            assert db.get(m.Charge, taskId).state == 'pending'
            print('[开始] 失败诊断保留检查')
            if scenario in failureStates:
                print('[分支] 管理员诊断保留且脱敏')
                assert task.result['_upstream_task_id'] == 'nano-test'
                assert task.result['_provider_error']['status'] == scenario
                assert 'sk-test-secret' not in json.dumps(task.result)
                assert '_provider_error' not in (result['result'] or {})
            else:
                print('[分支] 空图片结果')
            print('[结束] 失败诊断保留检查')
    else:
        print('[分支] 保存、读取和手动编辑')
        assert result['status'] == 'succeeded'
        saved = client.post('/api/v1/tasks/' + taskId + '/save', headers=headers).json()
        assert client.post('/api/v1/tasks/' + taskId + '/save', headers=headers).json()['id'] == saved['id']
        edited = client.post('/api/v1/assets/' + saved['id'] + '/edit', headers=headers,
            json={'rotation': 90})
        assert edited.status_code == 200, edited.text
        assert (edited.json()['width'], edited.json()['height']) == (24, 32)
        with SessionLocal() as db:
            assert db.get(m.Charge, taskId).actual_micros == 50000
        print('[开始] 参考图编码验收')
        if scenario == 'reference':
            print('[分支] 验证实际图片编码进入请求')
            inlineData = requestBody['contents'][0]['parts'][1]['inline_data']
            assert inlineData['mime_type'] == 'image/jpeg'
            assert storage.image_bytes(base64.b64decode(inlineData['data'])).size == (32, 24)
        else:
            print('[分支] 纯文字只有一个 part')
            assert len(requestBody['contents'][0]['parts']) == 1
        print('[结束] 参考图编码验收')
    print('[结束] 结果验收')
