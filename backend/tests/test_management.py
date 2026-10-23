from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock
from sqlalchemy import select

from app import models as m, billing, chat, visual_ai
from app.db import SessionLocal
from app.admin_security import HashPassword


def NewUser(client):
    result = client.post('/api/v1/auth/dev', json={'device_id': m.uid()}).json()
    return result['user'], {'Authorization': 'Bearer ' + result['access_token']}


def AdminHeaders(client):
    with SessionLocal() as db:
        account = db.get(m.AdminAccount, 'owner')
        print('[开始] 测试管理账号准备')
        if account is None:
            print('[分支] 创建隔离测试管理员')
            db.add(m.AdminAccount(id='owner', username='tester', password_hash=HashPassword('testing-password-123'), must_change=False))
        else:
            print('[分支] 复用测试管理员')
        print('[结束] 测试管理账号准备')
        db.commit()
    response = client.post('/api/admin/login', json={'username': 'tester', 'password': 'testing-password-123'})
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie']
    return {'X-Admin-Action': 'nature-note'}


def test_quota_reservation_actual_settlement_idempotency_and_percent(client, monkeypatch):
    user, headers = NewUser(client)
    session = client.post('/api/v1/chats', headers=headers, json={}).json()
    execute = Mock(return_value={'is_mock': False, 'answer': '自然观察回答', '_actual_micros': 120000, 'usage': {'answer': {'prompt_tokens': 20}}, '_billing_evidence': '测试服务商账单'})
    monkeypatch.setattr(chat, 'Execute', execute)
    response = client.post('/api/v1/tasks', headers=headers, json={'kind':'rag','input':{'chat_session_id':session['id'],'question':'这是什么？'}, 'operation_id':'once'})
    assert response.status_code == 200, response.text
    taskId = response.json()['id']
    repeated = client.post('/api/v1/tasks', headers=headers, json={'kind':'rag','input':{'chat_session_id':session['id'],'question':'这是什么？'}, 'operation_id':'once'})
    assert repeated.json()['id'] == taskId
    assert execute.call_count == 1
    publicTask = client.get('/api/v1/tasks/'+taskId, headers=headers).json()
    assert publicTask['status'] == 'succeeded'
    assert '_actual_micros' not in publicTask['result']
    quota = client.get('/api/v1/me/quota', headers=headers).json()['items'][0]
    assert quota['remaining_percent'] == 97.6
    assert set(quota) == {'provider', 'remaining_percent', 'day', 'resets_at'}
    with SessionLocal() as db:
        charge = db.get(m.Charge, taskId)
        billing.Finalize(db, taskId, 120000)
        db.commit()
        budget = db.get(m.DailyBudget, charge.budget_id)
        assert budget.spent_micros == 120000 and budget.held_micros == 0


def test_pending_cost_no_fake_zero_and_admin_reconciliation(client, monkeypatch):
    user, headers = NewUser(client)
    session = client.post('/api/v1/chats', headers=headers, json={}).json()
    monkeypatch.setattr(chat, 'Execute', Mock(return_value={'is_mock':False,'answer':'回答','usage':{}}))
    response = client.post('/api/v1/tasks', headers=headers, json={'kind':'rag','input':{'chat_session_id':session['id'],'question':'观察'}})
    taskId = response.json()['id']
    with SessionLocal() as db:
        charge = db.get(m.Charge, taskId)
        assert charge.state == 'pending' and charge.actual_micros is None
    assert client.post('/api/admin/charges/'+taskId+'/settle', headers=headers, json={'amount':'0.1','evidence':'provider receipt 123'}).status_code == 401
    adminHeaders = AdminHeaders(client)
    assert client.post('/api/admin/charges/'+taskId+'/settle', json={'amount':'0.1','evidence':'provider receipt 123'}).status_code == 403
    settled = client.post('/api/admin/charges/'+taskId+'/settle', headers=adminHeaders, json={'amount':'0.1','evidence':'provider receipt 123'})
    assert settled.status_code == 200, settled.text
    assert client.get('/api/v1/me/quota', headers=headers).json()['items'][0]['remaining_percent'] == 98
    client.post('/api/admin/logout', headers=adminHeaders)


def test_separate_model_slot_and_release_before_dispatch(client, monkeypatch):
    from app.routers import ai
    monkeypatch.setattr(ai, 'dispatch', Mock())
    user, headers = NewUser(client)
    session = client.post('/api/v1/chats', headers=headers, json={}).json()
    payload = {'kind':'rag','input':{'chat_session_id':session['id'],'question':'观察'}}
    first = client.post('/api/v1/tasks', headers=headers, json=payload)
    assert first.status_code == 200
    assert client.post('/api/v1/tasks', headers=headers, json=payload).status_code == 409
    image = client.post('/api/v1/tasks', headers=headers, json={'kind':'image_generation','input':{'prompt':'森林'}})
    assert image.status_code == 200
    assert client.post('/api/v1/tasks/'+first.json()['id']+'/cancel', headers=headers).status_code == 200
    assert client.get('/api/v1/me/quota', headers=headers).json()['items'][0]['remaining_percent'] == 100
    assert client.post('/api/v1/tasks/'+image.json()['id']+'/cancel', headers=headers).status_code == 200


def test_chat_and_feedback_are_private(client):
    firstUser, firstHeaders = NewUser(client)
    secondUser, secondHeaders = NewUser(client)
    session = client.post('/api/v1/chats', headers=firstHeaders, json={'title':'私人对话'}).json()
    assert client.get('/api/v1/chats/'+session['id'], headers=secondHeaders).status_code == 404
    feedback = client.post('/api/v1/feedback', headers=firstHeaders, json={'category':'ai','text':'测试反馈'}).json()
    assert client.post('/api/v1/feedback/'+feedback['id']+'/reply', headers=secondHeaders, json={'text':'越权'}).status_code == 404
    assert client.get('/api/v1/feedback', headers=secondHeaders).json()['items'] == []
    assert client.delete('/api/v1/chats/'+session['id'], headers=firstHeaders).status_code == 200
    assert client.get('/api/v1/chats/'+session['id'], headers=firstHeaders).status_code == 404


def test_topup_and_default_changes_do_not_rewrite_today(client):
    adminHeaders = AdminHeaders(client)
    user, headers = NewUser(client)
    before = client.get('/api/v1/me/quota', headers=headers).json()
    response = client.post('/api/admin/quotas', headers=adminHeaders, json={'provider':'qwen','mode':'personal','amount':'2','user_id':user['id'],'note':'测试次日生效'})
    assert response.status_code == 200, response.text
    response = client.post('/api/admin/quotas', headers=adminHeaders, json={'provider':'qwen','mode':'topup','amount':'1','user_id':user['id'],'note':'测试当天追加'})
    assert response.status_code == 200
    with SessionLocal() as db:
        owner = db.get(m.User, user['id'])
        budget = billing.Budget(db, owner, 'qwen')
        assert budget.limit_micros == 6000000
        override = db.get(m.QuotaOverride, billing.Identity(owner)+':qwen')
        assert override.next_amount_micros == 2000000 and override.effective_day > billing.Day()
    client.post('/api/admin/logout', headers=adminHeaders)
