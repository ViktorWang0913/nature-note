"""Runtime configuration, secret protection, task snapshots and admin access."""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import delete, select
from app import models as m, runtime_config, visual_ai, billing
from app.db import SessionLocal
from app.config import settings
from app.routers import ai
from test_management import AdminHeaders, NewUser


@pytest.fixture
def runtimeAdmin(client, monkeypatch):
    headers = AdminHeaders(client)
    monkeypatch.setattr(settings(), 'image_api_base_url', 'https://image.invalid')
    monkeypatch.setattr(settings(), 'image_api_model', 'env-model')
    monkeypatch.setattr(settings(), 'image_api_key', 'env-test-key')
    recordIds = ['runtime:image', 'runtime:qwen', 'runtime:map', 'pricing:image', 'pricing:qwen']
    with SessionLocal() as db:
        prior = {record.id: record.value for record in db.scalars(select(m.PlatformControl).where(m.PlatformControl.id.in_(recordIds)))}
        db.execute(delete(m.PlatformControl).where(m.PlatformControl.id.in_(recordIds)))
        db.commit()
    yield headers
    client.cookies.clear()
    with SessionLocal() as db:
        db.execute(delete(m.PlatformControl).where(m.PlatformControl.id.in_(recordIds)))
        print('[开始] 还原测试配置')
        for recordIndex, (recordId, value) in enumerate(prior.items(), 1):
            print(f'[开始] 还原配置 {recordIndex}/{len(prior)}')
            db.add(m.PlatformControl(id=recordId, value=value))
            print(f'[结束] 还原配置 {recordIndex}/{len(prior)}')
        print('[结束] 还原测试配置')
        db.commit()


def ServiceData(revision=0, modelName='model-one', apiKey='test-secret-one'):
    return {'revision': revision, 'model': modelName, 'base_url': 'https://image.invalid', 'api_key': apiKey,
            'pricing': {'per_call': '0.06', 'evidence': '测试合同单价'}}


def test_runtime_secret_masking_authorization_and_cross_process_read(client, runtimeAdmin):
    response = client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=ServiceData())
    assert response.status_code == 200
    loaded = client.get('/api/admin/runtime/services/image', headers=runtimeAdmin)
    assert loaded.headers['cache-control'] == 'no-store'
    assert loaded.json()['model'] == 'model-one' and loaded.json()['key_configured']
    assert 'test-secret-one' not in loaded.text and 'api_key' not in loaded.json()
    with SessionLocal() as db:
        record = db.get(m.PlatformControl, 'runtime:image')
        assert 'test-secret-one' not in json.dumps(record.value)
        audits = list(db.scalars(select(m.Audit).where(m.Audit.action == 'runtime_service_changed')))
        assert 'test-secret-one' not in json.dumps([audit.detail for audit in audits])
    process = subprocess.run([sys.executable, '-c',
        "from app.db import SessionLocal; from app.runtime_config import ReadProvider; "
        "db=SessionLocal(); values=ReadProvider(db,'image'); "
        "assert values['model']=='model-one'; assert values['api_key']=='test-secret-one'; db.close()"],
        capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    client.cookies.clear()
    assert client.get('/api/admin/runtime/services/image').status_code == 401
    assert client.put('/api/admin/runtime/services/image', json=ServiceData()).status_code == 401
    _, userHeaders = NewUser(client)
    assert client.get('/api/admin/runtime/services/image', headers=userHeaders).status_code == 401


def test_runtime_validation_version_conflict_and_key_preservation(client, runtimeAdmin):
    assert client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=ServiceData()).status_code == 200
    changed = ServiceData(1, 'model-two', '')
    assert client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=changed).status_code == 200
    with SessionLocal() as db:
        assert runtime_config.ReadProvider(db, 'image')['api_key'] == 'test-secret-one'
        assert db.get(m.PlatformControl, 'pricing:image').value['model'] == 'model-two'
    assert client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=changed).status_code == 409
    changed.update(revision=2, base_url='https://different.invalid')
    assert client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=changed).json()['detail']['code'] == 'new_key_required'
    changed.update(api_key='other-key', base_url='http://unsafe.invalid')
    assert client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=changed).status_code == 422
    assert client.put('/api/admin/runtime/services/image', headers={**runtimeAdmin, 'Origin': 'https://evil.invalid'}, json=ServiceData(2)).status_code == 403


