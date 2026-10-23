import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select

from app import jobs, models as m, schemas as s, visual_ai, chat
from app.db import SessionLocal


# 路径
contractPath = Path(__file__).resolve().parents[2] / 'contracts' / 'openapi.json'

# 参数设置
removedKinds = ('layout', 'text', 'bird_audio')


# 主程序：验证移除入口、历史任务和保留功能；测试函数名遵循 pytest 发现约定。
@pytest.mark.parametrize('removedKind', removedKinds)
def test_removed_task_creation_is_rejected(client, users, removedKind):
    user, headers = users[0]
    with SessionLocal() as db:
        taskCount = db.scalar(select(func.count()).select_from(m.Task).where(m.Task.user_id == user['id']))
    response = client.post('/api/v1/tasks', headers=headers, json={'kind': removedKind, 'input': {}})
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'validation_error'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(m.Task).where(m.Task.user_id == user['id'])) == taskCount


@pytest.mark.parametrize('removedKind', removedKinds)
@pytest.mark.parametrize('taskStatus', ('queued', 'running', 'failed', 'succeeded', 'cancelled'))
def test_removed_task_retry_is_rejected_without_leaking_ownership(client, users, removedKind, taskStatus):
    user, headers = users[0]
    _, otherHeaders = users[1]
    with SessionLocal() as db:
        task = m.Task(user_id=user['id'], kind=removedKind, input={}, status=taskStatus)
        db.add(task)
        db.commit()
        taskId = task.id
        taskCount = db.scalar(select(func.count()).select_from(m.Task))
    endpoint = f'/api/v1/tasks/{taskId}/retry'
    assert client.post(endpoint, headers=otherHeaders).status_code == 404
    response = client.post(endpoint, headers=headers)
    assert response.status_code == 410
    assert response.json()['detail']['code'] == 'task_kind_removed'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(m.Task)) == taskCount
        assert db.get(m.Task, taskId).status == taskStatus


@pytest.mark.parametrize('removedKind', removedKinds)
@pytest.mark.parametrize('taskStatus', ('queued', 'running'))
def test_removed_queued_tasks_finish_without_invoking_models(client, users, monkeypatch, removedKind, taskStatus):
    user, _ = users[0]
    visualCall = Mock(side_effect=AssertionError('Removed tasks must not call visual models'))
    knowledgeCall = Mock(side_effect=AssertionError('Removed tasks must not become knowledge queries'))
    monkeypatch.setattr(visual_ai, 'execute', visualCall)
    monkeypatch.setattr(chat, 'Execute', knowledgeCall)
    with SessionLocal() as db:
        task = m.Task(user_id=user['id'], kind=removedKind, input={}, status=taskStatus,
                      lease_until=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
        db.add(task)
        db.commit()
        taskId = task.id
    assert jobs.run_task(taskId) == 0
    with SessionLocal() as db:
        completed = db.get(m.Task, taskId)
        assert completed.status == 'failed'
        assert completed.error['code'] == 'task_kind_removed'
        assert completed.result is None
        assert completed.lease_owner is None and completed.lease_until is None
        updatedAt = completed.updated_at
    assert jobs.run_task(taskId) == 0
    with SessionLocal() as db:
        assert db.get(m.Task, taskId).updated_at == updatedAt
    visualCall.assert_not_called()
    knowledgeCall.assert_not_called()


def test_knowledge_task_requires_private_chat_and_never_uses_mock_search(client, users):
    _, headers = users[0]
    response = client.post('/api/v1/tasks', headers=headers, json={
        'kind':'rag', 'input':{'question':'白头鹎'},
    })
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'missing_chat'


def test_published_task_contract_matches_supported_features(client):
    contract = json.loads(contractPath.read_text(encoding='utf-8-sig'))
    liveContract = client.get('/openapi.json').json()
    assert contract['components']['schemas']['TaskCreate']['properties']['kind']['enum'] == [
        'image_generation', 'image_recognition', 'image_polish', 'rag',
    ]
    assert liveContract['components']['schemas']['TaskCreate'] == contract['components']['schemas']['TaskCreate']
    assert s.taskKinds == visual_ai.KINDS | {'rag'}
