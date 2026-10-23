import base64
import json
import math
from sqlalchemy import select, func, or_
from . import models as m, storage
from .security import fail, owned
from .file_access import CheckFileAccess, ProjectAssetIds


def page(db, query, serialize, cursor=None, limit=30, rows=False):
    limit = max(1, min(limit, 100))
    try:
        offset = int(base64.urlsafe_b64decode(cursor).decode()) if cursor else 0
        if offset < 0:
            raise ValueError()
    except Exception:
        fail(422, 'invalid_cursor', '分页参数无效')
    print('[开始] 分页查询结果类型')
    if rows:
        print('[分支] 一次查询素材及关联状态')
        values = db.execute(query.offset(offset).limit(limit + 1)).all()
    else:
        print('[分支] 普通实体分页')
        values = db.scalars(query.offset(offset).limit(limit + 1)).all()
    print('[结束] 分页查询结果类型')
    return {'items': [serialize(value) for value in values[:limit]], 'next_cursor': base64.urlsafe_b64encode(str(offset + limit).encode()).decode() if len(values) > limit else None}


def public_user(db, user, viewer=None):
    return {'id': user.id, 'name': user.name, 'nickname': user.name, 'avatar_url': user.avatar_url, 'bio': user.bio,
            'following': bool(viewer and db.get(m.Follow, (viewer.id, user.id))),
            'follower_count': db.scalar(select(func.count()).select_from(m.Follow).where(m.Follow.target_id == user.id)),
            'following_count': db.scalar(select(func.count()).select_from(m.Follow).where(m.Follow.user_id == user.id))}


def asset_access(db, asset_id, user, retainedIds=()):
    asset = db.get(m.Asset, asset_id)
    hiddenAsset = db.get(m.HiddenAsset, (user.id, asset_id)) if asset and asset.user_id is None else None
    if not asset or ((asset.deleted or hiddenAsset) and asset.id not in retainedIds) or (asset.user_id is not None and asset.user_id != user.id):
        fail(404, 'not_found', '素材不存在或不可访问')
    return asset


def assets_access(db, ids, user, retainedIds=()):
    for asset_id in ids:
        asset_access(db, asset_id, user, retainedIds)


def asset_json(db, asset, user, favoriteValue=None):
    return {'id': asset.id, 'title': asset.title, 'name': asset.title, 'category': asset.category, 'source': asset.source,
            'url': storage.url(asset.key, 'asset', asset.id), 'image_url': storage.url(asset.key, 'asset', asset.id), 'thumbnail_url': storage.url(asset.thumbnail_key or asset.key, 'asset', asset.id, preview=True),
            'width': asset.width, 'height': asset.height, 'version': asset.version, 'is_mock': asset.is_mock,
            'original_asset_id': asset.original_asset_id, 'favorite': bool(db.get(m.Favorite, (user.id, asset.id))) if favoriteValue is None else bool(favoriteValue),
            'created_at': asset.created_at, 'editable': asset.user_id == user.id}


def empty_layout():
    return {'schema_version': 1, 'width': 3600, 'height': 2400, 'background': '#fff8dc', 'elements': []}


def validate_layout(db, layout, user, retainedIds=()):
    if layout.get('schema_version') != 1 or not isinstance(layout.get('elements'), list):
        fail(422, 'invalid_layout', '不支持的画布结构')
    for key in ['width', 'height']:
        value = layout.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 100 <= value <= 10000:
            fail(422, 'invalid_layout', '画布尺寸应为 100 至 10000 像素')
    if len(layout['elements']) > 1000:
        fail(422, 'invalid_layout', '画布元素过多')
    ids = set()
    routes = set()
    for element in layout['elements']:
        if not isinstance(element, dict) or not element.get('id') or element['id'] in ids or element.get('type') not in {'image', 'text', 'route', 'stroke', 'shape'}:
            fail(422, 'invalid_layout', '元素类型或标识无效')
        ids.add(element['id'])
        for key in ['x', 'y', 'width', 'height', 'rotation', 'z']:
            value = element.get(key, 0)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 100000:
                fail(422, 'invalid_layout', '元素坐标无效')
        if element.get('asset_id'):
            asset_access(db, element['asset_id'], user, retainedIds)
        if element.get('type') == 'route':
            routes.add(element['id'])
            route = element.get('route', {})
            if route.get('track_id'):
                owned(db, m.Track, route['track_id'], user)
            for node in route.get('nodes', []):
                if not isinstance(node, dict) or not isinstance(node.get('asset_ids', []), list):
                    fail(422, 'invalid_layout', '观察点素材格式无效')
                if any(not isinstance(asset_id, str) or not asset_id for asset_id in node.get('asset_ids', [])):
                    fail(422, 'invalid_node_assets', '观察点素材标识无效')
                assets_access(db, node.get('asset_ids', []), user, retainedIds)
    for element in layout['elements']:
        if element.get('parent_id') and element['parent_id'] not in routes:
            fail(422, 'invalid_layout', '分组父元素不存在')


