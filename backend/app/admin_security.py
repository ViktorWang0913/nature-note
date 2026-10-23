"""Single-owner admin sessions use HttpOnly cookies, separate from user tokens."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from sqlalchemy import select
from . import models as m
from .db import get_db
from .security import fail
from .config import settings


def HashPassword(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + digest


def CheckPassword(password, savedHash):
    return hmac.compare_digest(HashPassword(password, savedHash.split(':')[0]), savedHash)


def AdminSession(request: Request, db=Depends(get_db)):
    cookie = request.cookies.get('nature_admin', '')
    session = db.get(m.AdminSession, hashlib.sha256(cookie.encode()).hexdigest())
    print('[开始] 管理员会话检查')
    if not session or session.expires_at <= m.now():
        print('[分支] 会话失效')
        fail(401, 'admin_login_required', '请登录管理员后台')
    else:
        print('[分支] 有效独立管理会话')
    print('[结束] 管理员会话检查')
    print('[开始] 管理写操作来源检查')
    if request.method not in {'GET', 'HEAD'}:
        print('[分支] 验证写操作自定义请求头及同源限制')
        origin = request.headers.get('origin')
        print('[开始] 写操作请求标识验证')
        if request.headers.get('x-admin-action') != 'nature-note' or (origin and origin.rstrip('/') != settings().public_base_url.rstrip('/')):
            print('[分支] 拒绝跨站管理操作')
            fail(403, 'admin_origin', '管理操作来源无效')
        else:
            print('[分支] 来源有效')
        print('[结束] 写操作请求标识验证')
    else:
        print('[分支] 只读操作')
    print('[结束] 管理写操作来源检查')
    session.expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    db.commit()
    return session


def Admin(request: Request, session=Depends(AdminSession), db=Depends(get_db)):
    account = db.get(m.AdminAccount, session.admin_id)
    print('[开始] 首次密码更改检查')
    if account.must_change:
        print('[分支] 先修改初始密码')
        fail(403, 'change_password_required', '请先修改初始管理员密码')
    else:
        print('[分支] 管理账号已初始化')
    print('[结束] 首次密码更改检查')
    return account


def Audit(db, actorId, action, targetId, detail):
    db.add(m.Audit(actor_id=actorId, action=action, target_id=targetId, detail=detail))
