"""Diagnostic regression: a failed GET must not abandon an existing paid task."""
import base64
import io
from datetime import datetime, timedelta, timezone
import httpx
import pytest
from PIL import Image, ImageDraw
from app import jobs, models as m, visual_ai
from app.config import settings
from app.db import SessionLocal
from app.routers import ai
from test_management import NewUser


@pytest.mark.parametrize('failureKind', ['timeout', 'http503', 'cancelled'])
def test_query_timeout_keeps_original_image_task_recoverable(client, monkeypatch, failureKind):
    user, headers = NewUser(client)
    calls = []
    clientClass = httpx.Client
    imageBytes = io.BytesIO()
    image = Image.new('RGB', (128, 128), 'white')
    ImageDraw.Draw(image).ellipse((30, 20, 98, 108), fill='#345634')
    image.save(imageBytes, format='PNG')
    monkeypatch.setattr(settings(), 'image_cny_per_call', 0.06)

    def Respond(request):
        calls.append(request.method)
        print('[开始] 隔离上游状态模拟')
        if request.method == 'POST':
            print('[分支] 上游接受任务；任务仍在执行')
            print('[结束] 隔离上游状态模拟')
            return httpx.Response(200, json={'task_id': 'review-existing-image'})
        elif calls.count('GET') == 1:
            print('[分支] 仅状态查询网络超时，未收到任务失败结果')
            print('[开始] 读取故障类型')
            if failureKind == 'http503':
                print('[分支] 临时 HTTP 503；[结束] 读取故障类型')
                print('[结束] 隔离上游状态模拟')
                return httpx.Response(503)
            else:
                print('[分支] 读取超时；[结束] 读取故障类型')
            print('[结束] 隔离上游状态模拟；读取失败')
            raise httpx.ReadTimeout('simulated query timeout', request=request)
        else:
            print('[分支] 查询同一任务取得生成结果；[结束] 隔离上游状态模拟')
            return httpx.Response(200, json={'status': 'completed', 'data': [
                {'b64_json': base64.b64encode(imageBytes.getvalue()).decode()}], 'usage': {'images': 1}})

    def CreateClient(**options):
        return clientClass(transport=httpx.MockTransport(Respond), **options)

    monkeypatch.setattr(visual_ai, '_configuration', lambda kind, db, task: ('https://image.invalid', 'review-model', 'fake-key'))
    monkeypatch.setattr(visual_ai.httpx, 'Client', CreateClient)
    # 单步执行真实 worker，避免 TestClient 自动等待整个恢复调度循环。
    monkeypatch.setattr(ai, 'dispatch', lambda taskId, background: print('隔离测试：由测试逐次执行原任务 '+taskId))
    response = client.post('/api/v1/tasks', headers=headers,
                           json={'kind': 'image_generation', 'input': {'prompt': '隔离状态查询测试'}})
    assert response.status_code == 200, response.text
    taskId = response.json()['id']
    jobs.run_task(taskId)
    with SessionLocal() as db:
        task = db.get(m.Task, taskId)
        print('诊断任务状态：', task.status, '费用状态：', db.get(m.Charge, taskId).state)
        assert task.result['_upstream_task_id'] == 'review-existing-image'
        assert task.user_id == user['id']
        assert task.status == 'running'
        assert task.error['code'] == 'image_query_pending'
        assert db.get(m.UserTaskSlot, db.get(m.Charge, taskId).slot_id).task_id == taskId
    assert calls == ['POST', 'GET']
    print('[开始] 恢复前用户取消检查')
    if failureKind == 'cancelled':
        print('[分支] 用户停止等待，仍核对原任务')
        assert client.post('/api/v1/tasks/' + taskId + '/cancel', headers=headers).status_code == 200
    else:
        print('[分支] 用户继续等待')
    print('[结束] 恢复前用户取消检查')
    with SessionLocal() as db:
        task = db.get(m.Task, taskId)
        task.lease_until = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        task.result = dict(task.result, _submitted_at=1)
        db.commit()
    assert taskId in jobs.recoverable_task_ids()
    jobs.run_task(taskId)
    assert calls == ['POST', 'GET', 'GET']
    with SessionLocal() as db:
        task = db.get(m.Task, taskId)
        assert task.status == ('cancelled' if failureKind == 'cancelled' else 'succeeded')
        assert task.result['provider_task_id'] == 'review-existing-image'
        charge = db.get(m.Charge, taskId)
        assert charge.state == 'settled' and charge.actual_micros == 60000
        assert db.get(m.UserTaskSlot, charge.slot_id).task_id is None
    print('[开始] 恢复结果保存验证')
    if failureKind != 'cancelled':
        print('[分支] 用户保存已恢复的图片')
        saved = client.post('/api/v1/tasks/' + taskId + '/save', headers=headers)
        assert saved.status_code == 200, saved.text
        assert client.get('/api/v1/tasks/' + taskId, headers=headers).json()['saved_asset_id'] == saved.json()['id']
    else:
        print('[分支] 已取消任务仅结算，不恢复为成功')
    print('[结束] 恢复结果保存验证')


def test_explicit_upstream_failure_is_not_automatically_resubmitted(client, monkeypatch):
    user, headers = NewUser(client)
    calls = []
    clientClass = httpx.Client

    def Respond(request):
        calls.append(request.method)
        print('[开始] 明确失败模拟')
        if request.method == 'POST':
            print('[分支] 原任务提交；[结束] 明确失败模拟')
            return httpx.Response(200, json={'task_id': 'review-overloaded'})
        else:
            print('[分支] 上游明确失败；[结束] 明确失败模拟')
            return httpx.Response(200, json={'status': 'failed', 'error': 'excessive system load secret-input'})

    def CreateClient(**options):
        return clientClass(transport=httpx.MockTransport(Respond), **options)

    monkeypatch.setattr(visual_ai, '_configuration', lambda kind, db, task: ('https://image.invalid', 'review-model', 'fake-key'))
    monkeypatch.setattr(visual_ai.httpx, 'Client', CreateClient)
    response = client.post('/api/v1/tasks', headers=headers,
                           json={'kind': 'image_generation', 'input': {'prompt': '隔离明确失败测试'}})
    taskId = response.json()['id']
    result = client.get('/api/v1/tasks/' + taskId, headers=headers).json()
    assert result['status'] == 'failed'
    assert '负载过高' in result['error']['message']
    assert 'secret-input' not in str(result)
    assert taskId not in jobs.recoverable_task_ids()
    jobs.run_task(taskId)
    assert calls == ['POST', 'GET']
