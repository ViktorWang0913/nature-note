from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from pydantic import Field, model_validator
from sqlalchemy import select, update, func, inspect

from .. import models as m, billing, services as svc, storage, atlas, retention, runtime_config
from ..db import get_db
from ..config import settings
from ..security import fail
from ..schemas import Input
from ..admin_security import Admin, AdminSession, HashPassword, CheckPassword, Audit

adminPath = Path(__file__).resolve().parents[1] / 'static' / 'admin.html'
api = APIRouter(tags=['administration'])


class LoginInput(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class PasswordInput(Input):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class ProviderInput(Input):
    enabled: bool
    message: str = Field(min_length=1, max_length=200)
    concurrency: int = Field(ge=1, le=100)
    reserve_micros: int = Field(ge=1, le=1000000000)
    context_limit: int = Field(ge=2048, le=2000000)
    output_limit: int = Field(ge=128, le=32000)


class PricingInput(Input):
    input_rate: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=6)
    output_rate: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=6)
    tier_threshold: int = Field(default=128000, ge=1, le=2000000)
    high_input_rate: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=6)
    high_output_rate: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=6)
    per_call: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=6)
    evidence: str = Field(min_length=3, max_length=1000)


class QuotaInput(Input):
    provider: str = Field(pattern='^(qwen|image)$')
    mode: str = Field(pattern='^(default|personal|topup|reset)$')
    amount: Decimal = Field(ge=0, le=1000000, decimal_places=6)
    user_id: str | None = None
    note: str = Field(min_length=1, max_length=300)


class SettlementInput(Input):
    amount: Decimal = Field(ge=0, le=1000000, decimal_places=6)
    evidence: str = Field(min_length=5, max_length=2000)


class StatusInput(Input):
    active: bool
    reason: str = Field(min_length=1, max_length=300)


class ReviewInput(Input):
    status: str = Field(pattern='^(approved|rejected)$')
    reason: str = Field(default='', max_length=300)


class ReplyInput(Input):
    text: str = Field(min_length=1, max_length=5000)
    status: str = Field(pattern='^(open|processing|resolved)$')


class AnnouncementInput(Input):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=10000)
    user_ids: list[str] = Field(default_factory=list, max_length=1000)
    starts_at: datetime
    ends_at: datetime
    status: str = Field(pattern='^(draft|published|withdrawn)$')


class GroupInput(Input):
    species_ids: list[str] = Field(min_length=1, max_length=100)
    group_key: str = Field(min_length=1, max_length=64)


class CorrectionInput(Input):
    name: str = Field(min_length=1, max_length=100)
    scientific_name: str = Field(default='', max_length=150)
    reason: str = Field(min_length=1, max_length=1000)


def Serialize(record):
    return {column.key: getattr(record, column.key) for column in inspect(type(record)).columns}


