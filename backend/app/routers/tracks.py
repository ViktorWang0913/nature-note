from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models as m, schemas as s, services as svc, atlas
from ..security import current_user, owned, fail
from .shared import check_species

api = APIRouter(prefix="/api/v1", tags=["tracks"])

@api.get('/tracks')
def tracks(cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.page(db, select(m.Track).where(m.Track.user_id == user.id).order_by(m.Track.created_at.desc()), lambda obj: svc.track_json(db, obj), cursor, limit)


@api.post('/tracks')
def create_track(data: s.TrackCreate, user=Depends(current_user), db: Session = Depends(get_db)):
    previous = svc.operation_get(db, user, 'track', data.operation_id, m.Track)
    if previous:
        return svc.track_json(db, previous)
    if data.project_id:
        owned(db, m.Project, data.project_id, user)
    obj = m.Track(user_id=user.id, **data.model_dump(exclude={'operation_id'}))
    db.add(obj)
    svc.operation_add(db, user, 'track', data.operation_id, obj)
    db.commit()
    return svc.track_json(db, obj)


@api.get('/tracks/{track_id}')
def track_detail(track_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.track_json(db, owned(db, m.Track, track_id, user))


@api.patch('/tracks/{track_id}')
def update_track(track_id: str, data: s.TrackPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = owned(db, m.Track, track_id, user)
    if obj.status == 'ended' and data.status != 'ended':
        fail(409, 'track_ended', '已结束的轨迹不可继续，请新建记录')
    obj.status = data.status
    if data.status == 'ended' and not obj.ended_at:
        obj.ended_at = m.now()
    db.commit()
    return svc.track_json(db, obj)


@api.post('/tracks/{track_id}/points')
def append_points(track_id: str, data: s.PointsInput, user=Depends(current_user), db: Session = Depends(get_db)):
    track = owned(db, m.Track, track_id, user)
    added = 0
    for point in data.points:
        existing = db.get(m.TrackPoint, (track.id, point.sequence))
        if existing:
            if any(getattr(existing, key) != value for key, value in point.model_dump().items()):
                fail(409, 'point_conflict', '同一轨迹序号已有不同采样，请保留原记录')
        else:
            db.add(m.TrackPoint(track_id=track.id, **point.model_dump()))
            added += 1
    db.commit()
    return {'accepted': added, 'track_id': track.id}


@api.post('/tracks/{track_id}/nodes')
def create_node(track_id: str, data: s.NodeCreate, user=Depends(current_user), db: Session = Depends(get_db)):
    track = owned(db, m.Track, track_id, user)
    previous = svc.operation_get(db, user, 'node', data.operation_id, m.Node)
    if previous:
        if previous.track_id != track.id:
            fail(409, 'operation_conflict', '该操作已用于另一条轨迹')
        return svc.node_json(previous)
    svc.assets_access(db, data.asset_ids, user)
    check_species(db, data.species_id, user)
    if data.cover_asset_id and data.cover_asset_id not in data.asset_ids:
        fail(422, 'invalid_cover', '封面必须来自该观察点素材')
    values = data.model_dump(exclude_none=True, exclude={'operation_id'})
    obj = m.Node(user_id=user.id, track_id=track.id, project_id=track.project_id, **values)
    db.add(obj)
    svc.operation_add(db, user, 'node', data.operation_id, obj)
    db.commit()
    return svc.node_json(obj)


@api.get('/nodes/{node_id}')
def node_detail(node_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.node_json(owned(db, m.Node, node_id, user))


@api.patch('/nodes/{node_id}')
def update_node(node_id: str, data: s.NodePatch, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = owned(db, m.Node, node_id, user)
    values = data.model_dump(exclude_unset=True)
    if data.asset_ids is not None:
        svc.assets_access(db, data.asset_ids, user)
    check_species(db, data.species_id, user)
    cover = values.get('cover_asset_id', obj.cover_asset_id)
    ids = values.get('asset_ids') if values.get('asset_ids') is not None else obj.asset_ids
    if cover and cover not in ids:
        if 'cover_asset_id' in values:
            fail(422, 'invalid_cover', '封面必须来自该观察点素材')
        values['cover_asset_id'] = ids[0] if ids else None
    for key, value in values.items():
        if value is not None or key in {'cover_asset_id', 'species_id'}:
            setattr(obj, key, value)
    db.commit()
    return svc.node_json(obj)


@api.delete('/nodes/{node_id}')
def delete_node(node_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = owned(db, m.Node, node_id, user)
    db.execute(update(m.Observation).where(m.Observation.user_id == user.id, m.Observation.node_id == obj.id).values(node_id=None))
    atlas.SaveArchive(db, user.id, 'node', obj)
    db.delete(obj)
    db.commit()
    return {'deleted': True, 'assets_preserved': True}