def node_attachment_updates(db, layout, user, retainedIds=()):
    """Validate/normalize layout attachments without changing persisted nodes."""
    updates = {}
    for element in layout.get('elements', []):
        route = element.get('route', {}) if element.get('type') == 'route' else {}
        track_id = route.get('track_id')
        if not track_id:
            continue
        owned(db, m.Track, track_id, user)
        for reference in route.get('nodes', []):
            if not isinstance(reference.get('id'), str) or not reference['id']:
                fail(422, 'invalid_node_reference', '真实轨迹观察点缺少有效标识')
            node = owned(db, m.Node, reference['id'], user)
            if node.track_id != track_id:
                fail(422, 'node_track_mismatch', '观察点不属于引用的真实轨迹')
            raw_ids = reference.get('asset_ids', node.asset_ids)
            if not isinstance(raw_ids, list) or len(raw_ids) > 200 or any(not isinstance(asset_id, str) or not asset_id for asset_id in raw_ids):
                fail(422, 'invalid_node_assets', '观察点素材应为有效标识列表，最多 200 项')
            asset_ids = list(dict.fromkeys(raw_ids))
            assets_access(db, asset_ids, user, retainedIds)
            cover = reference.get('cover_asset_id')
            if cover:
                if not isinstance(cover, str):
                    fail(422, 'invalid_cover', '观察点封面标识无效')
                asset_access(db, cover, user, retainedIds)
                if cover not in asset_ids:
                    fail(422, 'invalid_cover', '封面必须来自该观察点素材')
            else:
                cover = node.cover_asset_id if node.cover_asset_id in asset_ids else (asset_ids[0] if asset_ids else None)
            candidate = (node, asset_ids, cover)
            previous = updates.get(node.id)
            if previous and (previous[1] != asset_ids or previous[2] != cover):
                fail(422, 'node_attachment_conflict', '同一观察点的多处引用包含不同素材或封面，请先保持一致')
            updates[node.id] = candidate
            # Persist the same normalized view in layout and in the real node.
            reference['asset_ids'] = asset_ids
            reference['cover_asset_id'] = cover
    return list(updates.values())


def hydrate_layout(db, layout, user, projectId=None):
    result = json.loads(json.dumps(layout))
    for element in result.get('elements', []):
        if element.get('asset_id'):
            asset = db.get(m.Asset, element['asset_id'])
            if asset and (not asset.deleted or projectId) and asset.user_id in {None, user.id}:
                element['url'] = storage.url(asset.key, 'project' if projectId else 'asset', projectId or asset.id)
            else:
                element['url'] = ''
    return result


def project_json(db, project, user):
    result = {key: getattr(project, key) for key in ['id', 'user_id', 'title', 'version', 'asset_ids', 'cover_asset_id', 'created_at', 'updated_at']}
    result['layout'] = hydrate_layout(db, project.layout, user, project.id)
    cover = db.get(m.Asset, project.cover_asset_id) if project.cover_asset_id else None
    result['cover_url'] = storage.url(cover.thumbnail_key or cover.key, 'project', project.id, preview=True) if cover else ''
    return result


def task_json(task):
    result = {key: value for key, value in (task.result or {}).items() if not key.startswith('_')}
    if result.get('image_key'):
        result['image_url'] = storage.url(result.pop('image_key'), 'task', task.id)
    return {'id': task.id, 'kind': task.kind, 'status': task.status, 'input': task.input, 'result': result or None,
            'error': task.error, 'is_mock': task.is_mock, 'created_at': task.created_at, 'updated_at': task.updated_at, 'saved_asset_id': task.saved_asset_id}


def observed_photos(db, user, species_id):
    records = db.scalars(select(m.Observation).where(m.Observation.user_id == user.id, m.Observation.species_id == species_id, m.Observation.confirmation == 'confirmed', m.Observation.deleted == False).order_by(m.Observation.created_at)).all()
    result = {}
    for record in records:
        asset = db.get(m.Asset, record.asset_id)
        if asset and not asset.deleted and asset.source == 'photo' and not asset.is_mock:
            original_id = asset.original_asset_id or asset.id
            result[original_id] = asset
    return list(result.values())


def species_json(db, species, user, include_photos=False):
    photos = observed_photos(db, user, species.id)
    result = {key: getattr(species, key) for key in ['id', 'name', 'scientific_name', 'aliases', 'category', 'description', 'rarity', 'knowledge_version', 'source']}
    result.update(image_url=storage.url(species.image_key), photo_count=len(photos), recorded=bool(photos))
    print('[开始] 私人图鉴封面选择')
    if photos:
        print('[分支] 使用已确认照片，封面缺失时回退首张')
        cover = next((photo for photo in photos if photo.id == species.cover_asset_id), photos[0])
        result['image_url'] = storage.url(cover.key, 'asset', cover.id)
    else:
        print('[分支] 无观察照片，不展示基础图鉴示例封面')
        result['image_url'] = ''
    print('[结束] 私人图鉴封面选择')
    if include_photos:
        result['photos'] = [asset_json(db, asset, user) for asset in photos]
    return result


