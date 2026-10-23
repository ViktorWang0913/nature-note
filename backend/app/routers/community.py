from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models as m, schemas as s, services as svc, storage, atlas, moderation
from ..security import current_user, owned, fail, require_admin
from .shared import notification_json

def CheckCommunity(request: Request):
    print('[开始] 社区功能锁定检查')
    if request.url.path.startswith(('/api/v1/posts', '/api/v1/comments', '/api/v1/users')):
        print('[分支] 社区测试中；[结束] 社区功能锁定检查，提前结束')
        fail(503, 'community_testing', '社区功能测试中')
    print('[分支] 保留账号通知与反馈；[结束] 社区功能锁定检查')


api = APIRouter(prefix="/api/v1", tags=["community"], dependencies=[Depends(CheckCommunity)])


def CheckPublishing(db):
    control = db.get(m.PlatformControl, 'community')
    print('[开始] 社区维护检查')
    if control and not control.value.get('enabled', True):
        print('[分支] 社区发布暂停')
        fail(503, 'community_paused', control.value.get('message', '社区发布维护中'))
    else:
        print('[分支] 可提交审核')
    print('[结束] 社区维护检查')

@api.get('/posts')
def posts(feed: str = 'discover', q: str = '', user_id: str | None = None, cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(m.Post).where(m.Post.deleted == False, m.Post.hidden == False, or_(m.Post.title.contains(q), m.Post.text.contains(q)))
    print('[开始] 社区审核可见范围')
    if feed != 'mine':
        print('[分支] 仅已审核内容公开')
        query = query.where(m.Post.review_status == 'approved')
    else:
        print('[分支] 本人可查看待审核内容')
    print('[结束] 社区审核可见范围')
    if feed == 'following':
        query = query.where(m.Post.user_id.in_(select(m.Follow.target_id).where(m.Follow.user_id == user.id)))
    if feed == 'mine':
        query = query.where(m.Post.user_id == user.id)
    elif user_id:
        query = query.where(m.Post.user_id == user_id)
    return svc.page(db, query.order_by(m.Post.created_at.desc(), m.Post.id), lambda p: svc.post_json(db, p, user), cursor, limit)


@api.post('/posts')
def create_post(data: s.PostCreate, background: BackgroundTasks, user=Depends(current_user), db: Session = Depends(get_db)):
    CheckPublishing(db)
    previous = svc.operation_get(db, user, 'post', data.operation_id, m.Post)
    if previous:
        return svc.post_json(db, previous, user)
    if data.project_id:
        owned(db, m.Project, data.project_id, user)
    images = []
    for asset_id in data.asset_ids:
        asset = svc.asset_access(db, asset_id, user)
        # A public snapshot never uses the original's private URL or EXIF.
        image = storage.image_bytes(storage.read(asset.key))
        images.append(storage.put(storage.encode(image), public=False))
    obj = m.Post(user_id=user.id, title=data.title, text=data.text, images=images, project_id=data.project_id, location_text=data.location_text)
    db.add(obj)
    svc.operation_add(db, user, 'post', data.operation_id, obj)
    moderation.Queue(db,obj,'post')
    db.commit()
    background.add_task(moderation.Run,'review:post:'+obj.id)
    return svc.post_json(db, obj, user)


@api.get('/posts/{post_id}')
def post_detail(post_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.post_json(db, svc.public_post(db, post_id, user), user)


@api.patch('/posts/{post_id}')
def update_post(post_id: str, data: s.PostPatch, background: BackgroundTasks, user=Depends(current_user), db: Session = Depends(get_db)):
    CheckPublishing(db)
    obj = owned(db, m.Post, post_id, user)
    atlas.SaveArchive(db, user.id, 'post', obj, '用户修改帖子')
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    print('[开始] 帖子修改发布方式')
    if obj.review_status == 'approved':
        print('[分支] 旧版继续公开，新版进入审核')
        pendingId = 'edit:' + obj.id
        pending = db.get(m.PlatformControl, pendingId)
        print('[开始] 待审核版本检查')
        if pending is None:
            print('[分支] 首次提交修改')
            pending = m.PlatformControl(id=pendingId, value={})
            db.add(pending)
        else:
            print('[分支] 更新待审版本')
        print('[结束] 待审核版本检查')
        pending.value = {**pending.value, **changes}
    else:
        print('[分支] 未公开的内容直接更新后继续审核')
        obj.review_status = 'pending'
        print(f'[开始] 帖子字段更新，共 {len(changes)} 项')
        for fieldIndex, (key, value) in enumerate(changes.items(), 1):
            print(f'[开始] 帖子字段 {fieldIndex}/{len(changes)}')
            setattr(obj, key, value)
            print(f'[结束] 帖子字段 {fieldIndex}/{len(changes)}')
        print('[结束] 帖子字段更新')
    print('[结束] 帖子修改发布方式')
    db.flush()
    moderation.Queue(db,obj,'post')
    db.commit()
    background.add_task(moderation.Run,'review:post:'+obj.id)
    return svc.post_json(db, obj, user)


@api.delete('/posts/{post_id}')
def delete_post(post_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db, m.Post, post_id, user)
    atlas.SaveArchive(db, user.id, 'post', item)
    item.deleted = True
    db.commit()
    return {'deleted': True}


@api.put('/posts/{post_id}/like')
def like_post(post_id: str, data: s.LikeInput, user=Depends(current_user), db: Session = Depends(get_db)):
    post = svc.public_post(db, post_id, user)
    row = db.get(m.Like, (user.id, post.id))
    if data.liked and not row:
        db.add(m.Like(user_id=user.id, post_id=post.id))
        svc.notify(db, post.user_id, user.id, 'like', 'post', post.id, f'赞了你的笔记「{post.title}」')
    elif not data.liked and row:
        db.delete(row)
    db.commit()
    return svc.post_json(db, post, user)


@api.get('/posts/{post_id}/comments')
def comments(post_id: str, cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    svc.public_post(db, post_id, user)
    return svc.page(db, select(m.Comment).where(m.Comment.post_id == post_id, m.Comment.deleted == False, or_(m.Comment.review_status == 'approved', m.Comment.user_id == user.id)).order_by(m.Comment.created_at, m.Comment.id), lambda c: svc.comment_json(db, c, user), cursor, limit)


@api.post('/posts/{post_id}/comments')
def create_comment(post_id: str, data: s.CommentInput, background: BackgroundTasks, user=Depends(current_user), db: Session = Depends(get_db)):
    CheckPublishing(db)
    post = svc.public_post(db, post_id, user)
    if not data.text.strip():
        fail(422, 'empty_comment', '请输入评论内容')
    obj = m.Comment(user_id=user.id, post_id=post.id, text=data.text)
    db.add(obj)
    db.flush()
    moderation.Queue(db,obj,'comment')
    db.commit()
    background.add_task(moderation.Run,'review:comment:'+obj.id)
    return svc.comment_json(db, obj, user)


@api.delete('/comments/{comment_id}')
def delete_comment(comment_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    item = owned(db, m.Comment, comment_id, user)
    atlas.SaveArchive(db, user.id, 'comment', item)
    item.deleted = True
    db.commit()
    return {'deleted': True}


@api.get('/users/{user_id}')
def user_detail(user_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = db.get(m.User, user_id)
    if not obj or not obj.active:
        fail(404, 'not_found', '用户不存在')
    return svc.public_user(db, obj, user)


@api.get('/users')
def users(q: str = '', cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.page(db, select(m.User).where(m.User.active == True, m.User.name.contains(q)).order_by(m.User.name, m.User.id), lambda obj: svc.public_user(db, obj, user), cursor, limit)


@api.put('/users/{user_id}/follow')
def follow_user(user_id: str, data: s.FollowInput, user=Depends(current_user), db: Session = Depends(get_db)):
    target = db.get(m.User, user_id)
    if not target or not target.active:
        fail(404, 'not_found', '用户不存在')
    if user.id == target.id:
        fail(422, 'self_follow', '不能关注自己')
    row = db.get(m.Follow, (user.id, target.id))
    if data.following and not row:
        db.add(m.Follow(user_id=user.id, target_id=target.id))
        svc.notify(db, target.id, user.id, 'follow', 'user', user.id, '关注了你')
    elif not data.following and row:
        db.delete(row)
    db.commit()
    return svc.public_user(db, target, user)


@api.get('/notifications')
def notifications(filter: str = 'all', q: str = '', cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(m.Notification).where(m.Notification.user_id == user.id)
    if filter == 'follow':
        query = query.where(m.Notification.kind == 'follow')
    elif filter == 'interaction':
        query = query.where(m.Notification.kind != 'follow')
    if q:
        query = query.join(m.User, m.User.id == m.Notification.actor_id).where(or_(m.Notification.summary.contains(q), m.User.name.contains(q)))
    return svc.page(db, query.order_by(m.Notification.created_at.desc(), m.Notification.id), lambda obj: notification_json(db, obj, user), cursor, limit)


@api.post('/notifications/{notification_id}/read')
def notification_read(notification_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    obj = owned(db, m.Notification, notification_id, user)
    obj.read = True
    db.commit()
    return notification_json(db, obj, user)


@api.post('/reports')
def create_report(data: s.ReportInput, user=Depends(current_user), db: Session = Depends(get_db)):
    if data.target_type == 'post':
        svc.public_post(db, data.target_id, user)
    elif data.target_type == 'comment':
        comment = db.get(m.Comment, data.target_id)
        if not comment or comment.deleted:
            fail(404, 'not_found', '评论不存在')
        svc.public_post(db, comment.post_id, user)
    elif not db.get(m.User, data.target_id):
        fail(404, 'not_found', '用户不存在')
    obj = m.Report(user_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    return {'id': obj.id, 'status': obj.status}
