"""Expire archived content while preserving independently retained references."""
from sqlalchemy import select, delete

from . import models as m, storage
from .file_access import ProjectAssetIds


def MediaKeys(value, mediaField=False):
    # Only server storage keys are eligible; URLs and filesystem paths are ignored.
    keys = set()
    print('[开始] 归档媒体键读取')
    if isinstance(value, dict):
        print('[分支] 遍历结构字段')
        values = [(item, field in {'key', 'image_key', 'original_key', 'thumbnail_key', 'images', 'cover_key'}) for field, item in value.items() if field in {'key', 'image_key', 'original_key', 'thumbnail_key', 'images', 'cover_key', 'history', 'result', 'input', 'snapshot', 'route_draft', 'graph', 'nodes', 'template'}]
    elif isinstance(value, list):
        print('[分支] 遍历结构列表')
        values = [(item, mediaField) for item in value]
    elif mediaField and isinstance(value, str) and value.startswith(('private/', 'public/')):
        print('[分支] 服务器媒体键')
        print('[结束] 归档媒体键读取；提前返回键')
        return {value}
    else:
        print('[分支] 非媒体内容')
        values = []
    print('[结束] 归档媒体键读取')
    print(f'[开始] 媒体结构遍历，共 {len(values)} 项')
    for valueIndex, (item, isMedia) in enumerate(values, 1):
        print(f'[开始] 媒体字段 {valueIndex}/{len(values)}')
        keys.update(MediaKeys(item, isMedia))
        print(f'[结束] 媒体字段 {valueIndex}/{len(values)}')
    print('[结束] 媒体结构遍历')
    return keys


def RetainedAssetIds(db):
    ids = set()
    projects = list(db.scalars(select(m.Project).where(m.Project.deleted == False)))
    print(f'[开始] 保留笔记引用，共 {len(projects)} 本')
    for projectIndex, project in enumerate(projects, 1):
        print(f'[开始] 引用笔记 {projectIndex}/{len(projects)}')
        ids.update(ProjectAssetIds(project))
        print(f'[结束] 引用笔记 {projectIndex}/{len(projects)}')
    print('[结束] 保留笔记引用')
    ids.update(db.scalars(select(m.ChatMessage.asset_id).join(m.ChatSession, m.ChatSession.id == m.ChatMessage.session_id).where(m.ChatSession.deleted == False)))
    sessions = list(db.scalars(select(m.GenerationSession).where(m.GenerationSession.deleted == False)))
    print(f'[开始] 生图引用检查，共 {len(sessions)} 个会话')
    for sessionIndex, session in enumerate(sessions, 1):
        print(f'[开始] 生图引用 {sessionIndex}/{len(sessions)}')
        ids.update(message.get('asset_id') for message in session.messages)
        print(f'[结束] 生图引用 {sessionIndex}/{len(sessions)}')
    print('[结束] 生图引用检查')
    ids.update(db.scalars(select(m.Node.cover_asset_id)))
    nodes = list(db.scalars(select(m.Node)))
    print(f'[开始] 观察点保留引用，共 {len(nodes)} 条')
    for nodeIndex, node in enumerate(nodes, 1):
        print(f'[开始] 观察点保留 {nodeIndex}/{len(nodes)}')
        ids.update(node.asset_ids)
        print(f'[结束] 观察点保留 {nodeIndex}/{len(nodes)}')
    print('[结束] 观察点保留引用')
    return ids


