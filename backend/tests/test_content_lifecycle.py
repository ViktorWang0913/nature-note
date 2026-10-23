import io
from PIL import Image
from sqlalchemy import select
from app import models as m, lifecycle, billing
from app.db import SessionLocal
from app.admin_security import HashPassword
from test_management import NewUser, AdminHeaders
from app import retention, storage, services as svc


def Upload(client, headers, color):
    content = io.BytesIO()
    Image.new('RGB',(12,12),color).save(content,format='PNG')
    result = client.post('/api/v1/assets/upload',headers=headers,files={'file':('photo.png',content.getvalue(),'image/png')},data={'operation_id':m.uid()})
    assert result.status_code == 200
    return result.json()


def CreateHistoricalPost(userId, assetId, title):
    # 直接构造更新前的存量内容，不绕过线上接口锁定。
    from fastapi import BackgroundTasks
    from app import schemas
    from app.routers.community import create_post
    with SessionLocal() as database:
        return create_post(schemas.PostCreate(title=title, text='历史内容', asset_ids=[assetId],
            operation_id=m.uid()), BackgroundTasks(), user=database.get(m.User, userId), db=database)


def test_ModerationKeepsHistoricalContentPrivateDuringLock(client):
    user, headers = NewUser(client)
    asset = Upload(client, headers, '#998822')
    post = CreateHistoricalPost(user['id'], asset['id'], '历史观察')
    assert post['review_status'] == 'pending'
    adminHeaders = AdminHeaders(client)
    response = client.post('/api/admin/review/post/' + post['id'], headers=adminHeaders,
        json={'status': 'approved', 'reason': ''})
    assert response.status_code == 200, response.text
    assert client.get('/api/v1/posts/' + post['id'], headers=headers).status_code == 503
    assert client.get(post['images'][0]).status_code == 404
    assert client.delete('/api/v1/assets/' + asset['id'], headers=headers).status_code == 200
    assert client.get(asset['url']).status_code == 404
    with SessionLocal() as database:
        assert database.get(m.Post, post['id']).deleted is False
        assert database.get(m.Post, post['id']).review_status == 'approved'
    client.post('/api/admin/logout', headers=adminHeaders)


def test_account_closure_reauth_cleanup_and_same_identity_quota(client):
    deviceId = m.uid()
    login = client.post('/api/v1/auth/dev',json={'device_id':deviceId}).json()
    user = login['user']
    headers = {'Authorization':'Bearer '+login['access_token']}
    asset = Upload(client,headers,'#991199')
    client.post('/api/v1/observations',headers=headers,json={'asset_id':asset['id'],'species_name':'测试观察'})
    with SessionLocal() as db:
        owner = db.get(m.User,user['id'])
        db.add(m.WebCredential(username='closure-'+deviceId,user_id=user['id'],password_hash=HashPassword(deviceId),must_change=False))
        budget = billing.Budget(db,owner,'qwen')
        budget.spent_micros = 1000000
        db.commit()
    assert client.post('/api/v1/me/close',headers=headers,json={'password':'wrong','confirmation':'注销账号'}).status_code == 403
    closed = client.post('/api/v1/me/close',headers=headers,json={'password':deviceId,'confirmation':'注销账号'})
    assert closed.status_code == 200, closed.text
    assert client.get('/api/v1/me',headers=headers).status_code == 401
    assert client.get(asset['url']).status_code == 404
    with SessionLocal() as db:
        lifecycle.CleanupAccount(db,user['id'])
        assert db.get(m.PlatformControl,'deletion:'+user['id']).value['state'] == 'complete'
        assert db.get(m.Asset,asset['id']).key == ''
    assert client.post('/api/v1/auth/dev',json={'device_id':deviceId}).status_code == 409
    fresh = client.post('/api/v1/auth/dev',json={'device_id':deviceId,'create_new':True}).json()
    assert fresh['user']['id'] != user['id']
    freshHeaders = {'Authorization':'Bearer '+fresh['access_token']}
    assert client.get('/api/v1/atlas',headers=freshHeaders).json()['items'] == []
    assert client.get('/api/v1/me/quota',headers=freshHeaders).json()['items'][0]['remaining_percent'] == 80


