from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models as m, schemas as s, services as svc, storage, atlas
from ..security import current_user, owned, fail

api = APIRouter(prefix="/api/v1", tags=["projects"])

@api.get('/projects')
def projects(cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.page(db, select(m.Project).where(m.Project.user_id == user.id, m.Project.deleted == False).order_by(m.Project.updated_at.desc(), m.Project.id), lambda p: svc.project_json(db, p, user), cursor, limit)


@api.post('/projects')
def create_project(data: s.ProjectCreate, user=Depends(current_user), db: Session = Depends(get_db)):
    previousProject = svc.operation_get(db, user, 'manual_design', data.operation_id, m.Project)
    print('[开始] 设计创建去重')
    if previousProject:
        print('[分支] 返回已保存作品；[结束] 设计创建去重，提前结束')
        return svc.project_json(db, previousProject, user)
    print('[分支] 创建新作品；[结束] 设计创建去重')
    project = m.Project(user_id=user.id, title=data.title, layout=svc.empty_layout())
    print('[开始] 手动设计初始化')
    if data.layout is not None:
        print('[分支] 原子保存完整手动设计')
        from ..notebook import Validate
        if data.layout.get('designMode') != 'manual':
            print('[分支] 模式无效；[结束] 手动设计初始化，提前结束')
            fail(422, 'invalid_design_mode', '新设计必须使用手动画板')
        project.layout = {'designMode': 'manual', 'elements': []}
        project.layout, project.asset_ids = Validate(db, data.layout, user, project)
    else:
        print('[分支] 原有观察笔记')
    print('[结束] 手动设计初始化')
    db.add(project)
    svc.operation_add(db, user, 'manual_design', data.operation_id, project)
    db.commit()
    return svc.project_json(db, project, user)


@api.get('/projects/{project_id}')
def project_detail(project_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.project_json(db, owned(db, m.Project, project_id, user), user)


@api.patch('/projects/{project_id}')
def update_project(project_id: str, data: s.ProjectPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    project = owned(db, m.Project, project_id, user)
    values = data.model_dump(exclude_unset=True)
    base_version = values.pop('base_version')
    print('[开始] 手动排版保存检查')
    if data.layout is not None:
        print('[分支] 校验新版背景和排版素材')
        from ..notebook import Validate
        values['layout'], values['asset_ids'] = Validate(db, data.layout, user, project)
    else:
        print('[分支] 更新笔记资料或素材关联')
    print('[结束] 手动排版保存检查')
    if project.version != base_version:
        fail(409, 'version_conflict', '云端已有新版本，请保留本地副本或读取云端版本')
    retainedIds = svc.ProjectAssetIds(project)
    if values.get('asset_ids') is not None:
        svc.assets_access(db, values['asset_ids'], user, retainedIds)
    if values.get('cover_asset_id'):
        svc.asset_access(db, values['cover_asset_id'], user, retainedIds)
    values = {key: value for key, value in values.items() if value is not None or key == 'cover_asset_id'}
    result = db.execute(update(m.Project).where(m.Project.id == project.id, m.Project.version == base_version).values(**values, version=base_version + 1, updated_at=m.now()))
    if result.rowcount != 1:
        db.rollback()
        fail(409, 'version_conflict', '云端已有新版本，请保留本地副本或读取云端版本')
    db.commit()
    db.refresh(project)
    return svc.project_json(db, project, user)


@api.delete('/projects/{project_id}')
def delete_project(project_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    project = owned(db, m.Project, project_id, user)
    recording = db.scalar(select(m.Track).where(m.Track.project_id == project.id, m.Track.status != 'ended'))
    print('[开始] 删除笔记轨迹检查')
    if recording:
        print('[分支] 请先结束正在进行的记录')
        fail(409, 'track_active', '请先结束轨迹记录，再删除笔记')
    else:
        print('[分支] 保留原始轨迹并解除关联')
    print('[结束] 删除笔记轨迹检查')
    atlas.SaveArchive(db, user.id, 'project', project)
    db.execute(update(m.Track).where(m.Track.project_id == project.id).values(project_id=None))
    db.execute(update(m.Node).where(m.Node.project_id == project.id).values(project_id=None))
    db.execute(update(m.Observation).where(m.Observation.project_id == project.id).values(project_id=None))
    project.deleted = True
    db.commit()
    return {'deleted': True}


@api.get('/templates')
def templates(q: str = '', cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.page(db, select(m.Template).where(m.Template.title.contains(q)).order_by(m.Template.id), lambda t: {'id': t.id, 'title': t.title, 'cover_url': storage.url(t.cover_key, preview=True), 'layout': svc.hydrate_layout(db, t.layout, user)}, cursor, limit)


@api.get('/templates/{template_id}')
def template_detail(template_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = db.get(m.Template, template_id)
    if not obj:
        fail(404, 'not_found', '模板不存在')
    return {'id': obj.id, 'title': obj.title, 'cover_url': storage.url(obj.cover_key, preview=True), 'layout': svc.hydrate_layout(db, obj.layout, user)}
