from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .. import models as m, schemas as s, services as svc, route_notes as notes
from ..db import get_db
from ..security import current_user, owned, fail

api = APIRouter(prefix='/api/v1', tags=['route-notes'])


class RouteDraft(s.Input):
    baseVersion: int = Field(ge=1)
    trackId: str
    templateId: str
    description: str = Field(min_length=1, max_length=10000)


def Present(project):
    draft = project.route_draft or {}
    print('[开始] 背景草稿展示')
    if draft.get('mode') != 'background-v1':
        print('[分支] 尚无新背景草稿')
        draft = {}
    else:
        print('[分支] 展示当前描述')
        draft = {key: draft[key] for key in ('mode', 'version', 'description', 'trackId', 'templateId')}
    print('[结束] 背景草稿展示')
    return {'projectId': project.id, 'title': project.title, 'projectVersion': project.version, 'draft': draft}


@api.get('/projects/{projectId}/route')
def GetRoute(projectId: str, user=Depends(current_user), db: Session = Depends(get_db)):
    project = owned(db, m.Project, projectId, user)
    tracks = db.scalars(select(m.Track).where(m.Track.project_id == project.id,
        m.Track.user_id == user.id, m.Track.status == 'ended').order_by(m.Track.created_at.desc())).all()
    tasks = db.scalars(select(m.Task).where(m.Task.user_id == user.id, m.Task.deleted == False,
        m.Task.input['project_id'].as_string() == project.id,
        m.Task.input['mode'].as_string() == 'background-v1').order_by(m.Task.created_at.desc()).limit(1)).all()
    return Present(project) | {'tracks': [svc.track_json(db, track) for track in tracks],
                              'latestTask': next(iter([svc.task_json(task) for task in tasks]), None)}


@api.put('/projects/{projectId}/route')
def SaveRoute(projectId: str, data: RouteDraft, user=Depends(current_user), db: Session = Depends(get_db)):
    project = owned(db, m.Project, projectId, user)
    template = db.get(m.Template, data.templateId)
    print('[开始] 背景描述校验')
    if not template or not template.cover_key or not data.description.strip():
        print('[分支] 模板或描述缺失；[结束] 背景描述校验，提前结束')
        fail(422, 'invalid_background', '请选择风格并填写背景描述')
    print('[分支] 模板与描述有效；[结束] 背景描述校验')
    source = notes.Source(db, project, data.trackId, user)
    graph = notes.BuildGraph(source, template)
    graph['description'] = data.description.strip()
    draft = {'mode': 'background-v1', 'version': data.baseVersion + 1, 'graph': graph,
        'description': graph['description'], 'trackId': data.trackId, 'templateId': data.templateId}
    changed = db.execute(update(m.Project).where(m.Project.id == project.id, m.Project.version == data.baseVersion)
        .values(route_draft=draft, version=data.baseVersion + 1, updated_at=m.now()))
    print('[开始] 背景描述并发检查')
    if changed.rowcount != 1:
        print('[分支] 版本冲突；[结束] 背景描述并发检查，提前结束')
        db.rollback()
        fail(409, 'version_conflict', '笔记已更新，请重新打开后再生成')
    print('[分支] 已保存描述，保留原排版；[结束] 背景描述并发检查')
    db.commit()
    db.refresh(project)
    return Present(project)
