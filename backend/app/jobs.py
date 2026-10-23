import asyncio
import math
from datetime import datetime, timedelta, timezone
from celery import Celery
from sqlalchemy import select, update, or_, and_, case
from .config import settings
from .db import SessionLocal
from . import models as m, schemas as s, services as svc, visual_ai, billing, chat

celery_app = Celery('nature_note', broker=settings().redis_url, backend=settings().redis_url)
celery_app.conf.update(
    task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
    task_track_started=True, task_serializer='json', accept_content=['json'], result_serializer='json',
    broker_connection_retry_on_startup=True, task_soft_time_limit=780, task_time_limit=840,
    broker_transport_options={'visibility_timeout': 600},
    beat_schedule={'recover-expired-tasks': {'task': 'nature_note.recover', 'schedule': 60.0}},
)
LEASE_SECONDS = 300
VISUAL_LEASE_SECONDS = 900


def claim_task(db, task_id):
    """Atomic lease prevents duplicate deliveries from running concurrently."""
    current = datetime.now(timezone.utc)
    owner = m.uid()
    task = db.get(m.Task, task_id)
    if not task:
        return None, None, 0
    lease_seconds = VISUAL_LEASE_SECONDS if task.kind in visual_ai.KINDS or task.kind == 'rag' else LEASE_SECONDS
    acquired = db.execute(update(m.Task).where(
        m.Task.id == task_id,
        or_(m.Task.status == 'queued', and_(m.Task.status == 'running', or_(m.Task.lease_until.is_(None), m.Task.lease_until <= current.isoformat())), and_(m.Task.status == 'cancelled', m.Task.lease_owner.is_not(None), m.Task.lease_until <= current.isoformat())),
    ).values(status=case((m.Task.status == 'cancelled', 'cancelled'), else_='running'), lease_owner=owner, lease_until=(current + timedelta(seconds=lease_seconds)).isoformat(), updated_at=current.isoformat()))
    db.commit()
    task = db.get(m.Task, task_id)
    if acquired.rowcount == 1:
        db.refresh(task)
        return owner, task, 0
    if task and task.status == 'running':
        wait = math.ceil((datetime.fromisoformat(task.lease_until) - current).total_seconds()) if task.lease_until else 1
        return None, task, max(1, min(wait + 1, lease_seconds + 1))
    return None, task, 0