@api.get('/admin', include_in_schema=False)
@api.get('/admin/', include_in_schema=False)
def AdminPage():
    return FileResponse(adminPath, headers={'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; frame-ancestors 'none'"})


@api.get('/admin.js', include_in_schema=False)
def AdminScript():
    return FileResponse(adminPath.with_suffix('.js'), media_type='text/javascript', headers={'Cache-Control': 'no-store'})


@api.get('/admin.css', include_in_schema=False)
def AdminStyle():
    return FileResponse(adminPath.with_suffix('.css'), media_type='text/css', headers={'Cache-Control': 'no-store'})


@api.get('/admin/workspace.js', include_in_schema=False)
def AdminWorkspace():
    return FileResponse(adminPath.with_name('admin-workspace.js'), media_type='text/javascript', headers={'Cache-Control': 'no-store'})


@api.get('/admin/preview.js', include_in_schema=False)
def AdminPreview():
    return FileResponse(adminPath.with_name('admin-preview.js'), media_type='text/javascript', headers={'Cache-Control': 'no-store'})


@api.post('/api/admin/login')
def Login(data: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    account = db.get(m.AdminAccount, 'owner')
    print('[开始] 管理员登录可用检查')
    if account is None:
        print('[分支] 管理员尚未初始化；[结束] 管理员登录可用检查；提前结束')
        fail(503, 'admin_not_initialized', '管理员尚未初始化，请通过服务器管理命令检查')
    elif account.locked_until and account.locked_until > m.now():
        print('[分支] 登录暂时锁定；[结束] 管理员登录可用检查；提前结束')
        fail(429, 'admin_locked', '管理员登录因多次验证失败已锁定，请在最后一次失败后十五分钟再试，或通过服务器管理命令解锁')
    else:
        print('[分支] 校验凭据')
    print('[结束] 管理员登录可用检查')
    validPassword = CheckPassword(data.password, account.password_hash)
    print('[开始] 管理员凭据验证')
    if not validPassword or data.username.strip() != account.username:
        print('[分支] 凭据无效，记录尝试')
        account.failed_attempts += 1
        print('[开始] 登录锁定阈值检查')
        if account.failed_attempts >= 5:
            print('[分支] 暂停登录十五分钟')
            account.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            account.failed_attempts = 0
        else:
            print('[分支] 未达到锁定阈值')
        print('[结束] 登录锁定阈值检查')
        db.commit()
        fail(401, 'invalid_credentials', '账号或密码错误')
    else:
        print('[分支] 登录成功')
    print('[结束] 管理员凭据验证')
    account.failed_attempts, account.locked_until = 0, None
    rawToken = secrets.token_urlsafe(32)
    session = m.AdminSession(id=hashlib.sha256(rawToken.encode()).hexdigest(), admin_id=account.id,
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(), verified_at=m.now())
    db.add(session)
    Audit(db, account.id, 'admin_login', account.id, {})
    db.commit()
    response.set_cookie('nature_admin', rawToken, httponly=True, secure=settings().public_base_url.startswith('https://'), samesite='strict', path='/api/admin')
    response.headers['Cache-Control'] = 'no-store'
    return {'must_change': account.must_change}


@api.post('/api/admin/password')
def ChangePassword(data: PasswordInput, session=Depends(AdminSession), db=Depends(get_db)):
    account = db.get(m.AdminAccount, session.admin_id)
    print('[开始] 管理密码修改验证')
    if not CheckPassword(data.current_password, account.password_hash) or data.current_password == data.new_password:
        print('[分支] 旧密码错误或新密码未改变')
        fail(422, 'password_invalid', '请核对原密码并使用不同的新密码')
    else:
        print('[分支] 密码更改有效')
    print('[结束] 管理密码修改验证')
    account.password_hash, account.must_change = HashPassword(data.new_password), False
    db.query(m.AdminSession).filter(m.AdminSession.id != session.id).delete()
    Audit(db, account.id, 'password_changed', account.id, {})
    db.commit()
    return {'changed': True}


@api.post('/api/admin/logout')
def Logout(response: Response, session=Depends(AdminSession), db=Depends(get_db)):
    db.delete(session)
    db.commit()
    response.delete_cookie('nature_admin', path='/api/admin')
    return {'logged_out': True}


@api.get('/api/admin/overview')
def Overview(admin=Depends(Admin), db=Depends(get_db)):
    dayStart = datetime.combine(datetime.now(billing.beijingZone).date(), datetime.min.time(),
                                billing.beijingZone).astimezone(timezone.utc).isoformat()
    activeUsers = select(m.Task.user_id).where(m.Task.created_at >= dayStart).union(
        select(m.Project.user_id).where(m.Project.updated_at >= dayStart)).subquery()
    return {'users': db.scalar(select(func.count()).select_from(m.User)),
        'active_today': db.scalar(select(func.count()).select_from(activeUsers)),
        'queued_tasks': db.scalar(select(func.count()).select_from(m.Task).where(m.Task.status == 'queued', m.Task.deleted == False)),
        'running_tasks': db.scalar(select(func.count()).select_from(m.Task).where(m.Task.status == 'running', m.Task.deleted == False)),
        'failed_today': db.scalar(select(func.count()).select_from(m.Task).where(m.Task.status == 'failed', m.Task.updated_at >= dayStart, m.Task.deleted == False)),
        'disabled_users': db.scalar(select(func.count()).select_from(m.User).where(m.User.active == False)),
        'pending_posts': db.scalar(select(func.count()).select_from(m.Post).where(m.Post.review_status == 'pending', m.Post.deleted == False)),
        'pending_feedback': db.scalar(select(func.count()).select_from(m.Feedback).where(m.Feedback.status != 'resolved')),
        'community': getattr(db.get(m.PlatformControl, 'community'), 'value', {'enabled': True, 'message': '社区发布维护中'}),
        'providers': [Serialize(provider) | {'balance': None, 'balance_status': '暂不可查询'} for provider in db.scalars(select(m.Provider))],
        'billing': [dict(row._mapping) for row in db.execute(select(m.Charge.provider_id, m.Charge.state,
            func.sum(m.Charge.actual_micros).label('actual_micros'), func.sum(m.Charge.reserved_micros).label('reserved_micros'),
            func.count().label('count')).join(m.DailyBudget, m.DailyBudget.id == m.Charge.budget_id).where(m.DailyBudget.day == billing.Day()).group_by(m.Charge.provider_id, m.Charge.state))]}


@api.get('/api/admin/list/{section}')
def ListRecords(section: str, q: str = '', cursor: str | None = None, admin=Depends(Admin), db=Depends(get_db)):
    choices = {'users': m.User, 'tasks': m.Task, 'charges': m.Charge, 'feedback': m.Feedback, 'announcements': m.Announcement,
        'archives': m.Archive, 'audit': m.Audit, 'reports': m.Report, 'posts': m.Post, 'comments': m.Comment, 'species': m.Species,
        'corrections': m.Correction}
    print('[开始] 后台列表选择')
    if section not in choices:
        print('[分支] 未知列表')
        fail(404, 'not_found', '列表不存在')
    else:
        print('[分支] 授权管理列表')
    print('[结束] 后台列表选择')
    model = choices[section]
    query = select(model)
    print('[开始] 私人图鉴列表约束')
    if section == 'species':
        print('[分支] 仅列出有确认照片的用户物种')
        query = query.where(m.Species.user_id.is_not(None), m.Species.id.in_(select(m.Observation.species_id).where(m.Observation.deleted == False, m.Observation.confirmation == 'confirmed')))
    else:
        print('[分支] 普通管理列表')
    print('[结束] 私人图鉴列表约束')
    keyColumn = inspect(model).primary_key[0]
    print('[开始] 列表搜索检查')
    if q and keyColumn is not None:
        print('[分支] 按标识筛选')
        query = query.where(keyColumn.contains(q))
    else:
        print('[分支] 全部分页')
    print('[结束] 列表搜索检查')
    return svc.page(db, query.order_by(model.created_at.desc(), keyColumn), lambda item: Serialize(item) | ({'pending_revision': getattr(db.get(m.PlatformControl, 'edit:' + item.id), 'value', None)} if section == 'posts' else {}), cursor)


@api.post('/api/admin/users/{user_id}/status')
def SetUserStatus(user_id: str, data: StatusInput, admin=Depends(Admin), db=Depends(get_db)):
    user = db.get(m.User, user_id)
    print('[开始] 用户状态变更检查')
    if not user or user.deleted_at:
        print('[分支] 账号不存在或已注销')
        fail(404, 'not_found', '用户不存在或已注销，不能恢复')
    else:
        print('[分支] 更新停用状态')
    print('[结束] 用户状态变更检查')
    user.active = data.active
    print('[开始] 停用队列处理')
    if not data.active:
        print('[分支] 取消未提交任务')
        CancelQueued(db, userId=user.id)
    else:
        print('[分支] 恢复后由用户重新提交任务')
    print('[结束] 停用队列处理')
    Audit(db, admin.id, 'user_status', user.id, data.model_dump())
    db.commit()
    return {'active': user.active}


def CancelQueued(db, userId=None, providerId=None):
    query = select(m.Task).join(m.Charge, m.Charge.task_id == m.Task.id).where(m.Task.status.in_(['queued', 'running']), m.Charge.state == 'reserved')
    print('[开始] 取消范围选择')
    if userId:
        print('[分支] 当前用户')
        query = query.where(m.Task.user_id == userId)
    else:
        print('[分支] 当前模型')
        query = query.where(m.Charge.provider_id == providerId)
    print('[结束] 取消范围选择')
    tasks = list(db.scalars(query))
    print(f'[开始] 取消待提交任务，共 {len(tasks)} 条')
    for taskIndex, task in enumerate(tasks, 1):
        print(f'[开始] 取消任务 {taskIndex}/{len(tasks)}')
        task.status = 'cancelled'
        billing.Abort(db, task.id)
        print(f'[结束] 取消任务 {taskIndex}/{len(tasks)}')
    print('[结束] 取消待提交任务')


@api.put('/api/admin/providers/{provider_id}')
def SetProvider(provider_id: str, data: ProviderInput, admin=Depends(Admin), db=Depends(get_db)):
    provider = db.get(m.Provider, provider_id)
    print('[开始] 模型配置检查')
    if not provider or data.output_limit >= data.context_limit or (provider_id == 'qwen' and data.context_limit > settings().qwen_context_max):
        print('[分支] 模型或上下文参数无效')
        fail(422, 'provider_invalid', '输出空间必须小于上下文上限，且上下文不能超过部署配置的模型上限')
    else:
        print('[分支] 保存模型配置')
    print('[结束] 模型配置检查')
    db.execute(update(m.Provider).where(m.Provider.id == provider_id).values(**data.model_dump(), updated_at=m.now()))
    print('[开始] 服务暂停处理')
    if not data.enabled:
        print('[分支] 取消尚未提交模型的任务')
        CancelQueued(db, providerId=provider_id)
    else:
        print('[分支] 恢复接收，不重放历史任务')
    print('[结束] 服务暂停处理')
    Audit(db, admin.id, 'provider_settings', provider_id, data.model_dump())
    db.commit()
    return {'saved': True}


@api.get('/api/admin/pricing/{provider_id}')
def GetPricing(provider_id: str, admin=Depends(Admin), db=Depends(get_db)):
    print('[开始] 计费模型检查')
    if provider_id not in {'qwen', 'image'}:
        print('[分支] 未知模型')
        print('[结束] 计费模型检查；提前结束')
        fail(404, 'not_found', '模型不存在')
    else:
        print('[分支] 读取已配置单价')
    print('[结束] 计费模型检查')
    control = db.get(m.PlatformControl, 'pricing:' + provider_id)
    return {'pricing': control.value if control else billing.Pricing(db, provider_id),
        'model': runtime_config.ReadProvider(db, provider_id)['model']}


@api.put('/api/admin/pricing/{provider_id}')
def SetPricing(provider_id: str, data: PricingInput, admin=Depends(Admin), db=Depends(get_db)):
    print('[开始] 计费单价保存检查')
    if provider_id not in {'qwen', 'image'}:
        print('[分支] 未知模型')
        print('[结束] 计费单价保存检查；提前结束')
        fail(404, 'not_found', '模型不存在')
    else:
        print('[分支] 保存人民币合同单价，只影响新任务')
    print('[结束] 计费单价保存检查')
    runtimeValues = runtime_config.ReadProvider(db, provider_id)
    values = data.model_dump(mode='json') | {'model': runtimeValues['model'],
        'base_url': runtimeValues['base_url'].rstrip('/'), 'updated_at': m.now()}
    billing.InsertOnce(db, m.PlatformControl, {'id': 'pricing:' + provider_id, 'value': {}})
    db.get(m.PlatformControl, 'pricing:' + provider_id).value = values
    Audit(db, admin.id, 'pricing_changed', provider_id, values)
    db.commit()
    return {'saved': True, 'applies_to': 'new_tasks'}


@api.post('/api/admin/quotas')
def ChangeQuota(data: QuotaInput, admin=Depends(Admin), db=Depends(get_db)):
    amount = int(data.amount * billing.moneyScale)
    tomorrow = (datetime.now(billing.beijingZone).date() + timedelta(days=1)).isoformat()
    print('[开始] 额度调整方式')
    if data.mode == 'default':
        print('[分支] 默认额度次日生效')
        provider = db.get(m.Provider, data.provider)
        print('[开始] 默认额度生效检查')
        if provider.effective_day and provider.effective_day <= billing.Day():
            print('[分支] 保存已生效的默认额度')
            provider.daily_micros = provider.next_daily_micros
        else:
            print('[分支] 保留当前默认额度')
        print('[结束] 默认额度生效检查')
        provider.next_daily_micros, provider.effective_day = amount, tomorrow
    else:
        print('[分支] 用户额度调整')
        user = db.get(m.User, data.user_id)
        print('[开始] 额度所属用户检查')
        if not user or user.deleted_at:
            print('[分支] 用户不存在或已注销')
            fail(404, 'not_found', '用户不存在')
        else:
            print('[分支] 用户有效')
        print('[结束] 额度所属用户检查')
        budget = billing.Budget(db, user, data.provider)
        print('[开始] 今日追加与长期额度选择')
        if data.mode == 'topup':
            print('[分支] 追加今日额度')
            db.execute(update(m.DailyBudget).where(m.DailyBudget.id == budget.id).values(limit_micros=m.DailyBudget.limit_micros + amount))
            svc.notify(db, user.id, user.id, 'quota', 'account', user.id, '你的今日 AI 额度已增加')
        else:
            print('[分支] 长期个人额度次日生效')
            overrideId = billing.Identity(user) + ':' + data.provider
            billing.InsertOnce(db, m.QuotaOverride, dict(id=overrideId, identity_key=billing.Identity(user), provider_id=data.provider))
            override = db.get(m.QuotaOverride, overrideId)
            print('[开始] 现有个人额度生效检查')
            if override.effective_day and override.effective_day <= billing.Day():
                print('[分支] 保存已生效额度')
                override.amount_micros = override.next_amount_micros
            else:
                print('[分支] 当前额度保持')
            print('[结束] 现有个人额度生效检查')
            override.next_amount_micros = None
            print('[开始] 恢复默认或指定额度')
            if data.mode == 'personal':
                print('[分支] 指定额度')
                override.next_amount_micros = amount
            else:
                print('[分支] 恢复默认')
            print('[结束] 恢复默认或指定额度')
            override.effective_day = tomorrow
        print('[结束] 今日追加与长期额度选择')
    print('[结束] 额度调整方式')
    Audit(db, admin.id, 'quota_changed', data.user_id or data.provider, data.model_dump(mode='json'))
    db.commit()
    return {'saved': True, 'effective_day': billing.Day() if data.mode == 'topup' else tomorrow, 'mode': data.mode}


@api.post('/api/admin/charges/{task_id}/settle')
def Settle(task_id: str, data: SettlementInput, admin=Depends(Admin), db=Depends(get_db)):
    charge = db.get(m.Charge, task_id)
    print('[开始] 人工费用对账检查')
    if not charge or charge.state not in {'pending', 'submitted'}:
        print('[分支] 当前账单不可结算')
        fail(409, 'charge_unavailable', '请对已结束且待核对的任务结算')
    else:
        print('[分支] 核实任务已结束')
    task = db.get(m.Task, task_id)
    print('[开始] 结算任务状态检查')
    if task.status in {'queued', 'running'} or (task.lease_until and task.lease_until > m.now()):
        print('[分支] 任务未结束')
        fail(409, 'task_active', '任务尚未结束')
    else:
        print('[分支] 可以录入服务商实际账单')
    print('[结束] 结算任务状态检查')
    print('[结束] 人工费用对账检查')
    billing.Finalize(db, task_id, int(data.amount * billing.moneyScale), evidence=data.evidence)
    Audit(db, admin.id, 'charge_settled', task_id, data.model_dump(mode='json'))
    db.commit()
    return {'settled': True}


@api.post('/api/admin/review/{kind}/{item_id}')
def Review(kind: str, item_id: str, data: ReviewInput, admin=Depends(Admin), db=Depends(get_db)):
    model = {'post': m.Post, 'comment': m.Comment}.get(kind)
    print('[开始] 审核目标检查')
    if model is None:
        print('[分支] 不支持的审核类型')
        fail(404, 'not_found', '审核类型不存在')
    else:
        print('[分支] 查询审核内容')
    item = db.get(model, item_id)
    print('[开始] 审核内容存在检查')
    if not item or item.deleted:
        print('[分支] 内容不存在')
        fail(404, 'not_found', '内容不存在')
    else:
        print('[分支] 更新审核状态')
    print('[结束] 审核内容存在检查')
    print('[结束] 审核目标检查')
    control = db.get(m.PlatformControl, 'review:' + kind + ':' + item.id)
    print('[开始] 自动审核覆盖检查')
    if control:
        print('[分支] 人工决定优先，后续回调不能覆盖')
        control.value = {**control.value, 'state':'manual_override'}
    else:
        print('[分支] 当前没有自动审核')
    print('[结束] 自动审核覆盖检查')
    pending = db.get(m.PlatformControl, 'edit:' + item.id) if kind == 'post' else None
    print('[开始] 审核版本选择')
    if pending:
        print('[分支] 审核公开内容的新版本')
        print('[开始] 修改版本审核决定')
        if data.status == 'approved':
            print('[分支] 用已通过版本替换公开内容')
            print(f'[开始] 审核字段写入，共 {len(pending.value)} 项')
            for fieldIndex, (field, value) in enumerate(pending.value.items(), 1):
                print(f'[开始] 审核字段 {fieldIndex}/{len(pending.value)}')
                setattr(item, field, value)
                print(f'[结束] 审核字段 {fieldIndex}/{len(pending.value)}')
            print('[结束] 审核字段写入')
        else:
            print('[分支] 拒绝修改，旧版继续公开')
        print('[结束] 修改版本审核决定')
        Audit(db, admin.id, 'post_revision_review', item.id, {'submitted': pending.value, 'decision': data.status})
        db.delete(pending)
        item.review_reason = data.reason
    else:
        print('[分支] 首次审核或普通评论审核')
        item.review_status, item.review_reason = data.status, data.reason
    print('[结束] 审核版本选择')
    svc.notify(db, item.user_id, item.user_id, 'review', kind, item.id, '你的内容审核状态已更新')
    Audit(db, admin.id, 'content_review', item.id, data.model_dump())
    db.commit()
    return {'status': item.review_status}


@api.post('/api/admin/feedback/{feedback_id}/reply')
def Reply(feedback_id: str, data: ReplyInput, admin=Depends(Admin), db=Depends(get_db)):
    item = db.get(m.Feedback, feedback_id)
    print('[开始] 反馈回复检查')
    if not item:
        print('[分支] 反馈不存在')
        fail(404, 'not_found', '反馈不存在')
    else:
        print('[分支] 写入回复')
    print('[结束] 反馈回复检查')
    item.replies = item.replies + [{'role': 'admin', 'text': data.text, 'created_at': m.now()}]
    item.status = data.status
    svc.notify(db, item.user_id, item.user_id, 'feedback', 'feedback', item.id, '你的反馈收到管理员回复')
    Audit(db, admin.id, 'feedback_reply', item.id, data.model_dump())
    db.commit()
    return Serialize(item)


@api.post('/api/admin/announcements')
def PublishAnnouncement(data: AnnouncementInput, admin=Depends(Admin), db=Depends(get_db)):
    print('[开始] 公告时间检查')
    if data.starts_at.tzinfo is None or data.ends_at.tzinfo is None or data.ends_at <= data.starts_at:
        print('[分支] 时间无效')
        fail(422, 'invalid_time', '请填写含时区且先后正确的公告时间')
    else:
        print('[分支] 保存公告')
    print('[结束] 公告时间检查')
    values = data.model_dump(exclude={'starts_at', 'ends_at'})
    item = m.Announcement(**values, starts_at=data.starts_at.astimezone(timezone.utc).isoformat(), ends_at=data.ends_at.astimezone(timezone.utc).isoformat())
    db.add(item)
    db.flush()
    Audit(db, admin.id, 'announcement_created', item.id, {'status': item.status})
    db.commit()
    return Serialize(item)


@api.post('/api/admin/atlas/group')
def Regroup(data: GroupInput, admin=Depends(Admin), db=Depends(get_db)):
    db.execute(update(m.Species).where(m.Species.id.in_(data.species_ids), m.Species.user_id.is_not(None)).values(group_key=data.group_key))
    Audit(db, admin.id, 'atlas_regrouped', data.group_key, data.model_dump())
    db.commit()
    return {'saved': True}


@api.get('/api/admin/atlas/{group_key}/photos')
def GroupPhotos(group_key: str, cursor: str | None = None, admin=Depends(Admin), db=Depends(get_db)):
    query = select(m.Observation).join(m.Species, m.Species.id == m.Observation.species_id).join(m.Asset, m.Asset.id == m.Observation.asset_id).where(
        m.Species.group_key == group_key, m.Observation.deleted == False, m.Asset.deleted == False, m.Observation.confirmation == 'confirmed')
    return svc.page(db, query.order_by(m.Observation.created_at.desc()),
        lambda record: svc.observation_json(db, record, db.get(m.User, record.user_id)) | {'user_id': record.user_id, 'photographer': db.get(m.User, record.user_id).name}, cursor)


@api.post('/api/admin/atlas/{species_id}/correction')
def SuggestCorrection(species_id: str, data: CorrectionInput, admin=Depends(Admin), db=Depends(get_db)):
    species = db.get(m.Species, species_id)
    print('[开始] 更正建议目标检查')
    if not species or not species.user_id:
        print('[分支] 无个人物种')
        fail(404, 'not_found', '个人物种不存在')
    else:
        print('[分支] 建议由用户确认')
    print('[结束] 更正建议目标检查')
    item = m.Correction(user_id=species.user_id, species_id=species.id, **data.model_dump())
    db.add(item)
    db.flush()
    svc.notify(db, species.user_id, species.user_id, 'correction', 'correction', item.id, '你收到一条物种更正建议')
    Audit(db, admin.id, 'species_correction', species.id, data.model_dump())
    db.commit()
    return Serialize(item)


class CommunityInput(Input):
    enabled: bool
    message: str = Field(default='社区发布维护中，请稍后再试', min_length=1, max_length=200)


class PurgeInput(Input):
    password: str = Field(min_length=1, max_length=200)
    confirmation: str


@api.post('/api/admin/archives/{archive_id}/purge')
def PurgeArchivedContent(archive_id: str, data: PurgeInput, admin=Depends(Admin), db=Depends(get_db)):
    print('[开始] 清理操作验证频率检查')
    if admin.locked_until and admin.locked_until > m.now():
        print('[分支] 密码尝试过多，暂停身份验证')
        fail(429, 'reauth_locked', '身份验证暂时锁定，请稍后重试')
    else:
        print('[分支] 可以重新验证')
    print('[结束] 清理操作验证频率检查')
    print('[开始] 永久清理重新验证')
    if data.confirmation != archive_id or not CheckPassword(data.password, admin.password_hash):
        print('[分支] 身份或操作确认无效')
        admin.failed_attempts += 1
        print('[开始] 清理身份验证锁定检查')
        if admin.failed_attempts >= 5:
            print('[分支] 锁定十五分钟')
            admin.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        else:
            print('[分支] 未达到锁定阈值')
        print('[结束] 清理身份验证锁定检查')
        db.commit()
        fail(403, 'reauth_failed', '请重新验证管理员密码和清理目标')
    else:
        print('[分支] 已验证管理员身份与操作目标')
    print('[结束] 永久清理重新验证')
    archive = db.get(m.Archive, archive_id)
    print('[开始] 清理归档存在检查')
    if archive is None:
        print('[分支] 归档不存在')
        fail(404, 'not_found', '归档不存在')
    else:
        print('[分支] 将当前归档标记到期')
    print('[结束] 清理归档存在检查')
    archive.expires_at = m.now()
    Audit(db, admin.id, 'archive_purged', archive.id, {'resource_type':archive.resource_type, 'resource_id':archive.resource_id})
    db.flush()
    retention.ExpireArchives(db)
    return {'purged': True, 'independent_references_preserved': True}


@api.get('/api/admin/media/{kind}/{item_id}/{image_index}')
def PreviewMedia(kind: str, item_id: str, image_index: int, admin=Depends(Admin), db=Depends(get_db)):
    print('[开始] 管理媒体类型检查')
    if kind == 'archive':
        print('[分支] 查看管理归档')
        record = db.get(m.Archive, item_id)
        keys = sorted(retention.MediaKeys(record.snapshot)) if record else []
    elif kind == 'post':
        print('[分支] 查看待审帖子')
        record = db.get(m.Post, item_id)
        keys = record.images if record else []
    elif kind == 'asset':
        print('[分支] 查看总图鉴素材')
        record = db.get(m.Asset, item_id)
        keys = [record.key] if record and record.key else []
    else:
        print('[分支] 不支持的类型')
        keys = []
    print('[结束] 管理媒体类型检查')
    print('[开始] 管理媒体范围检查')
    if image_index < 0 or image_index >= len(keys):
        print('[分支] 图片不存在')
        fail(404, 'not_found', '图片不存在')
    else:
        print('[分支] 当前管理会话可读取图片')
    print('[结束] 管理媒体范围检查')
    Audit(db, admin.id, 'media_viewed', item_id, {'kind': kind, 'index': image_index})
    db.commit()
    key = keys[image_index]
    return Response(storage.read(key), media_type='image/jpeg' if key.endswith(('.jpg', '.jpeg')) else 'image/png',
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


class ReportInput(Input):
    action: str = Field(pattern='^(hide|dismiss)$')
    reason: str = Field(min_length=1, max_length=500)


@api.put('/api/admin/community')
def SetCommunity(data: CommunityInput, admin=Depends(Admin), db=Depends(get_db)):
    control = db.get(m.PlatformControl, 'community')
    print('[开始] 社区维护配置检查')
    if control is None:
        print('[分支] 创建维护配置')
        control = m.PlatformControl(id='community')
        db.add(control)
    else:
        print('[分支] 更新维护配置')
    print('[结束] 社区维护配置检查')
    control.value = data.model_dump()
    Audit(db, admin.id, 'community_settings', 'community', control.value)
    db.commit()
    return control.value


@api.put('/api/admin/announcements/{announcement_id}')
def EditAnnouncement(announcement_id: str, data: AnnouncementInput, admin=Depends(Admin), db=Depends(get_db)):
    item = db.get(m.Announcement, announcement_id)
    print('[开始] 公告修改检查')
    if not item or data.starts_at.tzinfo is None or data.ends_at.tzinfo is None or data.ends_at <= data.starts_at:
        print('[分支] 公告不存在或时间不合法')
        fail(422, 'invalid_announcement', '请核对公告与时间范围')
    else:
        print('[分支] 保存完整公告版本')
    print('[结束] 公告修改检查')
    item.title, item.text, item.user_ids, item.status = data.title, data.text, data.user_ids, data.status
    item.starts_at, item.ends_at = data.starts_at.astimezone(timezone.utc).isoformat(), data.ends_at.astimezone(timezone.utc).isoformat()
    Audit(db, admin.id, 'announcement_updated', item.id, {'status': item.status})
    db.commit()
    return Serialize(item)


@api.post('/api/admin/reports/{report_id}')
def ResolveReport(report_id: str, data: ReportInput, admin=Depends(Admin), db=Depends(get_db)):
    report = db.get(m.Report, report_id)
    print('[开始] 举报记录检查')
    if not report or report.status != 'open':
        print('[分支] 举报不存在或已经处理')
        fail(409, 'report_unavailable', '举报不存在或已处理')
    else:
        print('[分支] 处理举报')
    print('[结束] 举报记录检查')
    print('[开始] 举报处理决定')
    if data.action == 'hide':
        print('[分支] 限制对应内容或账号')
        target = db.get({'post': m.Post, 'comment': m.Comment, 'user': m.User}[report.target_type], report.target_id)
        print('[开始] 举报目标状态')
        if isinstance(target, m.Post):
            print('[分支] 下架帖子')
            target.hidden = True
        elif isinstance(target, m.Comment):
            print('[分支] 归档并移除评论')
            atlas.SaveArchive(db, target.user_id, 'comment', target, '举报处理')
            target.deleted = True
        elif isinstance(target, m.User):
            print('[分支] 暂停账号并取消未提交任务')
            target.active = False
            CancelQueued(db, userId=target.id)
        else:
            print('[分支] 目标已不存在，仅保留处理记录')
        print('[结束] 举报目标状态')
        report.status = 'resolved'
    else:
        print('[分支] 驳回举报')
        report.status = 'dismissed'
    print('[结束] 举报处理决定')
    Audit(db, admin.id, 'report_resolved', report.id, data.model_dump())
    db.commit()
    return Serialize(report)
