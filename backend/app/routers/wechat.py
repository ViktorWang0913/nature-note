import base64
import hashlib
import hmac
import json
import time

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from .. import moderation
from ..config import settings
from ..db import get_db
from ..security import fail

api = APIRouter(prefix='/api/wechat', tags=['wechat-callback'])


def Verify(signature, timestamp, nonce, encrypted=''):
    cfg = settings()
    print('[开始] 微信回调签名检查')
    if not cfg.wechat_callback_token or abs(int(time.time()) - timestamp) > 600:
        print('[分支] 未配置或回调时间无效')
        fail(403, 'invalid_callback', '回调未授权')
    else:
        print('[分支] 校验官方签名')
    print('[结束] 微信回调签名检查')
    parts = [cfg.wechat_callback_token, str(timestamp), nonce]
    print('[开始] 加密回调签名组成')
    if encrypted:
        print('[分支] 密文参与签名')
        parts.append(encrypted)
    else:
        print('[分支] 首次 URL 验证')
    print('[结束] 加密回调签名组成')
    expected = hashlib.sha1(''.join(sorted(parts)).encode()).hexdigest()
    print('[开始] 微信签名匹配')
    if not hmac.compare_digest(expected,signature):
        print('[分支] 签名不匹配')
        fail(403, 'invalid_callback', '回调未授权')
    else:
        print('[分支] 官方签名有效')
    print('[结束] 微信签名匹配')


@api.get('/callback',response_class=PlainTextResponse)
def VerifyUrl(signature: str, timestamp: int, nonce: str, echostr: str):
    Verify(signature,timestamp,nonce)
    return echostr


@api.post('/callback',response_class=PlainTextResponse)
async def Receive(request: Request, timestamp: int, nonce: str, msg_signature: str, db=Depends(get_db)):
    content = await request.body()
    print('[开始] 回调长度限制')
    if len(content) > 1024 * 1024 or len(settings().wechat_callback_aes_key) != 43:
        print('[分支] 内容过大或安全模式尚未配置')
        fail(422, 'invalid_callback', '回调格式无效')
    else:
        print('[分支] 读取 JSON 安全模式回调')
    print('[结束] 回调长度限制')
    envelope = json.loads(content)
    encrypted = envelope.get('Encrypt','')
    print('[开始] 安全模式密文检查')
    if not encrypted:
        print('[分支] 拒绝未加密的业务回调')
        fail(403,'encrypted_callback_required','请配置 JSON 安全模式消息推送')
    else:
        print('[分支] 验证密文签名')
    print('[结束] 安全模式密文检查')
    Verify(msg_signature,timestamp,nonce,encrypted)
    key = base64.b64decode(settings().wechat_callback_aes_key+'=')
    decryptor = Cipher(algorithms.AES(key),modes.CBC(key[:16])).decryptor()
    padded = decryptor.update(base64.b64decode(encrypted,validate=True))+decryptor.finalize()
    unpadder = padding.PKCS7(256).unpadder()
    plain = unpadder.update(padded)+unpadder.finalize()
    length = int.from_bytes(plain[16:20],'big')
    print('[开始] 解密小程序身份检查')
    if len(plain) < 20 or length > len(plain)-20 or plain[20+length:].decode() != settings().wechat_app_id:
        print('[分支] 解密内容不属于当前小程序')
        fail(403,'invalid_callback','回调未授权')
    else:
        print('[分支] 当前小程序审核消息')
    print('[结束] 解密小程序身份检查')
    payload = json.loads(plain[20:20+length])
    moderation.Callback(db,payload)
    return 'success'
