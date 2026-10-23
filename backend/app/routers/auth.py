import httpx
from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from .. import models as m, schemas as s, services as svc, billing, lifecycle, wechat_api
from ..security import current_user, fail, sign
from .shared import login

api = APIRouter(prefix="/api/v1", tags=["auth"])

@api.post('/auth/dev')
def dev_login(data: s.DevLogin, db: Session = Depends(get_db)):
    if settings().app_env != 'development' or not settings().enable_dev_auth:
        fail(404, 'not_found', '接口不可用')
    return login(db, 'dev:' + data.device_id, data.create_new)


@api.post('/auth/wechat')
async def wechat_login(data: s.WechatLogin, db: Session = Depends(get_db)):
    cfg = settings()
    print('[开始] Web 版本微信登录范围')
    if cfg.app_env != 'development' or not cfg.enable_dev_auth:
        print('[分支] 网页仅允许指定账号登录；[结束] Web 版本微信登录范围')
        fail(404, 'not_found', '接口不可用')
    print('[分支] 仅隔离测试兼容；[结束] Web 版本微信登录范围')
    if not cfg.wechat_app_id or not cfg.wechat_app_secret:
        fail(503, 'wechat_unconfigured', '微信登录尚未配置')
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            result = (await client.get('https://api.weixin.qq.com/sns/jscode2session', params={'appid': cfg.wechat_app_id, 'secret': cfg.wechat_app_secret, 'js_code': data.code, 'grant_type': 'authorization_code'})).json()
    except (httpx.HTTPError, ValueError):
        fail(503, 'wechat_unavailable', '微信登录暂时不可用')
    if not result.get('openid'):
        fail(401, 'wechat_login_failed', '微信登录失败，请重试')
    return login(db, 'wx:' + result['openid'], data.create_new)


# Web edition uses password reauthentication in web_auth.
async def CloseAccount(data: s.CloseAccountInput, user=Depends(current_user), db: Session = Depends(get_db)):
    cfg = settings()
    print('[开始] 注销身份重新验证')
    if cfg.app_env == 'development' and cfg.enable_dev_auth and user.identity.startswith('dev:'):
        print('[分支] 开发账号校验本机身份')
        identity = 'dev:' + data.code
    else:
        print('[分支] 使用新微信登录 code 校验身份')
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get('https://api.weixin.qq.com/sns/jscode2session', params={
                'appid':cfg.wechat_app_id, 'secret':cfg.wechat_app_secret, 'js_code':data.code, 'grant_type':'authorization_code'})
            result = response.json()
        identity = 'wx:' + str(result.get('openid', ''))
    print('[结束] 注销身份重新验证')
    print('[开始] 注销身份一致检查')
    if identity != user.identity:
        print('[分支] 身份不匹配')
        fail(403, 'reauth_failed', '身份验证失败，请重新登录后注销')
    else:
        print('[分支] 停用并启动清理')
    print('[结束] 注销身份一致检查')
    lifecycle.CloseAccount(db, user)
    return {'closed':True, 'cleanup_status':'queued'}


@api.get('/me')
def me(user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.public_user(db, user, user)


@api.get('/me/quota')
def GetQuota(user=Depends(current_user), db: Session = Depends(get_db)):
    result = billing.UserQuota(db, user)
    db.commit()
    return result


@api.patch('/me')
def update_me(data: s.ProfilePatch, user=Depends(current_user), db: Session = Depends(get_db)):
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, 'name' if key == 'nickname' else key, value)
    db.commit()
    return svc.public_user(db, user, user)


@api.get('/me/achievements')
def achievements(user=Depends(current_user), db: Session = Depends(get_db)):
    count = db.scalar(select(func.count(func.distinct(m.Observation.species_id))).where(m.Observation.user_id == user.id, m.Observation.confirmation == 'confirmed', m.Observation.deleted == False))
    return {'items': [{'id': f'species-{threshold}', 'title': title, 'achieved': count >= threshold, 'progress': min(count, threshold), 'target': threshold} for threshold, title in [(1, '初次观察'), (5, '自然探索者'), (10, '观察达人')]], 'next_cursor': None}



class PhoneInput(s.Input):
    code: str = Field(min_length=1, max_length=512)


@api.get('/me/phone')
def PhoneStatus(user=Depends(current_user), db: Session = Depends(get_db)):
    record = db.get(m.UserPhone, user.id)
    return {'bound': bool(record), 'masked_number': record.masked_number if record else '',
        'available': bool(settings().wechat_app_id and settings().wechat_app_secret and user.identity.startswith('wx:'))}


@api.post('/me/phone')
def BindPhone(data: PhoneInput, user=Depends(current_user), db: Session = Depends(get_db)):
    print('[开始] 手机号授权身份检查')
    if not user.identity.startswith('wx:'):
        print('[分支] 开发账号不可假冒微信手机号验证')
        fail(422, 'wechat_required', '请使用微信账号在真机中授权手机号')
    else:
        print('[分支] 当前微信身份')
    print('[结束] 手机号授权身份检查')
    normalized, masked = wechat_api.Phone(data.code, user.identity[3:])
    record = db.get(m.UserPhone, user.id)
    print('[开始] 手机号绑定记录检查')
    if record is None:
        print('[分支] 创建绑定记录，仅保留摘要和掩码')
        record = m.UserPhone(user_id=user.id)
        db.add(record)
    else:
        print('[分支] 更新已验证绑定')
    print('[结束] 手机号绑定记录检查')
    record.phone_hash, record.masked_number, record.verified_at = sign('phone:' + normalized), masked, m.now()
    db.commit()
    return {'bound': True, 'masked_number': masked}
