from datetime import datetime, timedelta, timezone
from ..config import settings
from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select, inspect

from .. import models as m, services as svc, chat, atlas, billing, storage
from ..db import get_db
from ..security import current_user, owned
from ..schemas import Input

api = APIRouter(prefix='/api/v1/chats', tags=['chat'])


class SessionInput(Input):
    title: str = Field(default='问问自然记', min_length=1, max_length=200)


class ContextInput(Input):
    text: str = Field(default='', max_length=50000)
    asset_id: str | None = None


@api.get('')
def Sessions(cursor: str | None = None, user=Depends(current_user), db=Depends(get_db)):
    return svc.page(db, select(m.ChatSession).where(m.ChatSession.user_id == user.id, m.ChatSession.deleted == False).order_by(m.ChatSession.created_at.desc()),
        lambda item: {'id': item.id, 'title': item.title, 'created_at': item.created_at}, cursor)


@api.post('')
def Create(data: SessionInput, user=Depends(current_user), db=Depends(get_db)):
    item = m.ChatSession(user_id=user.id, title=data.title)
    db.add(item)
    db.commit()
    return {'id': item.id, 'title': item.title}


@api.get('/{session_id}')
def Detail(session_id: str, user=Depends(current_user), db=Depends(get_db)):
    session = owned(db, m.ChatSession, session_id, user)
    messages = db.scalars(select(m.ChatMessage).where(m.ChatMessage.session_id == session.id).order_by(m.ChatMessage.created_at, m.ChatMessage.id))
    return {'id': session.id, 'title': session.title, 'context': chat.Context(db, session),
        'messages': [{'id': item.id, 'role': item.role, 'text': item.text, 'asset_id': item.asset_id,
                      'task_id': item.task_id, 'status': item.status, 'created_at': item.created_at,
                      'asset_url':storage.url(db.get(m.Asset,item.asset_id).key, 'chat', session.id) if item.asset_id and db.get(m.Asset,item.asset_id) else None} for item in messages]}


@api.post('/{session_id}/context')
def Context(session_id: str, data: ContextInput, user=Depends(current_user), db=Depends(get_db)):
    session = owned(db, m.ChatSession, session_id, user)
    print('[开始] 输入图片权限检查')
    if data.asset_id:
        print('[分支] 验证本人可访问素材')
        svc.asset_access(db, data.asset_id, user)
    else:
        print('[分支] 纯文字估算')
    print('[结束] 输入图片权限检查')
    return chat.Context(db, session, data.text, data.asset_id)


@api.patch('/{session_id}')
def Rename(session_id: str, data: SessionInput, user=Depends(current_user), db=Depends(get_db)):
    session = owned(db, m.ChatSession, session_id, user)
    session.title = data.title
    db.commit()
    return {'id': session.id, 'title': session.title}


@api.delete('/{session_id}')
def Delete(session_id: str, user=Depends(current_user), db=Depends(get_db)):
    session = owned(db, m.ChatSession, session_id, user)
    atlas.SaveArchive(db, user.id, 'chat', session)
    messages = list(db.scalars(select(m.ChatMessage).where(m.ChatMessage.session_id == session.id)))
    snapshot = {'messages': [{column.key:getattr(message,column.key) for column in inspect(m.ChatMessage).columns} for message in messages]}
    db.add(m.Archive(user_id=user.id, resource_type='chat_messages', resource_id=session.id,
        snapshot=snapshot, reason='用户删除会话', expires_at=(datetime.now(timezone.utc)+timedelta(days=settings().archive_retention_days)).isoformat()))

    taskIds = select(m.ChatMessage.task_id).where(m.ChatMessage.session_id == session.id)
    tasks = list(db.scalars(select(m.Task).where(m.Task.id.in_(taskIds))))
    print(f'[开始] 删除会话停止任务，共 {len(tasks)} 条')
    for taskIndex, task in enumerate(tasks, 1):
        print(f'[开始] 停止会话任务 {taskIndex}/{len(tasks)}')
        atlas.SaveArchive(db,user.id,'task',task)
        task.deleted = True
        print('[开始] 会话任务停止状态检查')
        if task.status in {'queued','running'}:
            print('[分支] 停止当前会话任务')
            task.status = 'cancelled'
            billing.Abort(db,task.id)
        else:
            print('[分支] 保留已经结束的任务账单')
        print('[结束] 会话任务停止状态检查')
        print(f'[结束] 停止会话任务 {taskIndex}/{len(tasks)}')
    print('[结束] 删除会话停止任务')
    session.deleted = True
    db.commit()
    return {'deleted': True}