def PurgeArchive(db, archive):
    keys = MediaKeys(archive.snapshot)
    models = {'asset': m.Asset, 'project': m.Project, 'post': m.Post, 'comment': m.Comment,
        'task': m.Task, 'chat': m.ChatSession, 'generation_session': m.GenerationSession, 'observation': m.Observation}
    model = models.get(archive.resource_type)
    record = db.get(model, archive.resource_id) if model else None
    otherArchive = db.scalar(select(m.Archive.id).where(m.Archive.id != archive.id,
        m.Archive.resource_type == archive.resource_type, m.Archive.resource_id == archive.resource_id).limit(1))
    print('[开始] 归档原记录清理条件')
    if record and getattr(record, 'deleted', False) and not otherArchive:
        print('[分支] 原记录已删除且不存在其他保留归档')
        print('[开始] 原记录清理类型')
        if isinstance(record, m.Asset):
            print('[分支] 检查照片独立引用')
            print('[开始] 独立引用保留检查')
            if record.id not in RetainedAssetIds(db):
                print('[分支] 清空照片记录')
                keys.update(MediaKeys(record.history))
                keys.update({record.key, record.original_key, record.thumbnail_key} - {''})
                record.key, record.original_key, record.thumbnail_key, record.title, record.history = '', '', '', '', []
            else:
                print('[分支] 保留笔记或会话使用的照片')
            print('[结束] 独立引用保留检查')
        elif isinstance(record, m.Project):
            print('[分支] 清空已删除笔记')
            record.title, record.layout, record.asset_ids, record.cover_asset_id = '', {}, [], None
        elif isinstance(record, m.Post):
            print('[分支] 清空已删除帖子')
            record.title, record.text, record.location_text, record.images = '', '', '', []
        elif isinstance(record, m.Comment):
            print('[分支] 清空已删除评论')
            record.text = ''
        elif isinstance(record, m.Task):
            print('[分支] 清空已删除任务私有内容，账单另行保留')
            record.input, record.result, record.error = {}, {}, None
        elif isinstance(record, m.ChatSession):
            print('[分支] 清空已删除问答及摘要')
            db.execute(delete(m.ChatMessage).where(m.ChatMessage.session_id == record.id))
            record.title, record.summary, record.summary_until = '', '', None
        elif isinstance(record, m.GenerationSession):
            print('[分支] 清空已删除生图会话')
            record.title, record.messages = '', []
        else:
            print('[分支] 清除已删除图鉴观察记录')
            db.delete(record)
        print('[结束] 原记录清理类型')
    else:
        print('[分支] 原内容仍在使用或仍有归档保留')
    print('[结束] 归档原记录清理条件')
    db.delete(archive)
    db.flush()
    return keys


def ReferencedMedia(db):
    keys = set()
    records = list(db.scalars(select(m.Asset)))
    print(f'[开始] 媒体保留扫描，共 {len(records)} 个素材')
    for recordIndex, asset in enumerate(records, 1):
        print(f'[开始] 媒体保留 {recordIndex}/{len(records)}')
        keys.update({asset.key, asset.original_key, asset.thumbnail_key})
        keys.update(MediaKeys(asset.history))
        print(f'[结束] 媒体保留 {recordIndex}/{len(records)}')
    print('[结束] 媒体保留扫描')
    values = list(db.scalars(select(m.Task.result))) + list(db.scalars(select(m.Task.input))) + list(db.scalars(select(m.Project.route_draft))) + [{'images': images} for images in db.scalars(select(m.Post.images))] + list(db.scalars(select(m.Archive.snapshot)))
    print(f'[开始] 任务帖子归档引用扫描，共 {len(values)} 项')
    for valueIndex, value in enumerate(values, 1):
        print(f'[开始] 媒体引用 {valueIndex}/{len(values)}')
        keys.update(MediaKeys(value))
        print(f'[结束] 媒体引用 {valueIndex}/{len(values)}')
    print('[结束] 任务帖子归档引用扫描')
    keys.update(db.scalars(select(m.Template.cover_key)))
    return keys


def ExpireArchives(db):
    archives = list(db.scalars(select(m.Archive).where(m.Archive.expires_at <= m.now()).limit(100)))
    keys = set()
    print(f'[开始] 归档到期清理，共 {len(archives)} 条')
    for archiveIndex, archive in enumerate(archives, 1):
        print(f'[开始] 到期归档 {archiveIndex}/{len(archives)}')
        keys.update(PurgeArchive(db, archive))
        print(f'[结束] 到期归档 {archiveIndex}/{len(archives)}')
    print('[结束] 归档到期清理')
    print('[开始] 到期文件回收检查')
    if keys:
        print('[分支] 删除不存在独立引用的到期私有文件')
        unreferenced = keys - ReferencedMedia(db)
        print(f'[开始] 到期文件回收，共 {len(unreferenced)} 个')
        for keyIndex, key in enumerate(sorted(unreferenced), 1):
            print(f'[开始] 到期文件 {keyIndex}/{len(unreferenced)}')
            storage.Delete(key, allowPublic=True)
            print(f'[结束] 到期文件 {keyIndex}/{len(unreferenced)}')
        print('[结束] 到期文件回收')
    else:
        print('[分支] 无到期文件')
    print('[结束] 到期文件回收检查')
    db.commit()
