"""Explicit account closure and resumable cleanup, separate from temporary suspension."""
from sqlalchemy import select, update, delete
from . import models as m, storage
from .security import fail
from .retention import MediaKeys, ReferencedMedia


def CloseAccount(db, user):
    from .routers.admin import CancelQueued
    user.active = False
    user.deleted_at = m.now()
    CancelQueued(db, userId=user.id)
    db.execute(update(m.Post).where(m.Post.user_id == user.id).values(deleted=True))
    db.execute(update(m.Comment).where(m.Comment.user_id == user.id).values(deleted=True))
    db.add(m.PlatformControl(id='deletion:' + user.id, value={'user_id': user.id, 'requested_at': user.deleted_at, 'state': 'queued'}))
    db.add(m.Audit(actor_id=user.id, action='account_closed', target_id=user.id, detail={'state':'cleanup_queued'}))
    db.commit()


def CleanupAccount(db, userId):
    user = db.get(m.User, userId)
    state = db.get(m.PlatformControl, 'deletion:' + userId)
    print('[开始] 注销清理资格检查')
    if not user or not user.deleted_at or not state or state.value.get('state') == 'complete':
        print('[分支] 无待清理注销账号')
        print('[结束] 注销清理资格检查；提前结束')
        return
    else:
        print('[分支] 检查进行中的上游任务')
    print('[结束] 注销清理资格检查')
    running = db.scalar(select(m.Task.id).where(m.Task.user_id == userId, m.Task.lease_until > m.now()).limit(1))
    print('[开始] 注销任务写入屏障')
    if running:
        print('[分支] 等待执行租约结束，避免清理后重新写入')
        print('[结束] 注销任务写入屏障；提前结束本轮清理')
        return
    else:
        print('[分支] 无有效任务租约')
    print('[结束] 注销任务写入屏障')
    assets = list(db.scalars(select(m.Asset).where(m.Asset.user_id == userId)))
    tasks = list(db.scalars(select(m.Task).where(m.Task.user_id == userId)))
    posts = list(db.scalars(select(m.Post).where(m.Post.user_id == userId)))
    keys = {key for asset in assets for key in (asset.key, asset.original_key, asset.thumbnail_key) if key}
    keys.update(task.result['image_key'] for task in tasks if task.result and task.result.get('image_key'))
    keys.update(key for post in posts for key in post.images)
    archives = list(db.scalars(select(m.Archive).where(m.Archive.user_id == userId)))
    print(f'[开始] 注销归档媒体收集，共 {len(archives)} 条')
    for archiveIndex, archive in enumerate(archives, 1):
        print(f'[开始] 注销归档 {archiveIndex}/{len(archives)}')
        keys.update(MediaKeys(archive.snapshot))
        print(f'[结束] 注销归档 {archiveIndex}/{len(archives)}')
    print('[结束] 注销归档媒体收集')
    sharedKeys = set(db.scalars(select(m.Asset.key).where(m.Asset.user_id.is_(None)))) | set(db.scalars(select(m.Template.cover_key)))
    keys.difference_update(sharedKeys)
    print(f'[开始] 注销文件清理，共 {len(keys)} 个')
    for keyIndex, key in enumerate(sorted(keys), 1):
        print(f'[开始] 注销文件 {keyIndex}/{len(keys)}')
        storage.Delete(key, allowPublic=True)
        print(f'[结束] 注销文件 {keyIndex}/{len(keys)}')
    print('[结束] 注销文件清理')
    trackIds = select(m.Track.id).where(m.Track.user_id == userId)
    db.execute(delete(m.TrackPoint).where(m.TrackPoint.track_id.in_(trackIds)))
    db.execute(delete(m.UserPhone).where(m.UserPhone.user_id == userId))
    db.execute(delete(m.Observation).where(m.Observation.user_id == userId))
    db.execute(delete(m.Node).where(m.Node.user_id == userId))
    db.execute(delete(m.Track).where(m.Track.user_id == userId))
    db.execute(delete(m.Project).where(m.Project.user_id == userId))
    db.execute(delete(m.Species).where(m.Species.user_id == userId))
    db.execute(delete(m.ChatMessage).where(m.ChatMessage.user_id == userId))
    db.execute(delete(m.ChatSession).where(m.ChatSession.user_id == userId))
    db.execute(delete(m.GenerationSession).where(m.GenerationSession.user_id == userId))
    db.execute(delete(m.Archive).where(m.Archive.user_id == userId))
    db.execute(delete(m.Correction).where(m.Correction.user_id == userId))
    db.execute(delete(m.Feedback).where(m.Feedback.user_id == userId))
    db.execute(delete(m.Notification).where((m.Notification.user_id == userId) | (m.Notification.actor_id == userId)))
    db.execute(delete(m.Favorite).where((m.Favorite.user_id == userId) | m.Favorite.asset_id.in_(select(m.Asset.id).where(m.Asset.user_id == userId))))
    db.execute(delete(m.Follow).where((m.Follow.user_id == userId) | (m.Follow.target_id == userId)))
    db.execute(delete(m.Like).where(m.Like.user_id == userId))
    db.execute(update(m.Asset).where(m.Asset.user_id == userId).values(deleted=True, key='', original_key='', thumbnail_key='', title='', history=[]))
    db.execute(update(m.Task).where(m.Task.user_id == userId).values(input={}, error=None))
    print(f'[开始] 移除任务内容，共 {len(tasks)} 条')
    for taskIndex, task in enumerate(tasks, 1):
        print(f'[开始] 清理任务内容 {taskIndex}/{len(tasks)}')
        result = task.result or {}
        task.result = {key: result[key] for key in ('provider_task_id', '_upstream_task_id') if key in result}
        print(f'[结束] 清理任务内容 {taskIndex}/{len(tasks)}')
    print('[结束] 移除任务内容')
    db.execute(update(m.Post).where(m.Post.user_id == userId).values(title='', text='', images=[], location_text='', deleted=True))
    db.execute(update(m.Comment).where(m.Comment.user_id == userId).values(text='', deleted=True))
    db.execute(delete(m.PlatformControl).where(m.PlatformControl.id.in_(['edit:' + post.id for post in posts])))
    reviewIds = ['review:post:' + post.id for post in posts]
    reviewIds += ['review:comment:' + commentId for commentId in db.scalars(select(m.Comment.id).where(m.Comment.user_id == userId))]
    db.execute(delete(m.PlatformControl).where(m.PlatformControl.id.in_(reviewIds)))
    db.execute(delete(m.PlatformControl).where(m.PlatformControl.id.startswith('trace:'), m.PlatformControl.value['record_id'].as_string().in_(reviewIds)))
    user.name, user.avatar_url, user.bio = '已注销用户', '', ''
    state.value = {**state.value, 'state':'complete', 'completed_at':m.now()}
    db.commit()


def CleanupPending(db):
    pending = list(db.scalars(select(m.PlatformControl).where(m.PlatformControl.id.startswith('deletion:'))))
    print(f'[开始] 注销清理调度，共 {len(pending)} 条')
    for itemIndex, item in enumerate(pending, 1):
        print(f'[开始] 注销清理调度 {itemIndex}/{len(pending)}')
        CleanupAccount(db, item.value['user_id'])
        print(f'[结束] 注销清理调度 {itemIndex}/{len(pending)}')
    print('[结束] 注销清理调度')