def run_task(task_id):
    """Return a retry delay when another delivery still owns the task."""
    with SessionLocal() as db:
        print(f'[开始] 执行排队许可 {task_id}')
        if not billing.CanRun(db, task_id):
            print('[分支] 继续等待模型队列')
            db.rollback()
            print(f'[结束] 执行排队许可 {task_id}；提前返回排队等待')
            return 3
        else:
            print('[分支] 可尝试领取任务')
        print(f'[结束] 执行排队许可 {task_id}')
        owner, task, retry_after = claim_task(db, task_id)
        if not owner:
            return retry_after
        print(f'[开始] 任务类型检查 {task_id}')
        if task.kind not in s.taskKinds:
            print('[分支] 已移除或不支持的任务类型')
            db.execute(update(m.Task).where(m.Task.id == task_id, m.Task.status == 'running', m.Task.lease_owner == owner).values(
                status='failed', error={'code': 'task_kind_removed', 'message': '该功能已移除，任务无法继续执行'},
                lease_owner=None, lease_until=None, updated_at=m.now()))
            db.commit()
            print(f'[结束] 任务类型检查 {task_id}；提前结束当前任务')
            return 0
        else:
            print('[分支] 当前支持的任务类型')
        print(f'[结束] 任务类型检查 {task_id}')
        try:
            user = db.get(m.User, task.user_id)
            print('[开始] 执行前账号状态检查')
            remoteResume = task.kind in {'image_generation', 'image_polish'} and bool((task.result or {}).get('_upstream_task_id'))
            if not user or ((not user.active or user.deleted_at) and not remoteResume):
                print('[分支] 账号已停用，不提交新请求')
                raise RuntimeError('账号已暂停使用，任务未提交')
            else:
                print('[分支] 账号有效')
            print('[结束] 执行前账号状态检查')
            print(f'[开始] 任务执行分派 {task_id}')
            if remoteResume:
                print('[分支] 只查询已提交的生图任务，不重新发送图片')
                result = visual_ai.GenerateImage(db, task, '', [])
            elif task.kind in visual_ai.KINDS:
                print('[分支] 图片模型任务')
                result = visual_ai.execute(db, task, user)
            else:
                print('[分支] 知识问答任务')
                result = chat.Execute(db, task, user)
            print(f'[结束] 任务执行分派 {task_id}')
            written = db.execute(update(m.Task).where(m.Task.id == task_id, m.Task.status == 'running', m.Task.lease_owner == owner).values(
                result=result, is_mock=result.get('is_mock', task.kind not in visual_ai.KINDS), status='succeeded', error=None, lease_owner=None, lease_until=None, updated_at=m.now()))
            if written.rowcount != 1:
                db.rollback()
                print('[开始] 已取消任务费用核对')
                currentTask = db.get(m.Task, task_id, populate_existing=True)
                if currentTask.status == 'cancelled' and currentTask.lease_owner == owner:
                    print('[分支] 保存已发生费用并释放执行位置')
                    billing.Finalize(db, task_id, result.get('_actual_micros'), result.get('usage'))
                    currentTask.result = result
                    currentTask.lease_owner, currentTask.lease_until = None, None
                    db.commit()
                else:
                    print('[分支] 执行租约已被接管，保留新执行器状态')
                print('[结束] 已取消任务费用核对')
                return 0
            billing.Finalize(db, task_id, result.get('_actual_micros'), result.get('usage'), result.get('_billing_evidence', ''))
            svc.notify(db, task.user_id, task.user_id, 'ai', 'task', task.id, '你的 AI 任务已完成，可以查看结果')
            session_id = task.input.get('session_id')
            if session_id:
                session = db.get(m.GenerationSession, session_id)
                if session and session.user_id == task.user_id and not any(message.get('role') == 'assistant' and message.get('task_id') == task_id for message in session.messages):
                    session.messages = session.messages + [{'id': m.uid(), 'role': 'assistant', 'text': result.get('text', ''), 'task_id': task.id, 'is_mock': result.get('is_mock', task.kind not in visual_ai.KINDS), 'created_at': m.now()}]
            db.commit()
        except Exception as exc:
            db.rollback()
            print('[开始] 上游余额不足保护')
            if isinstance(exc, visual_ai.ProviderBalanceEmpty):
                print('[分支] 暂停对应模型并释放未提交的排队任务')
                from .routers.admin import CancelQueued
                providerId = billing.ProviderId(task.kind)
                db.execute(update(m.Provider).where(m.Provider.id == providerId).values(enabled=False, message='该 AI 服务暂时不可用，请稍后再试'))
                CancelQueued(db, providerId=providerId)
            else:
                print('[分支] 普通失败，不暂停其他模型')
            print('[结束] 上游余额不足保护')
            currentTask = db.get(m.Task, task_id, populate_existing=True)
            print('[开始] 失败处理租约检查')
            if currentTask.lease_owner != owner:
                print('[分支] 租约已转移，原执行器不修改费用与状态')
                db.rollback()
                print('[结束] 失败处理租约检查；提前退出')
                return 0
            else:
                print('[分支] 当前执行器处理失败')
            print('[结束] 失败处理租约检查')
            print('[开始] 生图查询恢复检查')
            if isinstance(exc, visual_ai.ImageQueryPending) and (currentTask.result or {}).get('_upstream_task_id'):
                print('[分支] 保留原任务、费用及执行位置，稍后只读查询')
                checkpoint = dict(currentTask.result)
                queryRetries = int(checkpoint.get('_query_retries', 0)) + 1
                retryDelay = min(30 * 2 ** min(queryRetries - 1, 4), 300)
                checkpoint['_query_retries'] = queryRetries
                currentTask.result = checkpoint
                currentTask.error = {'code': 'image_query_pending', 'message': str(exc)}
                currentTask.lease_until = (datetime.now(timezone.utc) + timedelta(seconds=retryDelay)).isoformat()
                currentTask.updated_at = m.now()
                db.commit()
                print('[结束] 生图查询恢复检查；提前交还调度器')
                return retryDelay
            else:
                print('[分支] 明确失败或无可查询任务，沿用原失败处理')
            print('[结束] 生图查询恢复检查')
            billing.Abort(db, task_id)
            db.execute(update(m.ChatMessage).where(m.ChatMessage.task_id == task_id, m.ChatMessage.status == 'streaming').values(
                status='stopped' if currentTask.status == 'cancelled' else 'failed'))
            db.execute(update(m.Task).where(m.Task.id == task_id, m.Task.status == 'running', m.Task.lease_owner == owner).values(
                status='failed', error={'code': 'ai_not_configured' if isinstance(exc, visual_ai.VisualAPIUnavailable) else 'task_failed', 'message': str(exc)[:300]},
                lease_owner=None, lease_until=None, updated_at=m.now()))
            billing.Finalize(db, task_id)
            db.execute(update(m.Task).where(m.Task.id == task_id, m.Task.lease_owner == owner).values(lease_owner=None, lease_until=None))
            db.commit()
        return 0