def observation_json(db, obj, user):
    result = {key: getattr(obj, key) for key in ['id', 'asset_id', 'species_id', 'project_id', 'node_id', 'text', 'observed_at', 'latitude', 'longitude', 'is_mock', 'confirmation', 'created_at']}
    asset = db.get(m.Asset, obj.asset_id)
    result['asset'] = asset_json(db, asset, user) if asset and not asset.deleted else None
    species = db.get(m.Species, obj.species_id) if obj.species_id else None
    result['species_name'] = species.name if species else None
    result.update(evidence=obj.evidence, confirmed_by=obj.confirmed_by)
    return result


def node_json(obj):
    return {key: getattr(obj, key) for key in ['id', 'track_id', 'project_id', 'latitude', 'longitude', 'time', 'place_name', 'text', 'asset_ids', 'cover_asset_id', 'species_id']}


def track_json(db, track, detailed=True):
    result = {key: getattr(track, key) for key in ['id', 'project_id', 'title', 'status', 'coordinate_system', 'created_at', 'ended_at']}
    if detailed:
        result['points'] = [{key: getattr(p, key) for key in ['sequence', 'latitude', 'longitude', 'accuracy', 'timestamp', 'segment']} for p in db.scalars(select(m.TrackPoint).where(m.TrackPoint.track_id == track.id).order_by(m.TrackPoint.sequence))]
        result['nodes'] = [node_json(n) for n in db.scalars(select(m.Node).where(m.Node.track_id == track.id).order_by(m.Node.time))]
    return result


def public_post(db, post_id, user):
    post = db.get(m.Post, post_id)
    if not post or post.deleted or ((post.hidden or post.review_status != 'approved') and post.user_id != user.id):
        fail(404, 'not_found', '内容已删除或不可访问')
    return post


def post_json(db, post, user):
    pending = db.get(m.PlatformControl, 'edit:' + post.id)
    draft = pending.value if pending and post.user_id == user.id else {}
    return {'id': post.id, 'title': draft.get('title', post.title), 'text': draft.get('text', post.text), 'review_status': 'pending' if draft else post.review_status, 'review_reason': post.review_reason, 'images': [storage.url(key, 'post', post.id) for key in post.images],
            'location_text': draft.get('location_text', post.location_text), 'created_at': post.created_at, 'author': public_user(db, db.get(m.User, post.user_id), user),
            'liked': bool(db.get(m.Like, (user.id, post.id))), 'like_count': db.scalar(select(func.count()).select_from(m.Like).where(m.Like.post_id == post.id)),
            'comment_count': db.scalar(select(func.count()).select_from(m.Comment).where(m.Comment.post_id == post.id, m.Comment.deleted == False)), 'is_owner': user.id == post.user_id}


def comment_json(db, comment, user):
    return {'id': comment.id, 'post_id': comment.post_id, 'text': comment.text, 'created_at': comment.created_at,
            'author': public_user(db, db.get(m.User, comment.user_id), user), 'is_owner': comment.user_id == user.id}


def notify(db, recipient, actor, kind, target_type, target_id, summary):
    if recipient != actor or kind in {'quota', 'review', 'feedback', 'correction', 'ai', 'account'}:
        db.add(m.Notification(user_id=recipient, actor_id=actor, kind=kind, target_type=target_type, target_id=target_id, summary=summary))


def operation_get(db, user, kind, operation_id, model):
    if not operation_id:
        return None
    operation = db.get(m.Operation, (user.id, kind, operation_id))
    record = db.get(model, operation.resource_id) if operation else None
    print('[开始] 幂等操作删除状态检查')
    if record and getattr(record,'deleted',False):
        print('[分支] 原结果已删除，不重新展示或恢复')
        fail(410,'operation_deleted','原操作结果已删除，请开始新的操作')
    else:
        print('[分支] 可复用现有操作结果')
    print('[结束] 幂等操作删除状态检查')
    return record


def operation_add(db, user, kind, operation_id, resource):
    if operation_id:
        db.flush()
        db.add(m.Operation(user_id=user.id, kind=kind, operation_id=operation_id, resource_id=resource.id))


def knowledge(db, user, q, scope='all'):
    terms = [q.strip()] if q.strip() else []
    result = []
    if scope in {'all', 'public'}:
        for species in db.scalars(select(m.Species).where(m.Species.user_id == user.id)):
            searchable = species.name + ' '.join(species.aliases) + species.scientific_name + species.description
            if not terms or any(term.casefold() in searchable.casefold() or species.name in term for term in terms):
                result.append({'id': species.id, 'title': species.name, 'kind': 'public', 'excerpt': species.description, 'source': species.source, 'knowledge_version': species.knowledge_version})
    if scope in {'all', 'mine'}:
        for obs in db.scalars(select(m.Observation).where(m.Observation.user_id == user.id, m.Observation.deleted == False).order_by(m.Observation.created_at.desc()).limit(1000)):
            species = db.get(m.Species, obs.species_id) if obs.species_id else None
            name = species.name if species else '待确认观察'
            searchable = name + obs.text + (obs.observed_at or '')
            if not terms or any(term.casefold() in searchable.casefold() or name in term for term in terms):
                result.append({'id': obs.id, 'title': name, 'kind': 'mine', 'excerpt': obs.text, 'observed_at': obs.observed_at})
    return result[:30]
