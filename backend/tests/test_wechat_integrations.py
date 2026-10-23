import base64
import hashlib
import json
import time

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app import models as m, wechat_api
from app.config import settings
from app.db import SessionLocal
from app.security import token
from test_content_lifecycle import Upload, CreateHistoricalPost
from app import moderation
from test_management import NewUser, AdminHeaders


def WechatUser(client):
    user, headers = NewUser(client)
    with SessionLocal() as db:
        db.get(m.User,user['id']).identity = 'wx:' + user['id']
        db.commit()
    return user, headers


def EncryptedEvent(payload, appId, aesKey, callbackToken):
    key = base64.b64decode(aesKey+'=')
    content = json.dumps(payload).encode()
    plain = b'0123456789abcdef' + len(content).to_bytes(4,'big') + content + appId.encode()
    padder = padding.PKCS7(256).padder()
    padded = padder.update(plain)+padder.finalize()
    encryptor = Cipher(algorithms.AES(key),modes.CBC(key[:16])).encryptor()
    encrypted = base64.b64encode(encryptor.update(padded)+encryptor.finalize()).decode()
    timestamp, nonce = str(int(time.time())), 'test-nonce'
    signature = hashlib.sha1(''.join(sorted([callbackToken,timestamp,nonce,encrypted])).encode()).hexdigest()
    return {'Encrypt':encrypted}, {'timestamp':timestamp,'nonce':nonce,'msg_signature':signature}


def test_phone_binding_uses_current_openid_and_keeps_no_plain_phone(client,monkeypatch):
    user, headers = WechatUser(client)
    cfg = settings()
    monkeypatch.setattr(cfg,'wechat_app_id','wx-local-testing')
    monkeypatch.setattr(wechat_api,'AccessToken',lambda:'local-token')
    calls = []

    def ReadPhone(path,body,token):
        calls.append(body)
        return {'errcode':0,'phone_info':{'purePhoneNumber':'13812345678','countryCode':'86','watermark':{'appid':cfg.wechat_app_id}}}

    monkeypatch.setattr(wechat_api,'ReadResponse',ReadPhone)
    result = client.post('/api/v1/me/phone',headers=headers,json={'code':'single-use-code'})
    assert result.status_code == 200, result.text
    assert result.json()['masked_number'] == '138****5678'
    assert calls == [{'code':'single-use-code','openid':user['id']}]
    with SessionLocal() as db:
        record = db.get(m.UserPhone,user['id'])
        assert len(record.phone_hash) == 64
        assert '13812345678' not in str(record.__dict__)
    otherUser, otherHeaders = NewUser(client)
    assert client.get('/api/v1/me/phone',headers=otherHeaders).json()['bound'] is False
    assert client.post('/api/v1/me/phone',headers=otherHeaders,json={'code':'fake'}).status_code == 422


def test_automatic_text_and_encrypted_image_review_and_manual_override(client,monkeypatch):
    cfg = settings()
    appId, callbackToken = 'wx-test-moderation', 'test-callback-token'
    aesKey = base64.b64encode(b'12345678901234567890123456789012').decode().rstrip('=')
    monkeypatch.setattr(cfg,'wechat_moderation_enabled',True)
    monkeypatch.setattr(cfg,'wechat_app_id',appId)
    monkeypatch.setattr(cfg,'wechat_app_secret','local-fake-secret')
    monkeypatch.setattr(cfg,'wechat_callback_token',callbackToken)
    monkeypatch.setattr(cfg,'wechat_callback_aes_key',aesKey)
    monkeypatch.setattr(wechat_api,'AccessToken',lambda required=True:'local-token')
    traces = []

    def ReviewResponse(path,body,token,required=True):
        print('[开始] 本地微信审核模拟')
        if path.endswith('msg_sec_check'):
            print('[分支] 文字通过')
            result = {'errcode':0,'result':{'suggest':'pass'}}
        else:
            print('[分支] 图片等待可信回调')
            traceId = m.uid()
            traces.append(traceId)
            result = {'errcode':0,'trace_id':traceId}
        print('[结束] 本地微信审核模拟')
        return result

    monkeypatch.setattr(wechat_api,'ReadResponse',ReviewResponse)
    user, headers = WechatUser(client)
    otherUser, otherHeaders = NewUser(client)
    asset = Upload(client,headers,'#112233')
    post = CreateHistoricalPost(user['id'], asset['id'], '待自动审核')
    moderation.Run('review:post:' + post['id'])
    assert client.get('/api/v1/posts/'+post['id'],headers=otherHeaders).status_code == 503
    event, parameters = EncryptedEvent({'Event':'wxa_media_check','trace_id':traces[0],'errcode':0,'result':{'suggest':'pass'}},appId,aesKey,callbackToken)
    rejected = client.post('/api/wechat/callback',params={**parameters,'msg_signature':'invalid'},json=event)
    assert rejected.status_code == 403
    accepted = client.post('/api/wechat/callback',params=parameters,json=event)
    assert accepted.status_code == 200, accepted.text
    assert client.get('/api/v1/posts/'+post['id'],headers=otherHeaders).status_code == 503
    with SessionLocal() as database:
        assert database.get(m.Post, post['id']).review_status == 'approved'
    assert client.post('/api/wechat/callback',params=parameters,json=event).status_code == 200
    assert client.post('/api/v1/posts/' + post['id'] + '/comments', headers=headers,
        json={'text': '自然观察'}).status_code == 503
    postTwo = CreateHistoricalPost(user['id'], asset['id'], '人工优先')
    moderation.Run('review:post:' + postTwo['id'])
    adminHeaders = AdminHeaders(client)
    assert client.post('/api/admin/review/post/'+postTwo['id'],headers=adminHeaders,json={'status':'rejected','reason':'人工核实'}).status_code == 200
    eventTwo, parametersTwo = EncryptedEvent({'Event':'wxa_media_check','trace_id':traces[-1],'errcode':0,'result':{'suggest':'pass'}},appId,aesKey,callbackToken)
    assert client.post('/api/wechat/callback',params=parametersTwo,json=eventTwo).status_code == 200
    assert client.get('/api/v1/posts/'+postTwo['id'],headers=otherHeaders).status_code == 503
    with SessionLocal() as database:
        assert database.get(m.Post, postTwo['id']).review_status == 'rejected'
    client.post('/api/admin/logout',headers=adminHeaders)
