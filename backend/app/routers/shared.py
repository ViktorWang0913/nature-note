from sqlalchemy import select
from ..config import settings
from .. import models as m, services as svc
from ..security import owned, fail, token


def login(db, identity, createNew=False):
    user = db.scalar(select(m.User).where(m.User.identity == identity))
    print('[开始] 注销后重新注册检查')
    if user and user.deleted_at:
        print('[分支] 原账号已注销')
        print('[开始] 新账号确认检查')
        if not createNew:
            print('[分支] 等待明确确认')
            fail(409, 'account_deleted', '原账号已注销，确认后可创建空白新账号')
        else:
            print('[分支] 解除原身份占用，创建独立账号')
            user.identity = 'deleted:' + user.id
            db.flush()
            user = None
        print('[结束] 新账号确认检查')
    else:
        print('[分支] 普通登录或首次注册')
    print('[结束] 注销后重新注册检查')
    if not user:
        user = m.User(identity=identity)
        db.add(user)
        db.commit()
    user.last_seen_at = m.now()
    db.commit()
    return {'access_token': token(user.id), 'expires_in': 604800, 'user': svc.public_user(db, user, user) | {'restricted': not user.active}}


async def receive_image(file):
    content = await file.read(settings().max_upload_bytes + 1)
    if len(content) > settings().max_upload_bytes:
        fail(413, 'file_too_large', '图片超过大小限制')
    if not content:
        fail(422, 'empty_file', '图片为空')
    return content


def validate_task_input(db, data, user):
    value = data.input
    if data.kind == 'image_generation':
        if not value.get('asset_id') and not str(value.get('prompt') or '').strip():
            fail(422, 'missing_prompt', '请输入生成描述或添加参考图片')
        if value.get('asset_id'):
            svc.asset_access(db, value['asset_id'], user)
    if data.kind == 'image_recognition':
        if not value.get('asset_id'):
            fail(422, 'missing_asset', '请先上传照片')
        svc.asset_access(db, value['asset_id'], user)
    if value.get('session_id'):
        owned(db, m.GenerationSession, value['session_id'], user)
    print('[开始] 自然轨迹任务输入检查')
    if data.kind == 'image_polish':
        print('[分支] 从已保存的 GPS 框架创建服务端快照')
        from ..route_notes import Freeze
        Freeze(db, data, user)
    else:
        print('[分支] 其他任务沿用原输入')
    print('[结束] 自然轨迹任务输入检查')
    print('[开始] 千问图文问题检查')
    if data.kind == 'rag':
        print('[分支] 检查私人会话和输入')
        print('[开始] 问题内容检查')
        if not str(value.get('question', '')).strip() and not value.get('asset_id'):
            print('[分支] 空问题')
            fail(422, 'invalid_question', '请输入文字或添加一张图片')
        else:
            print('[分支] 输入有效')
        print('[结束] 问题内容检查')
        print('[开始] 对话归属检查')
        if not value.get('chat_session_id'):
            print('[分支] 未选择对话')
            fail(422, 'missing_chat', '请先新建或选择对话')
        else:
            print('[分支] 校验会话归属')
            owned(db, m.ChatSession, value['chat_session_id'], user)
        print('[结束] 对话归属检查')
        print('[开始] 对话图片检查')
        if value.get('asset_id'):
            print('[分支] 校验图片归属')
            svc.asset_access(db, value['asset_id'], user)
        else:
            print('[分支] 没有参考图')
        print('[结束] 对话图片检查')
    else:
        print('[分支] 非问答任务')
    print('[结束] 千问图文问题检查')
    if len(str(value)) > 500000:
        fail(413, 'input_too_large', '任务输入过大')


def check_species(db, species_id, user):
    species = db.get(m.Species, species_id) if species_id else None
    if species_id and (not species or species.user_id != user.id):
        fail(422, 'unknown_species', '请从图鉴中选择物种')


def notification_json(db, obj, user):
    target_exists = True
    if obj.target_type == 'post':
        post = db.get(m.Post, obj.target_id)
        target_exists = bool(post and not post.deleted and not post.hidden)
    return {'id': obj.id, 'kind': obj.kind, 'type': obj.kind, 'summary': obj.summary, 'text': obj.summary,
            'target_type': obj.target_type, 'target_id': obj.target_id, 'read': obj.read, 'created_at': obj.created_at,
            'actor': svc.public_user(db, db.get(m.User, obj.actor_id), user), 'target_exists': target_exists}
