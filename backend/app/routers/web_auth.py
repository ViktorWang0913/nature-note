"""Administrator-issued accounts for the standalone web edition."""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from sqlalchemy import select, delete
from .. import models as m, services as svc, lifecycle
from ..schemas import Input
from ..db import get_db
from ..security import SessionUser, fail
from ..admin_security import Admin, HashPassword, CheckPassword, Audit
from ..web_security import CheckOrigin, IssueSession, RevokeSessions, cookieName

api = APIRouter(tags=['web-accounts'])
dummyHash = HashPassword('not-a-real-account-password')


class LoginInput(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class PasswordInput(Input):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class CreateInput(LoginInput):
    nickname: str = Field(default='自然观察者', min_length=1, max_length=80)


class ResetInput(Input):
    password: str = Field(min_length=12, max_length=200)


class CloseInput(Input):
    password: str = Field(min_length=1, max_length=200)
    confirmation: str


def PublicAccount(db, credential):
    user = db.get(m.User, credential.user_id)
    return {'id': user.id, 'username': credential.username, 'name': user.name, 'active': user.active,
        'deleted_at': user.deleted_at, 'must_change': credential.must_change, 'created_at': user.created_at}


@api.post('/api/v1/auth/login')
def Login(data: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    CheckOrigin(request)
    username = data.username.strip().lower()
    credential = db.scalar(select(m.WebCredential).where(m.WebCredential.username == username))
    # 对不存在账号也执行相同密码计算，并按来源限制尝试次数。
    sourceId = hashlib.sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()
    attempt = db.get(m.WebLoginAttempt, sourceId)
    print('[开始] 登录来源记录')
    if not attempt:
        print('[分支] 创建来源记录')
        attempt = m.WebLoginAttempt(id=sourceId)
        db.add(attempt)
        db.flush()
    else:
        print('[分支] 使用现有记录')
    print('[结束] 登录来源记录')
    print('[开始] 登录限次检查')
    if (attempt.locked_until and attempt.locked_until > m.now()) or (credential and credential.locked_until and credential.locked_until > m.now()):
        print('[分支] 暂时锁定；[结束] 登录限次检查')
        fail(429, 'login_locked', '尝试次数过多，请十五分钟后重试')
    print('[分支] 可以验证；[结束] 登录限次检查')
    valid = CheckPassword(data.password, credential.password_hash if credential else dummyHash)
    print('[开始] 登录密码验证')
    if not credential or not valid:
        print('[分支] 密码无效')
        attempt.failed_attempts += 1
        print('[开始] 来源锁定阈值')
        if attempt.failed_attempts >= 20:
            print('[分支] 锁定来源')
            attempt.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            attempt.failed_attempts = 0
        else:
            print('[分支] 累计来源失败')
        print('[结束] 来源锁定阈值')
        print('[开始] 账号失败记录')
        if credential:
            print('[分支] 记录账号失败')
            credential.failed_attempts += 1
            print('[开始] 账号锁定阈值')
            if credential.failed_attempts >= 5:
                print('[分支] 锁定账号')
                credential.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
                credential.failed_attempts = 0
            else:
                print('[分支] 累计失败')
            print('[结束] 账号锁定阈值')
        else:
            print('[分支] 不暴露账号是否存在')
        print('[结束] 账号失败记录')
        db.commit()
        print('[结束] 登录密码验证')
        fail(401, 'invalid_credentials', '账号或密码不正确')
    print('[分支] 密码正确；[结束] 登录密码验证')
    user = db.get(m.User, credential.user_id)
    print('[开始] 注销账号登录检查')
    if user.deleted_at:
        print('[分支] 禁止自行重注册；[结束] 注销账号登录检查')
        fail(403, 'account_deleted', '账号已注销，请联系管理员重新发放')
    print('[分支] 可登录；[结束] 注销账号登录检查')
    credential.failed_attempts = attempt.failed_attempts = 0
    credential.locked_until = attempt.locked_until = None
    user.last_seen_at = m.now()
    IssueSession(db, credential, response)
    db.commit()
    return {'user': svc.public_user(db, user, user) | {'restricted': not user.active}, 'must_change': credential.must_change}


@api.get('/api/v1/auth/session')
def Session(user=Depends(SessionUser), db=Depends(get_db)):
    credential = db.scalar(select(m.WebCredential).where(m.WebCredential.user_id == user.id))
    return {'user': svc.public_user(db, user, user) | {'restricted': not user.active}, 'must_change': bool(credential and credential.must_change)}


@api.post('/api/v1/auth/logout')
def Logout(request: Request, response: Response, db=Depends(get_db)):
    CheckOrigin(request)
    sessionId = hashlib.sha256(request.cookies.get(cookieName, '').encode()).hexdigest()
    db.execute(delete(m.WebSession).where(m.WebSession.id == sessionId))
    db.commit()
    response.delete_cookie(cookieName, path='/')
    return {'logged_out': True}


@api.post('/api/v1/auth/password')
def ChangePassword(data: PasswordInput, response: Response, user=Depends(SessionUser), db=Depends(get_db)):
    credential = db.scalar(select(m.WebCredential).where(m.WebCredential.user_id == user.id))
    print('[开始] 当前密码复核')
    if not credential or not CheckPassword(data.current_password, credential.password_hash) or data.new_password == data.current_password:
        print('[分支] 密码不匹配或未更改；[结束] 当前密码复核')
        fail(422, 'password_invalid', '当前密码不正确，或新密码与原密码相同')
    print('[分支] 更新密码；[结束] 当前密码复核')
    credential.password_hash = HashPassword(data.new_password)
    credential.must_change = False
    RevokeSessions(db, credential.id)
    IssueSession(db, credential, response)
    Audit(db, user.id, 'web_password_changed', user.id, {})
    db.commit()
    return {'changed': True}


@api.post('/api/v1/me/close')
def CloseAccount(data: CloseInput, response: Response, user=Depends(SessionUser), db=Depends(get_db)):
    credential = db.scalar(select(m.WebCredential).where(m.WebCredential.user_id == user.id))
    print('[开始] 注销密码复核')
    if data.confirmation != '注销账号' or not credential or not CheckPassword(data.password, credential.password_hash):
        print('[分支] 拒绝注销；[结束] 注销密码复核')
        fail(403, 'reauth_failed', '密码或注销确认不正确')
    print('[分支] 停用并清理；[结束] 注销密码复核')
    RevokeSessions(db, credential.id)
    lifecycle.CloseAccount(db, user)
    response.delete_cookie(cookieName, path='/')
    return {'closed': True, 'cleanup_status': 'queued'}


@api.get('/api/admin/accounts')
def Accounts(admin=Depends(Admin), db=Depends(get_db)):
    credentials = db.scalars(select(m.WebCredential).order_by(m.WebCredential.username)).all()
    return {'items': [PublicAccount(db, credential) for credential in credentials], 'next_cursor': None}


@api.post('/api/admin/accounts')
def CreateAccount(data: CreateInput, admin=Depends(Admin), db=Depends(get_db)):
    username = data.username.strip().lower()
    print('[开始] 新账号校验')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,79}', username) or len(data.password) < 12:
        print('[分支] 格式错误；[结束] 新账号校验')
        fail(422, 'account_invalid', '账号须为3至80位字母、数字或 ._-，密码至少12位')
    print('[分支] 格式正确；[结束] 新账号校验')
    user = m.User(identity='web:' + username, name=data.nickname)
    db.add(user)
    db.flush()
    credential = m.WebCredential(username=username, user_id=user.id, password_hash=HashPassword(data.password))
    db.add(credential)
    Audit(db, admin.id, 'web_account_created', user.id, {'username': username})
    db.commit()
    return PublicAccount(db, credential)


@api.post('/api/admin/accounts/{userId}/password')
def ResetPassword(userId: str, data: ResetInput, admin=Depends(Admin), db=Depends(get_db)):
    credential = db.scalar(select(m.WebCredential).where(m.WebCredential.user_id == userId))
    print('[开始] 重置目标检查')
    if not credential:
        print('[分支] 账号不存在；[结束] 重置目标检查')
        fail(404, 'not_found', '账号不存在')
    print('[分支] 重置密码并撤销会话；[结束] 重置目标检查')
    credential.password_hash = HashPassword(data.password)
    credential.must_change = True
    credential.failed_attempts = 0
    credential.locked_until = None
    RevokeSessions(db, credential.id)
    Audit(db, admin.id, 'web_password_reset', userId, {})
    db.commit()
    return {'reset': True}


@api.post('/api/admin/accounts/{userId}/reissue')
def ReissueAccount(userId: str, data: ResetInput, admin=Depends(Admin), db=Depends(get_db)):
    credential = db.scalar(select(m.WebCredential).where(m.WebCredential.user_id == userId))
    user = db.get(m.User, userId)
    cleanup = db.get(m.PlatformControl, 'deletion:' + userId)
    print('[开始] 重新发放条件检查')
    if not credential or not user or not user.deleted_at or not cleanup or cleanup.value.get('state') != 'complete':
        print('[分支] 必须等待原账号注销清理完成；[结束] 重新发放条件检查')
        fail(409, 'cleanup_pending', '仅可重新发放已完成注销清理的账号')
    print('[分支] 保持计费身份创建空白账号；[结束] 重新发放条件检查')
    identity = user.identity
    user.identity = 'deleted:' + user.id
    db.flush()
    nextUser = m.User(identity=identity, name=user.name)
    db.add(nextUser)
    db.flush()
    RevokeSessions(db, credential.id)
    credential.user_id = nextUser.id
    credential.password_hash = HashPassword(data.password)
    credential.must_change = True
    credential.failed_attempts = 0
    credential.locked_until = None
    Audit(db, admin.id, 'web_account_reissued', nextUser.id, {'previous_user_id': userId})
    db.commit()
    return PublicAccount(db, credential)