@celery_app.task(name='nature_note.run', bind=True, acks_late=True, reject_on_worker_lost=True, max_retries=None)
def celery_run(self, task_id):
    retry_after = run_task(task_id)
    if retry_after:
        raise self.retry(countdown=retry_after)


def recoverable_task_ids():
    with SessionLocal() as db:
        return list(db.scalars(select(m.Task.id).where(or_(
            m.Task.status == 'queued',
            and_(m.Task.status == 'running', or_(m.Task.lease_until.is_(None), m.Task.lease_until <= m.now())),
            and_(m.Task.status == 'cancelled', m.Task.lease_owner.is_not(None), m.Task.lease_until <= m.now()),
        )).order_by(m.Task.created_at, m.Task.id).limit(100)))


@celery_app.task(name='nature_note.recover')
def recover_tasks():
    MaintainData()
    ids = recoverable_task_ids()
    for task_id in ids:
        celery_run.delay(task_id)
    return len(ids)


async def development_recovery_loop():
    """Restart-safe development queue; production recovery is owned by Celery beat."""
    cycleIndex = 0
    print('[开始] 本地任务恢复循环')
    while True:
        cycleIndex += 1
        print(f'[开始] 恢复轮次 {cycleIndex}')
        taskIds = await asyncio.to_thread(recoverable_task_ids)
        # Each delivery still acquires the provider gate and atomic task lease.
        await asyncio.gather(*map(RunRecovered, taskIds))
        print('[开始] 定期维护检查')
        if cycleIndex % 20 == 1:
            print('[分支] 执行周期维护')
            await asyncio.to_thread(MaintainData)
        else:
            print('[分支] 等待下个维护周期')
        print('[结束] 定期维护检查')
        print(f'[结束] 恢复轮次 {cycleIndex}')
        await asyncio.sleep(3)


async def RunRecovered(taskId):
    print(f'[开始] 并行恢复任务 {taskId}')
    await asyncio.to_thread(run_task, taskId)
    print(f'[结束] 并行恢复任务 {taskId}')


async def RunInline(taskId):
    retryDelay = 1
    attemptIndex = 0
    print(f'[开始] 本地任务调度 {taskId}')
    while retryDelay:
        attemptIndex += 1
        print(f'[开始] 调度 {taskId} 第 {attemptIndex} 次')
        retryDelay = await asyncio.to_thread(run_task, taskId)
        print('[开始] 队列等待检查')
        if retryDelay:
            print('[分支] 等待原任务执行许可或结果查询，不创建新任务')
            await asyncio.sleep(retryDelay)
        else:
            print('[分支] 本次任务已结束')
        print('[结束] 队列等待检查')
        print(f'[结束] 调度 {taskId} 第 {attemptIndex} 次')
    print(f'[结束] 本地任务调度 {taskId}')


def dispatch(task_id, background):
    if settings().queue_backend == 'inline':
        background.add_task(RunInline, task_id)
    else:
        try:
            celery_run.delay(task_id)
        except Exception:
            with SessionLocal() as db:
                task = db.get(m.Task, task_id)
                task.status = 'failed'
                task.error = {'code': 'queue_unavailable', 'message': '任务队列暂时不可用，请重试'}
                billing.Abort(db, task.id)
                db.commit()


def MaintainData():
    from .lifecycle import CleanupPending
    from .retention import ExpireArchives
    from .moderation import Recover
    with SessionLocal() as db:
        CleanupPending(db)
        ExpireArchives(db)
    Recover()
