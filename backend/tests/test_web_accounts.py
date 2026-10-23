import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import SessionLocal
from app import models as m, billing, lifecycle
from app.admin_security import HashPassword

webHeaders = {'X-Nature-Action': 'web'}
adminHeaders = {'X-Admin-Action': 'nature-note'}
initialPassword = 'acceptance-initial-2026'
changedPassword = 'acceptance-changed-2026'


def PrepareAdmin():
    with SessionLocal() as db:
        record = db.get(m.AdminAccount, 'owner')
        print('[开始] 隔离管理员准备')
        if record is None:
            print('[分支] 创建管理员')
            record = m.AdminAccount(id='owner', username='tester', password_hash=HashPassword('testing-password-123'), must_change=False)
            db.add(record)
        else:
            print('[分支] 复用管理员')
        print('[结束] 隔离管理员准备')
        db.commit()


def NewAccount(adminClient):
    username = 'web-' + uuid.uuid4().hex[:12]
    response = adminClient.post('/api/admin/accounts', headers=adminHeaders, json={'username': username, 'password': initialPassword})
    assert response.status_code == 200, response.text
    return username, response.json()['id']


def Login(client, username, password=initialPassword):
    return client.post('/api/v1/auth/login', headers=webHeaders, json={'username': username, 'password': password})


def test_web_sessions_account_isolation_reset_disabled_and_logout(client):
    PrepareAdmin()
    with TestClient(app) as adminClient, TestClient(app) as firstClient, TestClient(app) as secondClient:
        assert adminClient.post('/api/admin/login', json={'username':'tester','password':'testing-password-123'}).status_code == 200
        firstName, firstId = NewAccount(adminClient)
        secondName, secondId = NewAccount(adminClient)
        response = Login(firstClient, firstName)
        assert response.status_code == 200 and response.json()['must_change']
        assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
        assert 'access_token' not in response.json()
        assert firstClient.get('/api/v1/projects').status_code == 403
        assert firstClient.post('/api/v1/auth/password', headers=webHeaders, json={'current_password':initialPassword,'new_password':changedPassword}).status_code == 200
        project = firstClient.post('/api/v1/projects', headers=webHeaders, json={'title':'网页隔离笔记'}).json()
        assert Login(secondClient,secondName).status_code == 200
        assert secondClient.post('/api/v1/auth/password', headers=webHeaders, json={'current_password':initialPassword,'new_password':changedPassword}).status_code == 200
        assert secondClient.get('/api/v1/projects/'+project['id']).status_code == 404
        assert secondClient.delete('/api/v1/projects/'+project['id'], headers=webHeaders).status_code == 404
        assert firstClient.post('/api/v1/projects', json={'title':'无来源请求'}).status_code == 403
        assert firstClient.post('/api/v1/projects', headers=webHeaders|{'Origin':'https://evil.example'}, json={'title':'跨站请求'}).status_code == 403
        assert adminClient.post('/api/admin/users/'+firstId+'/status', headers=adminHeaders, json={'active':False,'reason':'隔离验收'}).status_code == 200
        assert firstClient.get('/api/v1/projects').status_code == 403
        assert firstClient.post('/api/v1/feedback', headers=webHeaders, json={'category':'account','text':'申请恢复'}).status_code == 200
        assert adminClient.post('/api/admin/users/'+firstId+'/status', headers=adminHeaders, json={'active':True,'reason':'恢复验收'}).status_code == 200
        assert adminClient.post('/api/admin/accounts/'+firstId+'/password', headers=adminHeaders, json={'password':initialPassword}).status_code == 200
        assert firstClient.get('/api/v1/auth/session').status_code == 401
        assert Login(firstClient,firstName).json()['must_change']
        assert firstClient.post('/api/v1/auth/logout', headers=webHeaders, json={}).status_code == 200
        assert firstClient.get('/api/v1/auth/session').status_code == 401


def test_web_closure_reissue_preserves_budget_and_requires_cleanup(client):
    PrepareAdmin()
    with TestClient(app) as adminClient, TestClient(app) as userClient:
        adminClient.post('/api/admin/login', json={'username':'tester','password':'testing-password-123'})
        username, userId = NewAccount(adminClient)
        Login(userClient,username)
        userClient.post('/api/v1/auth/password', headers=webHeaders, json={'current_password':initialPassword,'new_password':changedPassword})
        with SessionLocal() as db:
            budget = billing.Budget(db,db.get(m.User,userId),'qwen')
            budget.spent_micros = 1000000
            db.commit()
        assert userClient.post('/api/v1/me/close', headers=webHeaders, json={'password':'wrong','confirmation':'注销账号'}).status_code == 403
        assert userClient.post('/api/v1/me/close', headers=webHeaders, json={'password':changedPassword,'confirmation':'注销账号'}).status_code == 200
        assert Login(userClient,username,changedPassword).status_code == 403
        assert adminClient.post('/api/admin/accounts/'+userId+'/reissue', headers=adminHeaders, json={'password':initialPassword}).status_code == 409
        with SessionLocal() as db:
            lifecycle.CleanupAccount(db,userId)
        response = adminClient.post('/api/admin/accounts/'+userId+'/reissue', headers=adminHeaders, json={'password':initialPassword})
        assert response.status_code == 200, response.text
        newId = response.json()['id']
        assert newId != userId
        with SessionLocal() as db:
            assert billing.Budget(db,db.get(m.User,newId),'qwen').spent_micros == 1000000


def test_web_login_lockout_and_no_public_registration(client):
    PrepareAdmin()
    with TestClient(app) as adminClient, TestClient(app) as userClient:
        adminClient.post('/api/admin/login', json={'username':'tester','password':'testing-password-123'})
        username, userId = NewAccount(adminClient)
        print('[开始] 错误密码限次验收，共5次')
        for attemptIndex in range(5):
            print(f'[开始] 错误密码 {attemptIndex+1}/5')
            assert Login(userClient,username,'wrong').status_code == 401
            print(f'[结束] 错误密码 {attemptIndex+1}/5')
        print('[结束] 错误密码限次验收')
        assert Login(userClient,username).status_code == 429
        assert userClient.post('/api/v1/auth/register',json={'username':'someone','password':initialPassword}).status_code == 404