def test_deleted_library_photo_remains_in_existing_note_only(client):
    user, headers = NewUser(client)
    asset = Upload(client, headers, '#aa1212')
    project = client.post('/api/v1/projects', headers=headers, json={'title':'保留图片笔记'}).json()
    layout = svc.empty_layout()
    layout['elements'] = [{'id':'photo-one','type':'image','asset_id':asset['id'],'x':0,'y':0,'width':300,'height':300}]
    saved = client.patch('/api/v1/projects/'+project['id'], headers=headers, json={'base_version':1,'asset_ids':[asset['id']],'cover_asset_id':asset['id']})
    assert saved.status_code == 200, saved.text
    assert client.delete('/api/v1/assets/'+asset['id'],headers=headers).status_code == 200
    kept = client.get('/api/v1/projects/'+project['id'],headers=headers).json()
    assert client.get(kept['cover_url']).status_code == 200
    assert asset['id'] in kept['asset_ids']
    assert client.patch('/api/v1/projects/'+project['id'],headers=headers,json={'base_version':kept['version'],'asset_ids':[asset['id']]}).status_code == 200
    fresh = client.post('/api/v1/projects',headers=headers,json={'title':'新的笔记'}).json()
    assert client.patch('/api/v1/projects/'+fresh['id'],headers=headers,json={'base_version':1,'asset_ids':[asset['id']]}).status_code == 404
    with SessionLocal() as db:
        archive = db.scalar(select(m.Archive).where(m.Archive.resource_id == asset['id']))
        archive.expires_at = '2000-01-01T00:00:00+00:00'
        db.commit()
        retention.ExpireArchives(db)
        assert db.get(m.Asset,asset['id']).key != ''
    assert client.get(kept['cover_url']).status_code == 200


def test_expired_unreferenced_archive_removes_private_file(client):
    user, headers = NewUser(client)
    asset = Upload(client,headers,'#552299')
    client.delete('/api/v1/assets/'+asset['id'],headers=headers)
    with SessionLocal() as db:
        key = db.get(m.Asset,asset['id']).key
        archive = db.scalar(select(m.Archive).where(m.Archive.resource_id == asset['id']))
        archive.expires_at = '2000-01-01T00:00:00+00:00'
        db.commit()
        retention.ExpireArchives(db)
        assert db.get(m.Asset,asset['id']).key == ''
        assert not storage.local_path(key).exists()
    assert retention.MediaKeys({'text':'private/not-owned.png'}) == set()
    assert retention.MediaKeys({'input': {'snapshot': {'image_key': 'private/server-snapshot.png'}}}) == {'private/server-snapshot.png'}


def test_suspension_keeps_text_appeal_but_blocks_business(client):
    user, headers = NewUser(client)
    with SessionLocal() as db:
        db.get(m.User,user['id']).active = False
        db.commit()
    assert client.get('/api/v1/atlas',headers=headers).status_code == 403
    assert client.post('/api/v1/feedback',headers=headers,json={'category':'account','text':'请核实账号状态'}).status_code == 200
    assert client.get('/api/v1/feedback',headers=headers).status_code == 200
    assert client.post('/api/v1/feedback',headers=headers,json={'category':'ai','text':'其他请求'}).status_code == 403


def test_LockedCommunityRejectsEditsWithoutChangingHistoricalPost(client):
    user, headers = NewUser(client)
    asset = Upload(client, headers, '#55aa22')
    post = CreateHistoricalPost(user['id'], asset['id'], '原版标题')
    adminHeaders = AdminHeaders(client)
    assert client.post('/api/admin/review/post/' + post['id'], headers=adminHeaders,
        json={'status': 'approved'}).status_code == 200
    assert client.patch('/api/v1/posts/' + post['id'], headers=headers,
        json={'title': '新版标题'}).status_code == 503
    assert client.delete('/api/v1/posts/' + post['id'], headers=headers).status_code == 503
    with SessionLocal() as database:
        original = database.get(m.Post, post['id'])
        assert original.title == '原版标题' and original.deleted is False
    client.post('/api/admin/logout', headers=adminHeaders)
