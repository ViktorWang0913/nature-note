"""Browser sessions: separate from the administrator and never stored in JavaScript."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from . import models as m
from .config import settings
from .security import fail

cookieName = 'nature_web'


def CheckOrigin(request):
    print('[开始] 网页写请求来源检查')
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        print('[分支] 校验同源及请求头')
        origin = request.headers.get('origin', '').rstrip('/')
        expectedOrigin = settings().public_base_url.rstrip('/')
        print('[开始] 网页来源匹配')
        if request.headers.get('x-nature-action') != 'web' or (origin and origin != expectedOrigin):
            print('[分支] 拒绝来源；[结束] 网页来源匹配；[结束] 网页写请求来源检查')
            fail(403, 'invalid_origin', '请求来源无效')
        print('[分支] 来源有效；[结束] 网页来源匹配')
    else:
        print('[分支] 只读请求')
    print('[结束] 网页写请求来源检查')


def ReadSession(request, db):
    CheckOrigin(request)
    cookie = request.cookies.get(cookieName, '')
    session = db.get(m.WebSession, hashlib.sha256(cookie.encode()).hexdigest())
    print('[开始] 网页登录状态检查')
    if not session or session.expires_at <= m.now():
        print('[分支] 会话过期；[结束] 网页登录状态检查')
        fail(401, 'unauthorized', '请登录账号')
    print('[分支] 会话有效；[结束] 网页登录状态检查')
    credential = db.get(m.WebCredential, session.credential_id)
    user = db.get(m.User, credential.user_id)
    print('[开始] 账号注销检查')
    if not user or user.deleted_at:
        print('[分支] 账号已注销；[结束] 账号注销检查')
        fail(401, 'account_deleted', '账号已注销，请联系管理员')
    print('[分支] 账号存在；[结束] 账号注销检查')
    print('[开始] 首次密码检查')
    if credential.must_change and request.url.path not in {'/api/v1/auth/session', '/api/v1/auth/password', '/api/v1/auth/logout'}:
        print('[分支] 需要修改密码；[结束] 首次密码检查')
        fail(403, 'change_password_required', '请先修改初始密码')
    print('[分支] 允许访问；[结束] 首次密码检查')
    return user


def IssueSession(db, credential, response):
    secret = secrets.token_urlsafe(48)
    db.add(m.WebSession(id=hashlib.sha256(secret.encode()).hexdigest(), credential_id=credential.id,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat()))
    response.set_cookie(cookieName, secret, max_age=604800, httponly=True,
        secure=settings().public_base_url.startswith('https://'), samesite='lax', path='/')


def RevokeSessions(db, credentialId):
    db.execute(delete(m.WebSession).where(m.WebSession.credential_id == credentialId))