def test_new_tasks_use_new_config_existing_tasks_retain_original(client, runtimeAdmin, monkeypatch):
    monkeypatch.setattr(ai, 'dispatch', lambda taskId, background: print('隔离测试：仅排队，不调用模型'))
    assert client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=ServiceData()).status_code == 200
    _, userHeaders = NewUser(client)
    first = client.post('/api/v1/tasks', headers=userHeaders, json={'kind': 'image_generation', 'input': {'prompt': '隔离任务'}})
    assert first.status_code == 200, first.text
    assert client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=ServiceData(1, 'model-two', 'test-secret-two')).status_code == 200
    _, secondHeaders = NewUser(client)
    second = client.post('/api/v1/tasks', headers=secondHeaders, json={'kind': 'image_generation', 'input': {'prompt': '新配置任务'}})
    assert second.status_code == 200, second.text
    with SessionLocal() as db:
        oldTask = db.get(m.Task, first.json()['id'])
        newTask = db.get(m.Task, second.json()['id'])
        assert visual_ai._configuration('image', db, oldTask) == ('https://image.invalid', 'model-one', 'test-secret-one')
        assert visual_ai._configuration('image', db, newTask) == ('https://image.invalid', 'model-two', 'test-secret-two')
        assert db.get(m.Charge, oldTask.id).pricing['model'] == 'model-one'
        assert db.get(m.Charge, newTask.id).pricing['model'] == 'model-two'
        print('[开始] 执行原模型和新模型任务，共 2 项')
        for taskIndex, task in enumerate([oldTask, newTask], 1):
            print(f'[开始] 任务执行许可 {taskIndex}/2')
            task.status = 'running'
            task.lease_owner = 'runtime-regression'
            db.commit()
            billing.MarkSubmitted(db, task)
            billing.BeginCall(db, task, 'image')
            assert db.get(m.Charge, task.id).metering['inflight'] == 'image'
            task.status = 'cancelled'
            task.lease_owner = None
            task.lease_until = None
            db.commit()
            billing.Finalize(db, task.id, actualMicros=0, evidence='隔离测试未发送上游请求')
            print(f'[结束] 任务执行许可 {taskIndex}/2')
        print('[结束] 执行原模型和新模型任务')
    assert client.post('/api/v1/tasks/' + first.json()['id'] + '/cancel', headers=userHeaders).status_code == 200
    assert client.post('/api/v1/tasks/' + second.json()['id'] + '/cancel', headers=secondHeaders).status_code == 200


def test_map_config_updates_public_endpoint_without_restart(client, runtimeAdmin):
    assert client.put('/api/admin/runtime/map', headers=runtimeAdmin, json={'revision': 0, 'map_key': 'test-web-map'}).status_code == 200
    public = client.get('/api/v1/web-config')
    assert public.json() == {'map_key': 'test-web-map'}
    assert public.headers['cache-control'] == 'no-store'
    assert client.put('/api/admin/runtime/map', headers=runtimeAdmin, json={'revision': 1, 'map_key': ''}).status_code == 200
    assert client.get('/api/v1/web-config').json() == {'map_key': ''}


def test_admin_locked_message_and_expiry(client, runtimeAdmin):
    with SessionLocal() as db:
        account = db.get(m.AdminAccount, 'owner')
        account.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        db.commit()
    locked = client.post('/api/admin/login', json={'username': 'tester', 'password': 'testing-password-123'})
    assert locked.status_code == 429 and locked.json()['detail']['code'] == 'admin_locked'
    with SessionLocal() as db:
        db.get(m.AdminAccount, 'owner').locked_until = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.commit()
    login = client.post('/api/admin/login', json={'username': ' tester ', 'password': 'testing-password-123'})
    assert login.status_code == 200
    assert client.get('/api/admin/overview').status_code == 200
    assert client.get('/admin/').status_code == 200


def test_admin_server_unlock_keeps_password(client, runtimeAdmin):
    with SessionLocal() as db:
        account = db.get(m.AdminAccount, 'owner')
        originalHash = account.password_hash
        account.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        db.commit()
    scriptText = (Path(__file__).resolve().parents[2] / 'scripts/admin-access.py').read_text(encoding='utf-8')
    status = subprocess.run([sys.executable, '-'], input=scriptText, capture_output=True, text=True)
    assert status.returncode == 0 and '"locked_now": true' in status.stdout
    unlocked = subprocess.run([sys.executable, '-', '--unlock'], input=scriptText, capture_output=True, text=True)
    assert unlocked.returncode == 0, unlocked.stderr
    with SessionLocal() as db:
        account = db.get(m.AdminAccount, 'owner')
        assert account.password_hash == originalHash and account.locked_until is None
    assert client.post('/api/admin/login', json={'username': 'tester', 'password': 'testing-password-123'}).status_code == 200


def test_vision_settings_and_legacy_task_configuration(client, runtimeAdmin, monkeypatch):
    monkeypatch.setattr(ai, 'dispatch', lambda taskId, background: print('隔离测试：不执行任务'))
    visionData = {'revision': 0, 'base_url': 'https://vision.invalid/v1', 'model': 'new-vision', 'api_key': 'vision-test-key',
                  'pricing': {'input_rate': '0.6', 'output_rate': '4.8', 'evidence': '测试合同'}}
    assert client.put('/api/admin/runtime/services/qwen', headers=runtimeAdmin, json=visionData).status_code == 200
    with SessionLocal() as db:
        assert runtime_config.ReadProvider(db, 'qwen')['model'] == 'new-vision'
    _, userHeaders = NewUser(client)
    taskResponse = client.post('/api/v1/tasks', headers=userHeaders, json={'kind': 'image_generation', 'input': {'prompt': '历史任务'}})
    assert taskResponse.status_code == 200, taskResponse.text
    taskId = taskResponse.json()['id']
    with SessionLocal() as db:
        db.execute(delete(m.PlatformControl).where(m.PlatformControl.id == 'task-api:' + taskId))
        db.commit()
    assert client.put('/api/admin/runtime/services/image', headers=runtimeAdmin, json=ServiceData()).status_code == 200
    with SessionLocal() as db:
        assert visual_ai._configuration('image', db, db.get(m.Task, taskId)) == ('https://image.invalid', 'env-model', 'env-test-key')
    assert client.post('/api/v1/tasks/' + taskId + '/cancel', headers=userHeaders).status_code == 200
