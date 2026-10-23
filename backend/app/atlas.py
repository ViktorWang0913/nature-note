"""User-owned species; administrator grouping never changes user confirmation."""
import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, inspect

from . import models as m, services as svc
from .security import fail, owned
from .config import settings


def SaveArchive(db, userId, resourceType, resource, reason='用户删除'):
    snapshot = {column.key: getattr(resource, column.key) for column in inspect(type(resource)).columns}
    # A provisional cleanup deadline, not authority to retain otherwise unnecessary data.
    db.add(m.Archive(user_id=userId, resource_type=resourceType, resource_id=resource.id,
                     snapshot=snapshot, reason=reason,
                     expires_at=(datetime.now(timezone.utc) + timedelta(days=settings().archive_retention_days)).isoformat()))


def ResolveSpecies(db, user, speciesId=None, name='', scientificName=''):
    print('[开始] 个人物种解析')
    if speciesId:
        print('[分支] 使用个人物种标识')
        species = owned(db, m.Species, speciesId, user)
        print('[结束] 个人物种解析')
        return species
    else:
        print('[分支] 按用户确认名称解析')
    cleanName = name.strip()
    scientificName = scientificName.strip()
    print('[开始] 物种名称检查')
    if not cleanName:
        print('[分支] 未提供物种，保留未归档状态')
        print('[结束] 物种名称检查；提前结束个人物种解析')
        return None
    else:
        print('[分支] 已提供名称')
    print('[结束] 物种名称检查')
    identity = 'n:' + cleanName
    print('[开始] 学名合并选择')
    if scientificName:
        print('[分支] 优先使用学名')
        identity = 's:' + scientificName.casefold()
    else:
        print('[分支] 使用完全一致的确认名称')
    print('[结束] 学名合并选择')
    groupKey = hashlib.sha256(identity.encode()).hexdigest()
    speciesKey = hashlib.sha256((user.id + ':' + groupKey).encode()).hexdigest()
    species = db.get(m.Species, speciesKey)
    print('[开始] 个人条目创建检查')
    if species is None:
        print('[分支] 创建用户确认物种')
        species = m.Species(id=speciesKey, user_id=user.id, group_key=groupKey, name=cleanName,
                            scientific_name=scientificName, category='unclassified', description='',
                            source='用户自行确认', knowledge_version='user-v1')
        db.add(species)
        db.flush()
    else:
        print('[分支] 合并至已有个人物种')
    print('[结束] 个人条目创建检查')
    print('[结束] 个人物种解析')
    return species


def ConfirmPhoto(db, user, data):
    asset = owned(db, m.Asset, data.asset_id, user)
    print('[开始] 真实照片确认检查')
    if asset.source != 'photo' or asset.is_mock:
        print('[分支] 拒绝生成图或示例结果')
        fail(422, 'original_required', '请使用自己的真实照片归档')
    else:
        print('[分支] 接受真实照片')
    print('[结束] 真实照片确认检查')
    species = ResolveSpecies(db, user, data.species_id, data.species_name, data.scientific_name)
    print('[开始] 观察关联检查')
    if data.project_id:
        print('[分支] 检查关联笔记')
        owned(db, m.Project, data.project_id, user)
    else:
        print('[分支] 无关联笔记')
    print('[结束] 观察关联检查')
    print('[开始] 观察节点检查')
    if data.node_id:
        print('[分支] 校验节点及笔记一致性')
        node = owned(db, m.Node, data.node_id, user)
        print('[开始] 节点笔记一致性')
        if data.project_id and node.project_id != data.project_id:
            print('[分支] 关联冲突，拒绝归档')
            fail(422, 'node_project_mismatch', '观察点不属于该笔记')
        else:
            print('[分支] 关联有效')
        print('[结束] 节点笔记一致性')
    else:
        print('[分支] 无观察节点')
    print('[结束] 观察节点检查')
    record = db.scalar(select(m.Observation).where(m.Observation.user_id == user.id, m.Observation.asset_id == asset.id))
    print('[开始] 单张照片归档合并')
    if record is None:
        print('[分支] 新建观察')
        record = m.Observation(user_id=user.id, asset_id=asset.id)
        db.add(record)
    else:
        print('[分支] 更新已有观察，保留变化记录')
        SaveArchive(db, user.id, 'observation', record, '用户修改归档')
    print('[结束] 单张照片归档合并')
    record.species_id = getattr(species, 'id', None)
    record.confirmation = 'pending'
    print('[开始] 归档状态设置')
    if species:
        print('[分支] 用户已确认物种')
        record.confirmation = 'confirmed'
    else:
        print('[分支] 保留未归档状态')
    print('[结束] 归档状态设置')
    record.project_id, record.node_id = data.project_id, data.node_id
    record.text, record.observed_at = data.text, data.observed_at
    record.latitude, record.longitude = data.latitude, data.longitude
    record.deleted, record.is_mock = False, False
    record.confirmed_by = data.confirmed_by
    record.evidence = data.evidence
    db.flush()
    return record
