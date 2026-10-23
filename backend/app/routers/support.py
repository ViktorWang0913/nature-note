from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select, update
from .. import models as m, services as svc, atlas
from ..db import get_db
from ..security import current_user, SessionUser, owned, fail
from ..schemas import Input
from .admin import Serialize

api = APIRouter(prefix='/api/v1', tags=['support'])


class FeedbackInput(Input):
    category: str = Field(pattern='^(account|ai|quota|notes|other)$')
    text: str = Field(min_length=1, max_length=5000)
    asset_ids: list[str] = Field(default_factory=list, max_length=3)
    task_id: str | None = None


class ReplyInput(Input):
    text: str = Field(min_length=1, max_length=5000)


class Decision(Input):
    accept: bool


@api.get('/announcements')
def Announcements(user=Depends(current_user), db=Depends(get_db)):
    items = db.scalars(select(m.Announcement).where(m.Announcement.status == 'published',
        m.Announcement.starts_at <= m.now(), m.Announcement.ends_at > m.now()).order_by(m.Announcement.created_at.desc()))
    return {'items': [Serialize(item) for item in items if not item.user_ids or user.id in item.user_ids]}


@api.get('/feedback')
def FeedbackList(user=Depends(SessionUser), db=Depends(get_db)):
    return {'items': [Serialize(item) for item in db.scalars(select(m.Feedback).where(m.Feedback.user_id == user.id).order_by(m.Feedback.created_at.desc()).limit(100))]}


@api.post('/feedback')
def CreateFeedback(data: FeedbackInput, user=Depends(SessionUser), db=Depends(get_db)):
    print('[开始] 停用账号申诉范围检查')
    if not user.active and (data.category != 'account' or data.asset_ids or data.task_id):
        print('[分支] 仅接受纯文字账号申诉')
        fail(403, 'appeal_only', '停用期间仅可提交文字账号申诉')
    else:
        print('[分支] 允许本次反馈')
    print('[结束] 停用账号申诉范围检查')
    svc.assets_access(db, data.asset_ids, user)
    print('[开始] 反馈任务归属检查')
    if data.task_id:
        print('[分支] 检查关联任务')
        owned(db, m.Task, data.task_id, user)
    else:
        print('[分支] 无关联任务')
    print('[结束] 反馈任务归属检查')
    item = m.Feedback(user_id=user.id, **data.model_dump())
    db.add(item)
    db.commit()
    return Serialize(item)


@api.post('/feedback/{feedback_id}/reply')
def Reply(feedback_id: str, data: ReplyInput, user=Depends(SessionUser), db=Depends(get_db)):
    item = owned(db, m.Feedback, feedback_id, user)
    item.replies = item.replies + [{'role': 'user', 'text': data.text, 'created_at': m.now()}]
    item.status = 'open'
    db.commit()
    return Serialize(item)


@api.get('/corrections')
def Corrections(user=Depends(current_user), db=Depends(get_db)):
    return {'items': [Serialize(item) for item in db.scalars(select(m.Correction).where(m.Correction.user_id == user.id).order_by(m.Correction.created_at.desc()))]}


@api.post('/corrections/{correction_id}')
def DecideCorrection(correction_id: str, data: Decision, user=Depends(current_user), db=Depends(get_db)):
    item = owned(db, m.Correction, correction_id, user)
    print('[开始] 更正建议幂等检查')
    if item.status != 'pending':
        print('[分支] 已处理，直接返回')
        print('[结束] 更正建议幂等检查；提前结束')
        return Serialize(item)
    else:
        print('[分支] 接受用户决定')
    print('[结束] 更正建议幂等检查')
    print('[开始] 用户更正选择')
    if data.accept:
        print('[分支] 用户接受，更改个人归类')
        target = atlas.ResolveSpecies(db, user, name=item.name, scientificName=item.scientific_name)
        db.execute(update(m.Observation).where(m.Observation.user_id == user.id, m.Observation.species_id == item.species_id,
            m.Observation.deleted == False).values(species_id=target.id, confirmed_by='user'))
        item.status = 'accepted'
    else:
        print('[分支] 保留用户原判断')
        item.status = 'declined'
    print('[结束] 用户更正选择')
    db.commit()
    return Serialize(item)
