"""Billing regressions run against isolated SQLite and in-memory upstream responses."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import select, update

from app import billing, models as m, visual_ai
from app.config import settings
from app.db import SessionLocal
from app.routers import ai
from test_management import NewUser, AdminHeaders
from test_streaming_chat import MockProvider


@pytest.fixture(autouse=True)
def FinishTestTasks(client):
    with SessionLocal() as db:
        existingIds = list(db.scalars(select(m.Task.id)))
    yield
    # These ledger tests intentionally bypass the worker; do not leave its queue blocked.
    with SessionLocal() as db:
        db.execute(update(m.Task).where(m.Task.id.not_in(existingIds), m.Task.status.in_(['queued', 'running'])).values(
            status='cancelled', lease_owner=None, lease_until=None))
        db.commit()


def CreateQueued(client, headers, monkeypatch, kind='image_generation'):
    monkeypatch.setattr(ai, 'dispatch', Mock())
    result = client.post('/api/v1/tasks', headers=headers, json={'kind': kind, 'input': {'prompt': '自然插画'}})
    assert result.status_code == 200, result.text
    return result.json()['id']


def MockImages(monkeypatch, failStorage=False):
    requests = []
    clientClass = httpx.Client

    def Respond(request):
        requests.append(request)
        print('[开始] 生图计费模拟响应')
        if request.method == 'POST':
            print('[分支] 返回唯一异步任务编号')
            response = httpx.Response(200, json={'task_id': m.uid()})
        else:
            print('[分支] 返回已完成图片，不伪造用量字段')
            response = httpx.Response(200, json={'data': [{'url': 'https://cdn.invalid/result.png'}]})
        print('[结束] 生图计费模拟响应')
        return response

    def CreateClient(**options):
        return clientClass(transport=httpx.MockTransport(Respond), **options)

    monkeypatch.setattr(settings(), 'image_cny_per_call', 0.06)
    monkeypatch.setattr(visual_ai, '_configuration', lambda kind, db, task: ('https://rightapi.ai', 'gpt-image-2.5', 'fake-key'))
    monkeypatch.setattr(visual_ai.httpx, 'Client', CreateClient)
    print('[开始] 本地存储模拟选择')
    if failStorage:
        print('[分支] 模拟上游完成后的本地保存失败')
        monkeypatch.setattr(visual_ai, 'StoreImageResult', Mock(side_effect=RuntimeError('模拟保存失败')))
    else:
        print('[分支] 只返回本地占位路径，不发起图片下载')
        monkeypatch.setattr(visual_ai, 'StoreImageResult', Mock(return_value='test/image.png'))
    print('[结束] 本地存储模拟选择')
    return requests


def test_repeat_image_calls_settle_six_fen_and_other_user_untouched(client, monkeypatch):
    user, headers = NewUser(client)
    otherUser, otherHeaders = NewUser(client)
    requests = MockImages(monkeypatch)
    print('[开始] 连续生图验收，共 2 次')
    for taskIndex in range(2):
        print(f'[开始] 生图 {taskIndex + 1}/2')
        result = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation', 'input': {'prompt': '森林'}})
        assert result.status_code == 200
        with SessionLocal() as db:
            task = db.get(m.Task, result.json()['id'])
            charge = db.get(m.Charge, task.id)
            assert task.status == 'succeeded'
            assert charge.user_id == user['id']
            assert charge.actual_micros == charge.reserved_micros == 60000
            assert db.get(m.DailyBudget, charge.budget_id).held_micros == 0
        print(f'[结束] 生图 {taskIndex + 1}/2')
    print('[结束] 连续生图验收')
    assert client.get('/api/v1/me/quota', headers=headers).json()['items'][1]['remaining_percent'] == 97.6
    assert client.get('/api/v1/me/quota', headers=otherHeaders).json()['items'][1]['remaining_percent'] == 100
    assert requests[0].url.path == '/v1/images/generations'
    assert len(requests) == 4


def test_repeat_chat_requests_use_actual_usage_not_reservation(client, monkeypatch):
    user, headers = NewUser(client)
    session = client.post('/api/v1/chats', headers=headers, json={}).json()
    requests = MockProvider(monkeypatch)
    monkeypatch.setattr(settings(), 'qwen_input_cny_per_million', 0.6)
    monkeypatch.setattr(settings(), 'qwen_output_cny_per_million', 4.8)
    print('[开始] 连续问答验收，共 2 次')
    for taskIndex in range(2):
        print(f'[开始] 问答 {taskIndex + 1}/2')
        result = client.post('/api/v1/tasks', headers=headers, json={'kind': 'rag', 'input': {'chat_session_id': session['id'], 'question': '你好'}})
        assert result.status_code == 200
        with SessionLocal() as db:
            charge = db.get(m.Charge, result.json()['id'])
            assert charge.actual_micros == 264
            assert charge.state == 'settled'
            assert db.get(m.DailyBudget, charge.budget_id).held_micros == 0
        print(f'[结束] 问答 {taskIndex + 1}/2')
    print('[结束] 连续问答验收')
    assert len(requests) == 2


def test_completed_upstream_is_charged_when_local_storage_fails(client, monkeypatch):
    user, headers = NewUser(client)
    MockImages(monkeypatch, failStorage=True)
    result = client.post('/api/v1/tasks', headers=headers, json={'kind': 'image_generation', 'input': {'prompt': '森林'}})
    with SessionLocal() as db:
        task = db.get(m.Task, result.json()['id'])
        charge = db.get(m.Charge, task.id)
        assert task.status == 'failed'
        assert charge.state == 'settled' and charge.actual_micros == 60000
        assert db.get(m.DailyBudget, charge.budget_id).held_micros == 0


def test_token_tiers_invalid_usage_and_rounding():
    pricing = {'input_rate': '0.6', 'output_rate': '4.8', 'tier_threshold': 128000,
        'high_input_rate': '1.8', 'high_output_rate': '14.4'}
    assert billing.TokenCost({'prompt_tokens': 128000, 'completion_tokens': 10}, pricing) == 76848
    assert billing.TokenCost({'prompt_tokens': 128001, 'completion_tokens': 10}, pricing) == 230546
    assert billing.TokenCost({'prompt_tokens': 1, 'completion_tokens': 0}, pricing) == 1
    assert billing.TokenCost({'prompt_tokens': -1, 'completion_tokens': 0}, pricing) is None
    assert billing.TokenCost({'prompt_tokens': 10}, pricing) is None


def test_snapshot_and_original_day_survive_price_change_and_midnight(client, monkeypatch):
    user, headers = NewUser(client)
    monkeypatch.setattr(settings(), 'image_cny_per_call', 0.06)
    monkeypatch.setattr(billing, 'Day', lambda: '2026-10-14')
    taskId = CreateQueued(client, headers, monkeypatch)
    monkeypatch.setattr(settings(), 'image_cny_per_call', 1)
    monkeypatch.setattr(billing, 'Day', lambda: '2026-10-15')
    with SessionLocal() as db:
        task = db.get(m.Task, taskId)
        task.status = 'running'
        db.commit()
        billing.MarkSubmitted(db, task)
        billing.BeginCall(db, task, 'image')
        billing.RecordCall(db, task, 'image', {}, imageCompleted=True)
        billing.Finalize(db, taskId)
        billing.Finalize(db, taskId)
        db.commit()
        charge = db.get(m.Charge, taskId)
        assert charge.actual_micros == 60000
        assert db.get(m.DailyBudget, charge.budget_id).day == '2026-10-14'
        assert billing.Budget(db, db.get(m.User, user['id']), 'image').spent_micros == 0


def test_concurrent_settlement_and_late_pending_do_not_double_charge(client, monkeypatch):
    user, headers = NewUser(client)
    monkeypatch.setattr(settings(), 'image_cny_per_call', 0.06)
    taskId = CreateQueued(client, headers, monkeypatch)

    def Settle(amount):
        with SessionLocal() as db:
            billing.Finalize(db, taskId, amount)
            db.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(Settle, 60000)
        second = executor.submit(Settle, 60000)
        first.result()
        second.result()
    Settle(None)
    with SessionLocal() as db:
        charge = db.get(m.Charge, taskId)
        budget = db.get(m.DailyBudget, charge.budget_id)
        assert charge.state == 'settled'
        assert budget.spent_micros == 60000 and budget.held_micros == 0


def test_admin_prices_require_admin_and_do_not_reprice_existing_tasks(client, monkeypatch):
    user, headers = NewUser(client)
    monkeypatch.setattr(settings(), 'image_cny_per_call', 0.06)
    taskId = CreateQueued(client, headers, monkeypatch)
    price = {'per_call': '0.12', 'evidence': '本地测试确认的每次人民币合同价'}
    assert client.put('/api/admin/pricing/image', headers=headers, json=price).status_code == 401
    adminHeaders = AdminHeaders(client)
    assert client.put('/api/admin/pricing/image', headers=adminHeaders, json=price).status_code == 200
    with SessionLocal() as db:
        assert db.get(m.Charge, taskId).pricing['per_call'] == 0.06
        assert billing.Pricing(db, 'image')['per_call'] == '0.12'
        db.delete(db.get(m.PlatformControl, 'pricing:image'))
        db.commit()
    client.post('/api/admin/logout', headers=adminHeaders)


def test_next_compression_call_stops_at_budget_and_settles_completed_call(client, monkeypatch):
    user, headers = NewUser(client)
    monkeypatch.setattr(settings(), 'qwen_input_cny_per_million', 0.6)
    monkeypatch.setattr(settings(), 'qwen_output_cny_per_million', 4.8)
    with SessionLocal() as db:
        owner = db.get(m.User, user['id'])
        task = m.Task(user_id=owner.id, kind='rag', input={})
        db.add(task)
        db.flush()
        billing.Reserve(db, owner, task)
        charge = db.get(m.Charge, task.id)
        budget = db.get(m.DailyBudget, charge.budget_id)
        budget.limit_micros = charge.reserved_micros
        task.status = 'running'
        db.commit()
        billing.MarkSubmitted(db, task)
        billing.BeginCall(db, task, 'summary-1')
        billing.RecordCall(db, task, 'summary-1', {'prompt_tokens': 100, 'completion_tokens': 20})
        with pytest.raises(RuntimeError, match='剩余额度不足'):
            billing.BeginCall(db, task, 'answer')
        db.rollback()
        billing.Finalize(db, task.id)
        db.commit()
        assert db.get(m.Charge, task.id).actual_micros == 156
        assert db.get(m.DailyBudget, charge.budget_id).held_micros == 0


def test_missing_usage_remains_pending_and_never_becomes_free(client, monkeypatch):
    user, headers = NewUser(client)
    with SessionLocal() as db:
        owner = db.get(m.User, user['id'])
        task = m.Task(user_id=owner.id, kind='rag', input={})
        db.add(task)
        db.flush()
        billing.Reserve(db, owner, task)
        task.status = 'running'
        db.commit()
        billing.MarkSubmitted(db, task)
        billing.BeginCall(db, task, 'answer')
        billing.RecordCall(db, task, 'answer', {})
        billing.Finalize(db, task.id)
        db.commit()
        charge = db.get(m.Charge, task.id)
        assert charge.state == 'pending' and charge.actual_micros is None
        assert db.get(m.DailyBudget, charge.budget_id).held_micros == charge.reserved_micros


def test_concurrent_user_requests_only_reserve_once(client, monkeypatch):
    user, headers = NewUser(client)
    with SessionLocal() as db:
        firstTask = m.Task(user_id=user['id'], kind='image_generation', input={})
        secondTask = m.Task(user_id=user['id'], kind='image_generation', input={})
        db.add_all([firstTask, secondTask])
        db.commit()
        firstId, secondId = firstTask.id, secondTask.id

    def ReserveTask(taskId):
        with SessionLocal() as db:
            billing.Reserve(db, db.get(m.User, user['id']), db.get(m.Task, taskId))
            db.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(ReserveTask, firstId)
        second = executor.submit(ReserveTask, secondId)
        errors = [first.exception(), second.exception()]
    assert sum(error is None for error in errors) == 1
    assert next(error for error in errors if error is not None).status_code == 409
    with SessionLocal() as db:
        budget = billing.Budget(db, db.get(m.User, user['id']), 'image')
        charge = db.get(m.Charge, firstId) or db.get(m.Charge, secondId)
        assert budget.held_micros == charge.reserved_micros


def test_cancel_rechecks_submission_instead_of_refunding_stale_reservation(client, monkeypatch):
    user, headers = NewUser(client)
    taskId = CreateQueued(client, headers, monkeypatch)
    with SessionLocal() as staleDb:
        charge = staleDb.get(m.Charge, taskId)
        assert charge.state == 'reserved'
        with SessionLocal() as workerDb:
            workerDb.execute(update(m.Charge).where(m.Charge.task_id == taskId).values(state='submitted'))
            workerDb.commit()
        billing.Abort(staleDb, taskId)
        staleDb.commit()
        charge = staleDb.get(m.Charge, taskId)
        assert charge.state == 'pending' and charge.actual_micros is None
        assert staleDb.get(m.DailyBudget, charge.budget_id).held_micros == charge.reserved_micros
