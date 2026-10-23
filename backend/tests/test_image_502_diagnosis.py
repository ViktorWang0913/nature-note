"""Read-only diagnosis of HTTP 502 paths using an isolated DB and fake upstream."""
import httpx
import pytest
from unittest.mock import Mock
from app import models as m, visual_ai, jobs
from app.routers import ai
from app.db import SessionLocal
from test_management import NewUser
from test_species_cutout import UploadPhoto


@pytest.mark.parametrize('failurePhase', ['submit', 'query', 'timeout'])
@pytest.mark.parametrize('withPhoto', [False, True])
def test_image_502_preserves_submission_evidence(client, monkeypatch, failurePhase, withPhoto):
    _, headers = NewUser(client)
    requests = []
    clientClass = httpx.Client

    def Respond(request):
        requests.append(request.method)
        print('[开始] 隔离 HTTP 502 阶段模拟')
        if failurePhase == 'timeout':
            print('[分支] 模拟提交超时；[结束] 隔离 HTTP 502 阶段模拟，读取失败')
            raise httpx.ReadTimeout('test timeout', request=request)
        print('[分支] 返回 HTTP 响应')
        print('[结束] 隔离 HTTP 502 阶段模拟')
        print('[开始] 隔离 HTTP 响应选择')
        if failurePhase == 'submit' or request.method == 'GET':
            print('[分支] 返回网关错误；[结束] 隔离 HTTP 响应选择')
            return httpx.Response(502, text='Bad Gateway')
        print('[分支] 已接受任务；[结束] 隔离 HTTP 响应选择')
        return httpx.Response(200, json={'task_id': 'diagnosis-existing-502'})

    def CreateClient(**options):
        return clientClass(transport=httpx.MockTransport(Respond), **options)

    monkeypatch.setattr(visual_ai, '_configuration', lambda kind, db, task: ('https://image.invalid', 'nano-banana-2-lite', 'test-key'))
    monkeypatch.setattr(visual_ai.httpx, 'Client', CreateClient)
    monkeypatch.setattr(ai, 'dispatch', Mock())
    taskInput = {'prompt': 'HTTP 502 隔离诊断'}
    print('[开始] 诊断参考图选择')
    if withPhoto:
        print('[分支] 使用上传照片')
        taskInput['asset_id'] = UploadPhoto(client, headers)
    else:
        print('[分支] 纯文字')
    print('[结束] 诊断参考图选择')
    response = client.post('/api/v1/tasks', headers=headers, json={
        'kind': 'image_generation', 'input': taskInput})
    taskId = response.json()['id']
    jobs.run_task(taskId)
    with SessionLocal() as db:
        task = db.get(m.Task, taskId)
        charge = db.get(m.Charge, taskId)
        print('[开始] 请求阶段断言')
        if failurePhase in {'submit', 'timeout'}:
            print('[分支] 提交结果未知，禁止重发')
            assert requests == ['POST']
            assert task.status == 'failed'
            expectedMessages = {'submit': 'AI 服务暂时不可用（HTTP 502）', 'timeout': 'AI 服务请求超时，请稍后重试'}
            assert task.error['message'] == expectedMessages[failurePhase]
            assert task.result['_dispatch_started'] is True
            assert task.result['_image_request']['reference_count'] == int(withPhoto)
            assert task.result['_image_request']['body_bytes'] > 0
            assert not task.result.get('_upstream_task_id')
        else:
            print('[分支] 已有编号，仅继续查询')
            assert requests == ['POST', 'GET']
            assert task.status == 'running'
            assert task.error['code'] == 'image_query_pending'
            assert task.result['_upstream_task_id'] == 'diagnosis-existing-502'
        print('[结束] 请求阶段断言')
        assert charge.actual_micros is None
        assert charge.state in {'submitted', 'pending'}
        print({'phase': failurePhase, 'status': task.status, 'error': task.error,
               'upstreamTaskId': task.result.get('_upstream_task_id'), 'chargeState': charge.state})
        print('[开始] 隔离测试队列释放')
        if failurePhase == 'query':
            print('[分支] 结束已验证的模拟运行任务')
            task.status = 'cancelled'
            task.lease_owner = None
            task.lease_until = None
            db.commit()
        else:
            print('[分支] 模拟任务已失败')
        print('[结束] 隔离测试队列释放')
