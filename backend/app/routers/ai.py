from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models as m, schemas as s, services as svc, storage, visual_ai, billing, atlas, retention
from ..security import current_user, owned, fail
from ..jobs import dispatch
from .shared import validate_task_input

api = APIRouter(prefix="/api/v1", tags=["ai"])

@api.get('/sessions')
def sessions(cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.page(db, select(m.GenerationSession).where(m.GenerationSession.user_id == user.id, m.GenerationSession.deleted == False).order_by(m.GenerationSession.created_at.desc()), lambda obj: {'id': obj.id, 'title': obj.title, 'messages': obj.messages, 'created_at': obj.created_at}, cursor, limit)


@api.post('/sessions')
def create_session(data: s.ProjectCreate, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = m.GenerationSession(user_id=user.id, title=data.title)
    db.add(obj)
    db.commit()
    return {'id': obj.id, 'title': obj.title, 'messages': obj.messages, 'created_at': obj.created_at}


@api.get('/sessions/{session_id}')
def session_detail(session_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = owned(db, m.GenerationSession, session_id, user)
    messages = []
    print('[开始] 创作历史消息读取')
    for messageIndex, message in enumerate(obj.messages, 1):
        print(f'[开始] 历史消息 {messageIndex}/{len(obj.messages)}')
        result = dict(message)
        task = db.get(m.Task, message.get('task_id')) if message.get('task_id') else None
        print('[开始] 历史任务归属')
        if task and task.user_id == user.id:
            print('[分支] 当前用户任务')
            result['task'] = svc.task_json(task)
        else:
            print('[分支] 无可用任务')
        print('[结束] 历史任务归属')
        assetId = message.get('asset_id')
        asset = db.get(m.Asset, assetId) if assetId else None
        print('[开始] 历史参考图访问')
        if asset and not asset.deleted and asset.user_id in (None, user.id):
            print('[分支] 返回用户可访问的参考图')
            result['asset_url'] = storage.url(asset.key, 'asset', asset.id)
        else:
            print('[分支] 无参考图或素材不可访问')
        print('[结束] 历史参考图访问')
        messages.append(result)
        print(f'[结束] 历史消息 {messageIndex}/{len(obj.messages)}')
    print('[结束] 创作历史消息读取')
    return {'id': obj.id, 'title': obj.title, 'messages': messages, 'created_at': obj.created_at}


@api.post('/tasks')
def create_task(data: s.TaskCreate, background: BackgroundTasks, user=Depends(current_user), db: Session = Depends(get_db)):
    previous = svc.operation_get(db, user, 'task', data.operation_id, m.Task)
    if previous:
        return svc.task_json(previous)
    validate_task_input(db, data, user)
    obj = m.Task(user_id=user.id, kind=data.kind, input=data.input, is_mock=False)
    db.add(obj)
    db.flush()
    billing.Reserve(db, user, obj)
    print('[开始] 对话用户消息保存')
    if data.kind == 'rag':
        print('[分支] 保存千问图文问题')
        db.add(m.ChatMessage(user_id=user.id, session_id=data.input['chat_session_id'], task_id=obj.id,
                            role='user', text=data.input.get('question', ''), asset_id=data.input.get('asset_id')))
    else:
        print('[分支] 图片任务沿用生图会话')
    print('[结束] 对话用户消息保存')
    if data.input.get('session_id'):
        session = owned(db, m.GenerationSession, data.input['session_id'], user)
        session.messages = session.messages + [{'id': m.uid(), 'role': 'user', 'text': data.input.get('prompt', ''), 'asset_id': data.input.get('asset_id'), 'task_id': obj.id, 'created_at': m.now()}]
    svc.operation_add(db, user, 'task', data.operation_id, obj)
    db.commit()
    dispatch(obj.id, background)
    db.refresh(obj)
    return svc.task_json(obj)


@api.get('/tasks/{task_id}')
def task_detail(task_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    task = owned(db, m.Task, task_id, user)
    charge = db.get(m.Charge, task.id)
    ahead = 0
    print('[开始] 排队位置查询')
    if charge and task.status == 'queued':
        print('[分支] 查询同一模型前方待执行任务')
        ahead = db.scalar(select(func.count()).select_from(m.Task).join(m.Charge, m.Charge.task_id == m.Task.id).where(
            m.Charge.provider_id == charge.provider_id, m.Task.id != task.id,
            or_(and_(m.Task.status.in_(['running', 'cancelled']), m.Task.lease_until > m.now()),
                and_(m.Task.status == 'queued', or_(m.Charge.created_at < charge.created_at, and_(m.Charge.created_at == charge.created_at, m.Task.id < task.id))))))
    else:
        print('[分支] 当前不在队列中')
    print('[结束] 排队位置查询')
    return svc.task_json(task) | {'queue_ahead': ahead}


@api.post('/tasks/{task_id}/cancel')
def cancel_task(task_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = owned(db, m.Task, task_id, user)
    if obj.status in {'queued', 'running'}:
        obj.status = 'cancelled'
        obj.updated_at = m.now()
        billing.Abort(db, obj.id)
        db.commit()
    return svc.task_json(obj)


@api.delete('/tasks/{taskId}')
def DeleteNotebookHistory(taskId: str, user=Depends(current_user), db: Session = Depends(get_db)):
    task = owned(db, m.Task, taskId, user)
    print('[开始] 笔记历史删除资格')
    if task.kind not in {'image_polish', 'route_summary'}:
        print('[分支] 其他任务随所属会话管理')
        print('[结束] 笔记历史删除资格；提前拒绝')
        fail(409, 'session_required', '请在所属会话中删除此记录')
    elif task.status in {'queued', 'running'}:
        print('[分支] 先完成或停止生成')
        print('[结束] 笔记历史删除资格；提前拒绝')
        fail(409, 'task_active', '请先完成或停止生成，再删除记录')
    else:
        print('[分支] 归档历史，保留原始观察和已另存图片')
    print('[结束] 笔记历史删除资格')
    atlas.SaveArchive(db, user.id, 'task', task)
    task.deleted = True
    db.commit()
    return {'deleted': True, 'saved_assets_preserved': True}


@api.post('/tasks/{task_id}/retry')
def retry_task(task_id: str, background: BackgroundTasks, user=Depends(current_user), db: Session = Depends(get_db)):
    previous = owned(db, m.Task, task_id, user)
    print(f'[开始] 重试任务类型检查 {task_id}')
    if previous.kind not in s.taskKinds:
        print('[分支] 功能已移除')
        print(f'[结束] 重试任务类型检查 {task_id}；提前拒绝重试')
        fail(410, 'task_kind_removed', '该功能已移除，无法重试')
    else:
        print('[分支] 当前支持的任务类型')
    print(f'[结束] 重试任务类型检查 {task_id}')
    if previous.status in {'queued', 'running'}:
        fail(409, 'task_active', '任务尚未结束')
    data = s.TaskCreate(kind=previous.kind, input=previous.input)
    validate_task_input(db, data, user)
    obj = m.Task(user_id=user.id, kind=previous.kind, input=data.input, attempt=previous.attempt + 1, is_mock=previous.kind not in visual_ai.KINDS)
    db.add(obj)
    db.flush()
    billing.Reserve(db, user, obj)
    print('[开始] 重试问答保存')
    if previous.kind == 'rag':
        print('[分支] 将重试作为新问题保存')
        db.add(m.ChatMessage(user_id=user.id, session_id=previous.input['chat_session_id'], task_id=obj.id,
                            role='user', text=previous.input.get('question', ''), asset_id=previous.input.get('asset_id')))
    else:
        print('[分支] 生图任务')
    print('[结束] 重试问答保存')
    db.commit()
    dispatch(obj.id, background)
    return svc.task_json(obj)


@api.post('/tasks/{task_id}/save')
def save_task(task_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = owned(db, m.Task, task_id, user)
    # Lock the task while assigning its one saved asset in PostgreSQL.
    obj = db.scalar(select(m.Task).where(m.Task.id == obj.id).with_for_update())
    if obj.saved_asset_id:
        return svc.asset_json(db, db.get(m.Asset, obj.saved_asset_id), user)
    if obj.kind not in {'image_generation', 'image_polish'} or obj.status != 'succeeded':
        fail(409, 'result_unavailable', '当前任务没有可保存的生成图片')
    source = db.get(m.Asset, obj.input['asset_id']) if obj.input.get('asset_id') else None
    project = db.get(m.Project, obj.input['project_id']) if obj.kind == 'image_polish' else None
    stored = storage.store_image(storage.read(obj.result['image_key']), keep_original=False)
    title = project.title + ' · AI 润色' if project else source.title + ' · AI 生图' if source else str(obj.input.get('prompt') or 'AI 生图')[:80]
    asset = m.Asset(user_id=user.id, title=title, category=source.category if source else 'environment', source='generated', original_asset_id=source.id if source else None, is_mock=obj.is_mock, history=[{'task_id': obj.id, 'model': obj.result.get('model'), 'reference_group_version': obj.result.get('reference_group_version'), 'parameters': obj.input}], **stored)
    print('[开始] 笔记背景归类')
    if obj.input.get('mode') == 'background-v1':
        print('[分支] 独立背景，不进入单图素材库')
        asset.source = 'notebook_background'
        asset.title = project.title + ' · 背景'
    else:
        print('[分支] 单图生成素材')
    print('[结束] 笔记背景归类')
    db.add(asset)
    db.flush()
    obj.saved_asset_id = asset.id
    print('[开始] 轨迹笔记成图封面更新')
    if project and not project.deleted and obj.input.get('mode') != 'background-v1':
        print('[分支] 最新保存成图作为笔记封面，历史任务保留')
        project.cover_asset_id = asset.id
        project.asset_ids = list(set(project.asset_ids) | {asset.id})
        project.version += 1
    else:
        print('[分支] 独立素材沿用原保存方式')
    print('[结束] 轨迹笔记成图封面更新')
    db.commit()
    return svc.asset_json(db, asset, user)


@api.post('/tasks/{task_id}/reference')
def ContinueImage(task_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    task = owned(db, m.Task, task_id, user)
    print('[开始] 改图参考结果检查')
    if task.kind not in {'image_generation', 'image_polish'} or task.status != 'succeeded' or not (task.result or {}).get('image_key'):
        print('[分支] 没有可用成图')
        fail(409, 'result_unavailable', '请等待图片生成完成')
    else:
        print('[分支] 使用已生成结果，不调用模型')
    print('[结束] 改图参考结果检查')
    referenceId = 'reference-' + task.id
    asset = db.get(m.Asset, referenceId)
    print('[开始] 参考素材幂等创建')
    if asset is None:
        print('[分支] 创建隐藏参考素材')
        imageKey = task.result['image_key']
        picture = storage.image_bytes(storage.read(imageKey))
        asset = m.Asset(id=referenceId, user_id=user.id, title='改图参考', source='ai_reference', category='unclassified',
            original_asset_id=task.input.get('asset_id'),
            key=imageKey, original_key=imageKey, thumbnail_key=imageKey, width=picture.width, height=picture.height)
        db.add(asset)
        db.commit()
    else:
        print('[分支] 复用已保存参考')
        # Backfill provenance for references created before the cutout contract.
        asset.original_asset_id = task.input.get('asset_id')
        db.commit()
    print('[结束] 参考素材幂等创建')
    return svc.asset_json(db, asset, user)


@api.patch('/sessions/{session_id}')
def RenameGenerationSession(session_id: str, data: s.ProjectCreate, user=Depends(current_user), db: Session = Depends(get_db)):
    session = owned(db, m.GenerationSession, session_id, user)
    session.title = data.title
    db.commit()
    return {'id':session.id, 'title':session.title}


@api.delete('/sessions/{session_id}')
def DeleteGenerationSession(session_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    session = owned(db, m.GenerationSession, session_id, user)
    atlas.SaveArchive(db, user.id, 'generation_session', session)
    taskIds = {message.get('task_id') for message in session.messages if message.get('task_id')}
    tasks = list(db.scalars(select(m.Task).where(m.Task.id.in_(taskIds), m.Task.user_id == user.id)))
    print(f'[开始] 生图会话结果归档，共 {len(tasks)} 条')
    for taskIndex, task in enumerate(tasks, 1):
        print(f'[开始] 会话任务 {taskIndex}/{len(tasks)}')
        print('[开始] 执行中任务检查')
        if task.status in {'queued', 'running'}:
            print('[分支] 等待结束或先取消')
            fail(409, 'task_active', '请先完成或取消会话中的任务')
        else:
            print('[分支] 归档历史结果，保留独立素材')
        print('[结束] 执行中任务检查')
        atlas.SaveArchive(db, user.id, 'task', task)
        task.deleted = True
        print(f'[结束] 会话任务 {taskIndex}/{len(tasks)}')
    print('[结束] 生图会话结果归档')
    session.deleted = True
    db.flush()
    retainedIds = retention.RetainedAssetIds(db)
    print(f'[开始] 会话临时参考清理，共 {len(tasks)} 条')
    for taskIndex, task in enumerate(tasks,1):
        print(f'[开始] 临时参考 {taskIndex}/{len(tasks)}')
        reference = db.get(m.Asset,'reference-'+task.id)
        print('[开始] 临时参考保留检查')
        if reference and reference.id not in retainedIds:
            print('[分支] 未被其他笔记或会话使用，撤销访问')
            atlas.SaveArchive(db,user.id,'asset',reference)
            reference.deleted = True
        else:
            print('[分支] 已被独立引用或未创建临时素材')
        print('[结束] 临时参考保留检查')
        print(f'[结束] 临时参考 {taskIndex}/{len(tasks)}')
    print('[结束] 会话临时参考清理')
    db.commit()
    return {'deleted':True, 'saved_assets_preserved':True}
