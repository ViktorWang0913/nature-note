import base64
import hashlib
import hmac
import json
import time
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)


def fail(status, code, message):
    raise HTTPException(status, {'code': code, 'message': message})


def sign(value: str):
    return hmac.new(settings().secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def token(user_id):
    payload = base64.urlsafe_b64encode(json.dumps({'sub': user_id, 'exp': int(time.time()) + 86400 * 7}, separators=(',', ':')).encode()).decode().rstrip('=')
    return payload + '.' + sign(payload)


def SessionUser(request: Request, auth: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    print('[开始] 身份验证方式')
    if request.cookies.get('nature_web') or not (settings().app_env == 'development' and settings().enable_dev_auth and auth):
        print('[分支] 网页会话；[结束] 身份验证方式')
        from .web_security import ReadSession
        return ReadSession(request, db)
    print('[分支] 隔离测试凭据；[结束] 身份验证方式')
    try:
        payload, signature = auth.credentials.split('.')
        if not hmac.compare_digest(signature, sign(payload)):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        if int(data['exp']) <= time.time():
            raise ValueError()
        user = db.get(User, data['sub'])
        if not user or user.deleted_at:
            raise ValueError()
        return user
    except (AttributeError, ValueError, KeyError, TypeError):
        fail(401, 'unauthorized', '请重新登录')


def owned(db, model, resource_id, user):
    obj = db.get(model, resource_id)
    if not obj or obj.user_id != user.id or getattr(obj, 'deleted', False):
        fail(404, 'not_found', '记录不存在或不可访问')
    return obj


def require_admin(user):
    if user.id not in settings().admin_user_ids.split(','):
        fail(403, 'forbidden', '没有管理权限')


def current_user(user=Depends(SessionUser)):
    print('[开始] 账号业务权限检查')
    if not user.active:
        print('[分支] 停用账号仅保留申诉入口')
        fail(403, 'account_disabled', '账号已停用，可通过意见反馈提交申诉')
    else:
        print('[分支] 账号业务可用')
    print('[结束] 账号业务权限检查')
    return user
