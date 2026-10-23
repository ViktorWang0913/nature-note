from sqlalchemy import select, or_
from . import models as m
from .security import fail


def CheckFileAccess(db, key, resourceType, resourceId):
    allowed = False
    ownerId = None
    print('[开始] 文件实时资源授权检查')
    if resourceType == 'asset':
        print('[分支] 素材访问')
        asset = db.get(m.Asset, resourceId)
        allowed = bool(asset and not asset.deleted and key in {asset.key, asset.original_key, asset.thumbnail_key})
        ownerId = getattr(asset, 'user_id', None)
    elif resourceType == 'project':
        print('[分支] 笔记保留引用')
        project = db.get(m.Project, resourceId)
        print('[开始] 笔记引用有效检查')
        if project and not project.deleted:
            print('[分支] 查找画布中的图片标识')
            ids = ProjectAssetIds(project)
            asset = db.scalar(select(m.Asset).where(m.Asset.id.in_(ids), or_(m.Asset.key == key, m.Asset.thumbnail_key == key)))
            allowed = bool(asset and asset.user_id in {None, project.user_id})
            ownerId = project.user_id
        else:
            print('[分支] 笔记已移除')
        print('[结束] 笔记引用有效检查')
    elif resourceType == 'chat':
        print('[分支] 对话保留的参考照片')
        session = db.get(m.ChatSession, resourceId)
        messageIds = select(m.ChatMessage.asset_id).where(m.ChatMessage.session_id == resourceId)
        asset = db.scalar(select(m.Asset).where(m.Asset.id.in_(messageIds), m.Asset.key == key))
        allowed = bool(session and not session.deleted and asset and asset.user_id in {None, session.user_id})
        ownerId = getattr(session, 'user_id', None)
    elif resourceType == 'post':
        print('[分支] 社区测试中，帖子旧文件链接停用')
        allowed = False
    elif resourceType == 'task':
        print('[分支] 生成结果')
        task = db.get(m.Task, resourceId)
        allowed = bool(task and not task.deleted and task.status == 'succeeded' and (task.result or {}).get('image_key') == key)
        ownerId = getattr(task, 'user_id', None)
    else:
        print('[分支] 兼容公共模板与公共素材')
        asset = db.scalar(select(m.Asset).where(m.Asset.deleted == False, m.Asset.user_id.is_(None), or_(m.Asset.key == key, m.Asset.thumbnail_key == key, m.Asset.original_key == key)))
        templateId = db.scalar(select(m.Template.id).where(m.Template.cover_key == key).limit(1))
        allowed = bool(asset or templateId)
    print('[结束] 文件实时资源授权检查')
    print('[开始] 文件账号有效检查')
    if ownerId:
        print('[分支] 私人资源要求账号仍有效')
        owner = db.get(m.User, ownerId)
        allowed = allowed and bool(owner and owner.active and not owner.deleted_at)
    else:
        print('[分支] 公共素材')
    print('[结束] 文件账号有效检查')
    print('[开始] 文件最终授权')
    if not allowed:
        print('[分支] 已删除或无权访问，旧链接失效')
        fail(404, 'file_unavailable', '文件已不可访问')
    else:
        print('[分支] 允许访问')
    print('[结束] 文件最终授权')


def ProjectAssetIds(project):
    ids = set(project.asset_ids or []) | {project.cover_asset_id}
    elements = project.layout.get('elements', [])
    print(f'[开始] 笔记引用汇总，共 {len(elements)} 个元素')
    for elementIndex, element in enumerate(elements, 1):
        print(f'[开始] 笔记引用 {elementIndex}/{len(elements)}')
        ids.add(element.get('asset_id'))
        nodes = element.get('route', {}).get('nodes', [])
        print(f'[开始] 轨迹图片汇总，共 {len(nodes)} 个观察点')
        for nodeIndex, node in enumerate(nodes, 1):
            print(f'[开始] 观察点引用 {nodeIndex}/{len(nodes)}')
            ids.update(node.get('asset_ids', []))
            ids.add(node.get('cover_asset_id'))
            print(f'[结束] 观察点引用 {nodeIndex}/{len(nodes)}')
        print('[结束] 轨迹图片汇总')
        print(f'[结束] 笔记引用 {elementIndex}/{len(elements)}')
    print('[结束] 笔记引用汇总')
    ids.discard(None)
    return ids
