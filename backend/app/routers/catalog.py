from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models as m, schemas as s, services as svc, atlas
from ..security import current_user, owned, fail
from .shared import check_species
from pydantic import Field

api = APIRouter(prefix="/api/v1", tags=["catalog"])


class PhotoBatch(s.Input):
    asset_ids: list[str] = Field(min_length=1, max_length=9)


@api.post('/species/{species_id}/photos')
def AddSpeciesPhotos(species_id: str, data: PhotoBatch, user=Depends(current_user), db: Session = Depends(get_db)):
    owned(db, m.Species, species_id, user)
    assetIds = list(dict.fromkeys(data.asset_ids))
    records = []
    print(f'[开始] 手动批量归档，共 {len(assetIds)} 张')
    for photoIndex, assetId in enumerate(assetIds, 1):
        print(f'[开始] 手动归档 {photoIndex}/{len(assetIds)}')
        existing = db.scalar(select(m.Observation).where(m.Observation.user_id == user.id, m.Observation.asset_id == assetId))
        values = {'asset_id':assetId, 'species_id':species_id}
        print('[开始] 原观察信息保留检查')
        if existing:
            print('[分支] 保留原拍摄时间、备注和位置')
            values.update({key:getattr(existing,key) for key in ('text','observed_at','latitude','longitude','project_id','node_id')})
        else:
            print('[分支] 新照片归档')
        print('[结束] 原观察信息保留检查')
        records.append(atlas.ConfirmPhoto(db, user, s.ObservationCreate(**values)))
        print(f'[结束] 手动归档 {photoIndex}/{len(assetIds)}')
    print('[结束] 手动批量归档')
    db.commit()
    return {'items':[svc.observation_json(db, record, user) for record in records]}

@api.get('/species')
@api.get('/atlas')
def species_list(q: str = '', sort: str = 'category', cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    items = [svc.species_json(db, sp, user) for sp in db.scalars(select(m.Species).where(m.Species.user_id == user.id, m.Species.id.in_(select(m.Observation.species_id).join(m.Asset, m.Asset.id == m.Observation.asset_id).where(m.Observation.user_id == user.id, m.Observation.deleted == False, m.Observation.confirmation == 'confirmed', m.Asset.deleted == False))).order_by(m.Species.id)) if not q or q.casefold() in (sp.name + sp.scientific_name + ''.join(sp.aliases)).casefold()]
    if sort == 'count':
        items.sort(key=lambda item: (-item['photo_count'], item['name']))
    elif sort == 'rarity':
        order = {'常见': 0, '少见': 1, '罕见': 2, '未标注': 3}
        items.sort(key=lambda item: (order.get(item['rarity'], 3), item['name']))
    else:
        items.sort(key=lambda item: (item['category'], item['name']))
    import base64
    try:
        offset = int(base64.urlsafe_b64decode(cursor).decode()) if cursor else 0
        if offset < 0:
            raise ValueError()
    except Exception:
        fail(422, 'invalid_cursor', '分页参数无效')
    limit = min(max(limit, 1), 100)
    return {'items': items[offset:offset + limit], 'next_cursor': base64.urlsafe_b64encode(str(offset + limit).encode()).decode() if offset + limit < len(items) else None}


@api.get('/species/{species_id}')
def species_detail(species_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = owned(db, m.Species, species_id, user)
    if not obj:
        fail(404, 'not_found', '物种不存在')
    return svc.species_json(db, obj, user, include_photos=True)


@api.get('/observations')
def observations(species_id: str | None = None, project_id: str | None = None, node_id: str | None = None, asset_id: str | None = None, pending: bool = False, cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(m.Observation).where(m.Observation.user_id == user.id, m.Observation.deleted == False)
    for key, value in [('species_id', species_id), ('project_id', project_id), ('node_id', node_id), ('asset_id', asset_id)]:
        if value:
            query = query.where(getattr(m.Observation, key) == value)
    if pending:
        query = query.where(m.Observation.confirmation == 'pending')
    return svc.page(db, query.order_by(func.coalesce(m.Observation.observed_at, m.Observation.created_at).desc(), m.Observation.id), lambda obj: svc.observation_json(db, obj, user), cursor, limit)


@api.post('/observations')
def CreateObservation(data: s.ObservationCreate, user=Depends(current_user), db: Session = Depends(get_db)):
    record = atlas.ConfirmPhoto(db, user, data)
    db.commit()
    return svc.observation_json(db, record, user)


@api.patch('/observations/{observation_id}')
def UpdateObservation(observation_id: str, data: s.ObservationPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    record = owned(db, m.Observation, observation_id, user)
    values = {key: getattr(record, key) for key in s.ObservationCreate.model_fields if hasattr(record, key)}
    changes = data.model_dump(exclude_unset=True)
    print('[开始] 修改物种方式选择')
    if 'species_name' in changes:
        print('[分支] 名称重新归类')
        values['species_id'] = None
    else:
        print('[分支] 保留或明确变更物种标识')
    print('[结束] 修改物种方式选择')
    values.update(changes)
    updated = atlas.ConfirmPhoto(db, user, s.ObservationCreate(**values))
    db.commit()
    return svc.observation_json(db, updated, user)


@api.delete('/observations/{observation_id}')
def DeleteObservation(observation_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    record = owned(db, m.Observation, observation_id, user)
    atlas.SaveArchive(db, user.id, 'observation', record)
    record.deleted = True
    db.commit()
    return {'deleted': True}


@api.put('/species/{species_id}/cover')
def SetSpeciesCover(species_id: str, data: s.SpeciesCover, user=Depends(current_user), db: Session = Depends(get_db)):
    species = owned(db, m.Species, species_id, user)
    record = db.scalar(select(m.Observation).where(m.Observation.user_id == user.id,
        m.Observation.species_id == species.id, m.Observation.asset_id == data.asset_id,
        m.Observation.deleted == False, m.Observation.confirmation == 'confirmed'))
    print('[开始] 图鉴封面照片检查')
    if record is None:
        print('[分支] 不是此物种的有效归档照片')
        fail(422, 'invalid_cover', '请从该物种的照片中选择封面')
    else:
        print('[分支] 使用已确认照片')
    print('[结束] 图鉴封面照片检查')
    svc.asset_access(db, data.asset_id, user)
    species.cover_asset_id = data.asset_id
    db.commit()
    return svc.species_json(db, species, user, include_photos=True)


@api.get('/knowledge/search')
def knowledge_search(q: str = '', scope: str = 'all', user=Depends(current_user), db: Session = Depends(get_db)):
    if scope not in {'all', 'public', 'mine'}:
        fail(422, 'invalid_scope', '查询范围无效')
    return {'items': svc.knowledge(db, user, q, scope), 'next_cursor': None}
