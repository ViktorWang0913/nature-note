"""Integer RMB micro-units; unverified upstream charges remain explicitly pending."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from sqlalchemy import select, update, func, or_, and_
from sqlalchemy.dialects.sqlite import insert as sqliteInsert
from sqlalchemy.dialects.postgresql import insert as postgresInsert

from . import models as m, runtime_config
from .security import fail, sign
from .config import settings

# 参数设置
moneyScale = 1000000
beijingZone = timezone(timedelta(hours=8))


def Day():
    return datetime.now(beijingZone).date().isoformat()


def Identity(user):
    return sign('quota:' + user.identity)


def ProviderId(kind):
    return {'image_generation': 'image', 'image_polish': 'image', 'image_recognition': 'qwen', 'route_summary': 'qwen', 'rag': 'qwen'}[kind]


def Pricing(db, providerId, runtimeValues=None):
    cfg = settings()
    runtimeValues = runtimeValues or runtime_config.ReadProvider(db, providerId)
    target = {'model': runtimeValues['model'], 'base_url': runtimeValues['base_url'].rstrip('/')}
    control = db.get(m.PlatformControl, 'pricing:' + providerId)
    print('[开始] 计费配置来源检查')
    if control:
        print('[分支] 使用管理员确认的单价')
        prices = dict(control.value)
        print('[开始] 单价对应模型检查')
        if prices['model'] != target['model'] or prices['base_url'] != target['base_url']:
            print('[分支] 模型或服务商已变更，拒绝套用旧价格')
            print('[结束] 单价对应模型检查；提前结束计费配置来源检查')
            fail(503, 'pricing_changed', '模型配置已更新，计费正在核对，请稍后再试')
        else:
            print('[分支] 单价与当前模型一致')
        print('[结束] 单价对应模型检查')
    else:
        print('[分支] 使用部署配置中的合同价格')
        prices = dict(target, input_rate=cfg.qwen_input_cny_per_million, output_rate=cfg.qwen_output_cny_per_million,
            tier_threshold=cfg.qwen_tier_threshold, high_input_rate=cfg.qwen_high_input_cny_per_million,
            high_output_rate=cfg.qwen_high_output_cny_per_million, per_call=cfg.image_cny_per_call,
            evidence='部署环境中的管理员合同单价，人民币')
    print('[结束] 计费配置来源检查')
    provider = db.get(m.Provider, providerId)
    return prices | {'provider': providerId, 'fallback_micros': provider.reserve_micros,
        'context_limit': min(provider.context_limit, cfg.qwen_context_max), 'output_limit': provider.output_limit}


def TokenCost(usage, pricing):
    inputTokens, outputTokens = usage.get('prompt_tokens'), usage.get('completion_tokens')
    print('[开始] token 用量有效性检查')
    if type(inputTokens) is not int or type(outputTokens) is not int or inputTokens < 0 or outputTokens < 0:
        print('[分支] 用量不完整或无效，不能推算实际费用')
        print('[结束] token 用量有效性检查；提前结束')
        return None
    else:
        print('[分支] 使用服务商返回的完整用量')
    print('[结束] token 用量有效性检查')
    inputRate, outputRate = pricing.get('input_rate'), pricing.get('output_rate')
    print('[开始] 长上下文阶梯检查')
    if inputTokens > pricing.get('tier_threshold', 128000):
        print('[分支] 整次调用使用长上下文档位')
        inputRate, outputRate = pricing.get('high_input_rate'), pricing.get('high_output_rate')
    else:
        print('[分支] 使用普通档位')
    print('[结束] 长上下文阶梯检查')
    print('[开始] 合同单价完整性检查')
    if inputRate is None or outputRate is None:
        print('[分支] 缺少对应档位价格，等待账单')
        print('[结束] 合同单价完整性检查；提前结束')
        return None
    else:
        print('[分支] 按单价计算人民币微元')
    print('[结束] 合同单价完整性检查')
    amount = Decimal(str(inputRate)) * inputTokens + Decimal(str(outputRate)) * outputTokens
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def EstimateCost(pricing, task):
    print('[开始] 请求费用预留计算')
    if pricing['provider'] == 'qwen':
        print('[分支] 按上下文容量和最大输出保守预留')
        outputTokens = max(1200, pricing['output_limit'])
        amount = TokenCost({'prompt_tokens': pricing['context_limit'], 'completion_tokens': outputTokens}, pricing)
    elif pricing.get('per_call') is not None:
        print('[分支] 首版单张图片按确认的每次单价预留')
        amount = int((Decimal(str(pricing['per_call'])) * moneyScale).to_integral_value(rounding=ROUND_CEILING))
    else:
        print('[分支] 未配置价格，采用明确标记的暂占金额')
        amount = None
    print('[结束] 请求费用预留计算')
    return max(1, pricing['fallback_micros'] if amount is None else amount)


def BeginCall(db, task, callId):
    # A charge row serializes reservation changes on both SQLite and PostgreSQL.
    db.execute(update(m.Charge).where(m.Charge.task_id == task.id).values(updated_at=m.now()))
    charge = db.get(m.Charge, task.id, populate_existing=True)
    print('[开始] 单次上游请求许可检查')
    if charge is None or charge.state not in {'submitted', 'pending'} or charge.metering.get('inflight') or callId in charge.metering.get('calls', {}):
        print('[分支] 原请求未核清或已经执行，禁止重复收费')
        print('[结束] 单次上游请求许可检查；提前结束')
        raise RuntimeError('原请求已提交或尚待核对，不会自动重复调用')
    else:
        print('[分支] 核对用户与执行状态')
    print('[结束] 单次上游请求许可检查')
    active = db.scalar(select(m.Task.id).join(m.User, m.User.id == m.Task.user_id).join(
        m.Provider, m.Provider.id == charge.provider_id).where(m.Task.id == task.id, m.Task.status == 'running',
        m.Task.lease_owner == task.lease_owner, m.User.active == True, m.User.deleted_at.is_(None), m.Provider.enabled == True))
    print('[开始] 调用前取消检查')
    if active is None:
        print('[分支] 已停止，不再提交新的付费请求')
        print('[结束] 调用前取消检查；提前结束')
        raise RuntimeError('任务或服务已停止')
    else:
        print('[分支] 可以申请本次费用')
    print('[结束] 调用前取消检查')
    pricing = charge.pricing
    cfg = settings()
    taskProvider = runtime_config.ReadTaskProvider(db, task, charge.provider_id)
    print('[开始] 任务模型与计费快照检查')
    if pricing.get('model') != taskProvider['model'] or pricing.get('base_url') != taskProvider['base_url'].rstrip('/'):
        print('[分支] 任务模型与计费快照不一致，停止当前任务')
        print('[结束] 任务模型与计费快照检查；提前结束')
        raise RuntimeError('模型已变更，请重新提交任务以使用新的计费配置')
    else:
        print('[分支] 模型一致，保留创建任务时的单价')
    print('[结束] 任务模型与计费快照检查')
    provider = db.get(m.Provider, charge.provider_id, populate_existing=True)
    amount = EstimateCost(pricing | {'context_limit': max(pricing['context_limit'], min(provider.context_limit, cfg.qwen_context_max)),
        'output_limit': max(pricing['output_limit'], provider.output_limit)}, task)
    previous = sum(call['reserved_micros'] if call['actual_micros'] is None else call['actual_micros']
        for call in charge.metering.get('calls', {}).values())
    extra = max(0, previous + amount - charge.reserved_micros)
    changed = db.execute(update(m.DailyBudget).where(m.DailyBudget.id == charge.budget_id,
        m.DailyBudget.limit_micros - m.DailyBudget.spent_micros - m.DailyBudget.held_micros >= extra
        ).values(held_micros=m.DailyBudget.held_micros + extra))
    print('[开始] 摘要与回答累计预算检查')
    if changed.rowcount != 1:
        print('[分支] 剩余额度不足，停止后续调用并结算已完成部分')
        print('[结束] 摘要与回答累计预算检查；提前结束')
        raise RuntimeError('本次对话的剩余额度不足，已保留完成的内容，请稍后继续')
    else:
        print('[分支] 本次费用已预留')
    print('[结束] 摘要与回答累计预算检查')
    charge.reserved_micros += extra
    charge.metering = {**charge.metering, 'inflight': callId, 'call_reserve_micros': amount}
    db.commit()


def RecordCall(db, task, callId, usage, imageCompleted=False):
    db.execute(update(m.Charge).where(m.Charge.task_id == task.id).values(updated_at=m.now()))
    charge = db.get(m.Charge, task.id, populate_existing=True)
    print('[开始] 上游用量持久化检查')
    if charge is None or charge.state in {'settled', 'released'} or charge.metering.get('inflight') != callId:
        print('[分支] 已记录或已结算，忽略重复响应')
        print('[结束] 上游用量持久化检查；提前结束')
        return
    else:
        print('[分支] 先保存计费证据，再处理业务结果')
    print('[结束] 上游用量持久化检查')
    print('[开始] 实际费用方式选择')
    if charge.provider_id == 'qwen':
        print('[分支] 实际 token 乘任务价格快照')
        actualMicros = TokenCost(usage, charge.pricing)
    elif imageCompleted and charge.pricing.get('per_call') is not None:
        print('[分支] 单张生图完成，按确认的每次人民币单价')
        actualMicros = int((Decimal(str(charge.pricing['per_call'])) * moneyScale).to_integral_value(rounding=ROUND_CEILING))
    else:
        print('[分支] 无法确认费用，继续待核对')
        actualMicros = None
    print('[结束] 实际费用方式选择')
    calls = {**charge.metering.get('calls', {}), callId: {'usage': usage, 'actual_micros': actualMicros,
        'reserved_micros': charge.metering['call_reserve_micros'], 'recorded_at': m.now()}}
    charge.metering = {**charge.metering, 'calls': calls, 'inflight': None}
    charge.usage = usage
    db.commit()


def InsertOnce(db, model, values):
    dialectName = db.get_bind().dialect.name
    print('[开始] 幂等写入方言选择')
    if dialectName == 'sqlite':
        print('[分支] SQLite 幂等插入')
        statement = sqliteInsert(model).values(**values).on_conflict_do_nothing()
    else:
        print('[分支] PostgreSQL 幂等插入')
        statement = postgresInsert(model).values(**values).on_conflict_do_nothing()
    print('[结束] 幂等写入方言选择')
    db.execute(statement)


def Budget(db, user, providerId):
    today = Day()
    identityKey = Identity(user)
    provider = db.get(m.Provider, providerId)
    limit = provider.daily_micros
    print('[开始] 默认额度生效检查')
    if provider.effective_day and provider.effective_day <= today:
        print('[分支] 使用已生效的新默认额度')
        limit = provider.next_daily_micros
    else:
        print('[分支] 使用当前默认额度')
    print('[结束] 默认额度生效检查')
    override = db.get(m.QuotaOverride, identityKey + ':' + providerId)
    print('[开始] 个人额度覆盖检查')
    if override:
        print('[分支] 读取个人额度')
        amount = override.amount_micros
        print('[开始] 个人额度生效日期')
        if override.effective_day and override.effective_day <= today:
            print('[分支] 使用新个人额度或恢复默认')
            amount = override.next_amount_micros
        else:
            print('[分支] 使用现有个人额度')
        print('[结束] 个人额度生效日期')
        print('[开始] 个人额度数值检查')
        if amount is not None:
            print('[分支] 覆盖默认额度')
            limit = amount
        else:
            print('[分支] 使用默认额度')
        print('[结束] 个人额度数值检查')
    else:
        print('[分支] 无个人覆盖')
    print('[结束] 个人额度覆盖检查')
    budgetId = identityKey + ':' + providerId + ':' + today
    InsertOnce(db, m.DailyBudget, dict(id=budgetId, identity_key=identityKey, provider_id=providerId,
                                     day=today, limit_micros=limit, held_micros=0, spent_micros=0))
    return db.get(m.DailyBudget, budgetId, populate_existing=True)


def Reserve(db, user, task):
    providerId = ProviderId(task.kind)
    provider = db.get(m.Provider, providerId)
    print('[开始] AI 服务可用检查')
    if not provider.enabled:
        print('[分支] 服务暂停')
        fail(503, 'provider_paused', provider.message)
    else:
        print('[分支] 服务可用')
    print('[结束] AI 服务可用检查')
    budget = Budget(db, user, providerId)
    slotId = Identity(user) + ':' + providerId
    InsertOnce(db, m.UserTaskSlot, dict(id=slotId, task_id=None))
    acquired = db.execute(update(m.UserTaskSlot).where(m.UserTaskSlot.id == slotId,
        m.UserTaskSlot.task_id.is_(None)).values(task_id=task.id))
    print('[开始] 用户模型并发检查')
    if acquired.rowcount != 1:
        print('[分支] 已有同类任务，拒绝重复提交')
        fail(409, 'task_active', '该类 AI 任务正在处理中，请完成后再提交')
    else:
        print('[分支] 获得用户任务位置')
    print('[结束] 用户模型并发检查')
    runtimeValues = runtime_config.ReadProvider(db, providerId)
    pricing = Pricing(db, providerId, runtimeValues)
    amount = EstimateCost(pricing, task)
    reserved = db.execute(update(m.DailyBudget).where(m.DailyBudget.id == budget.id,
        m.DailyBudget.limit_micros - m.DailyBudget.held_micros - m.DailyBudget.spent_micros >= amount,
        amount > 0).values(held_micros=m.DailyBudget.held_micros + amount))
    print('[开始] 额度预占检查')
    if reserved.rowcount != 1:
        print('[分支] 今日额度不足')
        fail(429, 'daily_quota_exhausted', '当前可用额度不足以预留本次请求，请等待费用结算或明天再来')
    else:
        print('[分支] 已预占额度，完成后按实际费用结算')
    print('[结束] 额度预占检查')
    db.add(m.Charge(task_id=task.id, user_id=user.id, budget_id=budget.id, slot_id=slotId,
                    provider_id=providerId, reserved_micros=amount, pricing=pricing))
    runtime_config.Snapshot(db, task, runtimeValues)


def MarkSubmitted(db, task):
    eligible = select(m.Task.id).join(m.User, m.User.id == m.Task.user_id).where(m.Task.id == task.id,
        m.Task.status == 'running', m.User.active == True, m.User.deleted_at.is_(None))
    enabledProviders = select(m.Provider.id).where(m.Provider.enabled == True)
    changed = db.execute(update(m.Charge).where(m.Charge.task_id.in_(eligible), m.Charge.state == 'reserved',
        m.Charge.provider_id.in_(enabledProviders)).values(state='submitted', updated_at=m.now()))
    print('[开始] 模型提交幂等及取消检查')
    if changed.rowcount != 1:
        print('[分支] 已提交、取消或维护，不再次请求付费接口')
        raise RuntimeError('请求已停止或已提交过，请查看任务状态；不会自动重复调用')
    else:
        print('[分支] 本次请求取得首次提交权')
    print('[结束] 模型提交幂等及取消检查')
    db.commit()


def Finalize(db, taskId, actualMicros=None, usage=None, evidence='', releaseSlot=True):
    # Lock the charge before changing either the ledger or aggregate budget.
    db.execute(update(m.Charge).where(m.Charge.task_id == taskId).values(updated_at=m.now()))
    charge = db.scalar(select(m.Charge).where(m.Charge.task_id == taskId).with_for_update().execution_options(populate_existing=True))
    print('[开始] 任务费用结算')
    if charge is None or charge.state in {'settled', 'released'}:
        print('[分支] 无账单或已结算，幂等退出')
        print('[开始] 已结算任务执行位置检查')
        if charge and releaseSlot:
            print('[分支] 执行器已退出，释放同一任务的位置')
            db.execute(update(m.UserTaskSlot).where(m.UserTaskSlot.id == charge.slot_id,
                m.UserTaskSlot.task_id == taskId).values(task_id=None))
        else:
            print('[分支] 无需释放')
        print('[结束] 已结算任务执行位置检查')
        print('[结束] 任务费用结算；提前结束')
        return
    else:
        print('[分支] 处理未结算费用')
    print('[开始] 已持久化用量核对')
    if actualMicros is None and 'calls' in charge.metering and not charge.metering.get('inflight'):
        print('[分支] 尝试按完整调用账本结算')
        costs = [call['actual_micros'] for call in charge.metering['calls'].values()]
        actualMicros = sum(costs) if all(cost is not None for cost in costs) else None
        evidence = evidence or '逐次服务商用量与任务创建时确认的人民币单价；详见 metering 和 pricing'
    else:
        print('[分支] 使用显式账单或继续等待用量')
    print('[结束] 已持久化用量核对')
    print('[开始] 实际费用确认')
    if actualMicros is None:
        print('[分支] 无明确账单，保留暂占并等待对账')
        charge.state = 'pending'
    else:
        print('[分支] 使用经确认的实际费用')
        amount = int(actualMicros)
        print('[开始] 金额有效性检查')
        if amount < 0:
            print('[分支] 拒绝负费用')
            raise ValueError('实际费用不能为负数')
        else:
            print('[分支] 金额有效')
        print('[结束] 金额有效性检查')
        changed = db.execute(update(m.Charge).where(m.Charge.task_id == taskId,
            m.Charge.state.in_(['reserved', 'submitted', 'pending'])).values(state='settled', actual_micros=amount))
        print('[开始] 并发结算幂等检查')
        if changed.rowcount != 1:
            print('[分支] 已被另一请求结算')
            print('[结束] 并发结算幂等检查；提前结束实际费用确认和任务费用结算')
            return
        else:
            print('[分支] 本次拥有结算权')
        print('[结束] 并发结算幂等检查')
        db.execute(update(m.DailyBudget).where(m.DailyBudget.id == charge.budget_id).values(
            held_micros=m.DailyBudget.held_micros - charge.reserved_micros,
            spent_micros=m.DailyBudget.spent_micros + amount))
    print('[结束] 实际费用确认')
    charge.usage = usage or charge.usage
    charge.evidence = evidence or charge.evidence
    charge.updated_at = m.now()
    print('[开始] 用户执行位置释放检查')
    if releaseSlot:
        print('[分支] 执行器已退出，释放位置')
        db.execute(update(m.UserTaskSlot).where(m.UserTaskSlot.id == charge.slot_id,
            m.UserTaskSlot.task_id == taskId).values(task_id=None))
    else:
        print('[分支] 等待上游执行器退出')
    print('[结束] 用户执行位置释放检查')
    print('[结束] 任务费用结算')


def Abort(db, taskId):
    # Re-read under the same write lock as submission, so a stale reserved state cannot refund a submitted call.
    db.execute(update(m.Charge).where(m.Charge.task_id == taskId).values(updated_at=m.now()))
    charge = db.get(m.Charge, taskId, populate_existing=True)
    print('[开始] 未执行任务额度释放')
    if charge and charge.state == 'reserved':
        print('[分支] 尚未提交模型，确认零费用')
        Finalize(db, taskId, 0, evidence='任务尚未提交模型')
    else:
        print('[分支] 已提交或未知，等待实际费用核对')
        Finalize(db, taskId, releaseSlot=False)
    print('[结束] 未执行任务额度释放')


def UserQuota(db, user):
    items = []
    print('[开始] 两类额度读取')
    for providerIndex, providerId in enumerate(('qwen', 'image'), 1):
        print(f'[开始] 额度 {providerIndex}/2')
        budget = Budget(db, user, providerId)
        available = max(0, budget.limit_micros - budget.held_micros - budget.spent_micros)
        percent = round(available / max(1, budget.limit_micros) * 100, 1)
        items.append(dict(provider=providerId, remaining_percent=percent, day=budget.day,
                          resets_at=(datetime.now(beijingZone).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()))
        print(f'[结束] 额度 {providerIndex}/2')
    print('[结束] 两类额度读取')
    return {'items': items}


def CanRun(db, taskId):
    task = db.get(m.Task, taskId)
    print('[开始] 执行任务终态检查')
    if not task or task.status not in {'queued', 'running'}:
        print('[分支] 已结束，交由幂等领取检查')
        print('[结束] 执行任务终态检查')
        return True
    else:
        print('[分支] 检查模型队列')
    print('[结束] 执行任务终态检查')
    charge = db.get(m.Charge, taskId)
    print('[开始] 全站并发检查')
    if charge is None:
        print('[分支] 旧任务无账单，交由原处理器')
        print('[结束] 全站并发检查')
        return True
    else:
        print('[分支] 使用模型队列锁')
    # UPDATE acquires a write lock on SQLite and a row lock on PostgreSQL.
    db.execute(update(m.Provider).where(m.Provider.id == charge.provider_id).values(updated_at=m.now()))
    provider = db.get(m.Provider, charge.provider_id, populate_existing=True)
    running = db.scalar(select(func.count()).select_from(m.Task).join(m.Charge, m.Charge.task_id == m.Task.id).where(
        m.Charge.provider_id == charge.provider_id, m.Task.id != taskId, m.Task.status.in_(['running', 'cancelled']), m.Task.lease_owner.is_not(None)))
    earlier = db.scalar(select(func.count()).select_from(m.Task).join(m.Charge, m.Charge.task_id == m.Task.id).where(
        m.Charge.provider_id == charge.provider_id, m.Task.status == 'queued', or_(m.Charge.created_at < charge.created_at, and_(m.Charge.created_at == charge.created_at, m.Task.id < taskId))))
    print('[结束] 全站并发检查')
    return (provider.enabled or charge.state != 'reserved') and running < provider.concurrency and (earlier < provider.concurrency - running or charge.state != 'reserved')
