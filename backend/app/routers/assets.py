import hmac
import io
import time
import hashlib
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, Response
from PIL import ImageEnhance, ImageOps
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from .. import models as m, schemas as s, services as svc, storage, atlas
from ..security import current_user, owned, fail, sign
from .shared import receive_image

api = APIRouter(prefix="/api/v1", tags=["assets"])

@api.get('/files/{key:path}')
def private_file(request: Request, key: str, expires: int, signature: str, resource_type: str = '', resource_id: str = '', preview: bool = False, db: Session = Depends(get_db)):
    if expires < time.time() or expires > time.time() + 3700 or not hmac.compare_digest(signature, sign(key + ':' + str(expires) + ':' + resource_type + ':' + resource_id + ':preview' * preview)):
        fail(403, 'expired_file_link', '文件授权已过期，请刷新')
    svc.CheckFileAccess(db, key, resource_type, resource_id)
    etag = '"' + hashlib.sha256((key + ':preview' * preview).encode()).hexdigest() + '"'
    headers = {'Cache-Control': 'private, no-cache', 'ETag': etag, 'X-Content-Type-Options': 'nosniff'}
    print('[开始] 图片条件请求')
    if request.headers.get('if-none-match') == etag:
        print('[分支] 授权通过且文件未变；[结束] 图片条件请求，提前结束')
        return Response(status_code=304, headers=headers)
    else:
        print('[分支] 返回图片内容')
    print('[结束] 图片条件请求')
    print('[开始] 图片响应类型')
    if preview:
        print('[分支] 授权通过后返回预览或缓存确认；[结束] 图片响应类型')
        previewPath = storage.PreviewPath(key)
        return FileResponse(previewPath, media_type='image/webp', headers=headers)
    print('[分支] 返回完整原图；[结束] 图片响应类型')
    return Response(storage.read(key), media_type='image/jpeg' if key.lower().endswith(('.jpg', '.jpeg')) else 'image/png', headers=headers)


@api.get('/assets')
def assets(q: str = '', category: str = '', source: str = 'all', favorite: bool = False, unfiled: bool = False, cursor: str | None = None, limit: int = 30, user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(m.Asset).where(m.Asset.deleted == False, m.Asset.source.not_in(['ai_reference', 'notebook_background']), or_(m.Asset.user_id == user.id, m.Asset.user_id.is_(None)), m.Asset.title.contains(q))
    query = query.where(~m.Asset.id.in_(select(m.HiddenAsset.asset_id).where(m.HiddenAsset.user_id == user.id)))
    if category and category != 'all':
        query = query.where(m.Asset.category == category)
    if source == 'public':
        query = query.where(m.Asset.user_id.is_(None))
    elif source != 'all':
        query = query.where(m.Asset.user_id == user.id, m.Asset.source == source)
    if favorite:
        query = query.join(m.Favorite, m.Favorite.asset_id == m.Asset.id).where(m.Favorite.user_id == user.id)
    print('[开始] 未归档筛选')
    if unfiled:
        print('[分支] 仅查询本人尚未归档的真实照片')
        query = query.where(m.Asset.user_id == user.id, m.Asset.source == 'photo', ~m.Asset.id.in_(
            select(m.Observation.asset_id).where(m.Observation.user_id == user.id,
                m.Observation.deleted == False, m.Observation.confirmation == 'confirmed')))
    else:
        print('[分支] 使用普通素材筛选')
    print('[结束] 未归档筛选')
    favoriteQuery = select(m.Favorite.asset_id).where(m.Favorite.user_id == user.id, m.Favorite.asset_id == m.Asset.id).correlate(m.Asset).exists()
    return svc.page(db, query.add_columns(favoriteQuery).order_by(m.Asset.created_at.desc(), m.Asset.id),
                    lambda row: svc.asset_json(db, row[0], user, row[1]), cursor, limit, rows=True)


@api.get('/assets/featured')
def FeaturedAssets(user=Depends(current_user), db: Session = Depends(get_db)):
    visible = select(m.Asset).where(m.Asset.deleted == False,
        or_(m.Asset.user_id == user.id, m.Asset.user_id.is_(None)),
        ~m.Asset.id.in_(select(m.HiddenAsset.asset_id).where(m.HiddenAsset.user_id == user.id)))
    photo = db.scalar(visible.where(m.Asset.source == 'photo').order_by(m.Asset.created_at.desc(), m.Asset.id).limit(1))
    print('[开始] 首页照片选择')
    if photo is None:
        print('[分支] 没有照片时保留公共示例')
        photo = db.scalar(visible.where(m.Asset.id == 'public-photo-bulbul-1'))
    else:
        print('[分支] 使用最新可见照片')
    print('[结束] 首页照片选择')
    illustration = db.scalar(visible.where(m.Asset.id == 'public-bulbul'))
    print('[开始] 首页插画选择')
    if illustration is None:
        print('[分支] 使用最新插画素材')
        illustration = db.scalar(visible.where(m.Asset.source.not_in(['photo', 'ai_reference', 'notebook_background']))
            .order_by(m.Asset.created_at.desc(), m.Asset.id).limit(1))
    else:
        print('[分支] 使用公共示例插画')
    print('[结束] 首页插画选择')
    return {'photo': storage.url(photo.thumbnail_key or photo.key, 'asset', photo.id, preview=True) if photo else '',
            'illustration': storage.url(illustration.thumbnail_key or illustration.key, 'asset', illustration.id, preview=True) if illustration else ''}


@api.post('/assets/upload')
async def upload(file: UploadFile = File(...), operation_id: str = Form(..., max_length=150), category: str = Form('unclassified'), user=Depends(current_user), db: Session = Depends(get_db)):
    previous = svc.operation_get(db, user, 'upload', operation_id, m.Asset)
    if previous:
        return svc.asset_json(db, previous, user)
    content = await receive_image(file)
    digest = hashlib.sha256(content).hexdigest()
    duplicate = db.scalar(select(m.Asset).where(m.Asset.user_id == user.id, m.Asset.source == 'photo', m.Asset.content_hash == digest, m.Asset.deleted == False))
    if duplicate:
        svc.operation_add(db, user, 'upload', operation_id, duplicate)
        db.commit()
        return svc.asset_json(db, duplicate, user)
    stored = storage.store_image(content)
    asset = m.Asset(user_id=user.id, title=Path(file.filename or '照片').stem[:200], category=category, source='photo', content_hash=digest, **stored)
    db.add(asset)
    svc.operation_add(db, user, 'upload', operation_id, asset)
    db.commit()
    return svc.asset_json(db, asset, user)


@api.get('/assets/{asset_id}')
def asset_detail(asset_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return svc.asset_json(db, svc.asset_access(db, asset_id, user), user)


@api.delete('/assets/{asset_id}')
def delete_asset(asset_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    asset = db.get(m.Asset, asset_id)
    print('[开始] 素材删除权限')
    if not asset or asset.user_id not in {None, user.id}:
        print('[分支] 不可访问；[结束] 素材删除权限，提前结束')
        fail(404, 'not_found', '素材不存在或不可访问')
    print('[分支] 本人或公共素材；[结束] 素材删除权限')
    print('[开始] 素材删除范围')
    if asset.user_id is None:
        print('[分支] 仅从本账号素材库移除')
        db.merge(m.HiddenAsset(user_id=user.id, asset_id=asset.id))
        db.commit()
        print('[结束] 素材删除范围，提前结束')
        return {'deleted': True, 'scope': 'library'}
    print('[分支] 本人素材软删除；[结束] 素材删除范围')
    print('[开始] 重复删除检查')
    if asset.deleted:
        print('[分支] 已删除；[结束] 重复删除检查，提前结束')
        return {'deleted': True}
    print('[分支] 首次删除；[结束] 重复删除检查')
    atlas.SaveArchive(db, user.id, 'asset', asset)
    asset.deleted = True
    records = list(db.scalars(select(m.Observation).where(m.Observation.user_id == user.id, m.Observation.asset_id == asset.id, m.Observation.deleted == False)))
    print(f'[开始] 素材关联归档清理，共 {len(records)} 条')
    for recordIndex, record in enumerate(records, 1):
        print(f'[开始] 关联归档 {recordIndex}/{len(records)}')
        atlas.SaveArchive(db, user.id, 'observation', record)
        record.deleted = True
        print(f'[结束] 关联归档 {recordIndex}/{len(records)}')
    print('[结束] 素材关联归档清理')
    db.commit()
    return {'deleted': True}


@api.put('/assets/{asset_id}/favorite')
def favorite(asset_id: str, data: s.FavoriteInput, user=Depends(current_user), db: Session = Depends(get_db)):
    asset = svc.asset_access(db, asset_id, user)
    row = db.get(m.Favorite, (user.id, asset.id))
    if data.favorite and not row:
        db.add(m.Favorite(user_id=user.id, asset_id=asset.id))
    elif not data.favorite and row:
        db.delete(row)
    db.commit()
    return svc.asset_json(db, asset, user)


@api.post('/assets/{asset_id}/edit')
def edit_asset(asset_id: str, data: s.EditInput, user=Depends(current_user), db: Session = Depends(get_db)):
    source = svc.asset_access(db, asset_id, user)
    image = storage.image_bytes(storage.read(source.key))
    if data.crop:
        crop = data.crop
        if crop.x + crop.width > 1.000001 or crop.y + crop.height > 1.000001:
            fail(422, 'invalid_crop', '裁剪范围超出图片')
        box = (round(crop.x * image.width), round(crop.y * image.height), round((crop.x + crop.width) * image.width), round((crop.y + crop.height) * image.height))
        if box[2] <= box[0] or box[3] <= box[1]:
            fail(422, 'invalid_crop', '裁剪范围太小')
        image = image.crop(box)
    image = image.rotate(-data.rotation, expand=True)
    image = ImageEnhance.Brightness(image).enhance(data.brightness)
    image = ImageEnhance.Contrast(image).enhance(data.contrast)
    image = ImageEnhance.Color(image).enhance(data.saturation)
    alpha = image.getchannel('A')
    if data.filter == 'grayscale':
        image = ImageOps.grayscale(image).convert('RGBA')
    elif data.filter == 'sepia':
        image = ImageOps.colorize(ImageOps.grayscale(image), '#38281f', '#fff2c7').convert('RGBA')
    elif data.filter in {'warm', 'cool'}:
        red, green, blue, _ = image.split()
        red = red.point(lambda x: min(255, int(x * (1.08 if data.filter == 'warm' else .94))))
        blue = blue.point(lambda x: min(255, int(x * (.94 if data.filter == 'warm' else 1.08))))
        from PIL import Image
        image = Image.merge('RGBA', (red, green, blue, alpha))
    image.putalpha(alpha)
    stored = storage.store_image(storage.encode(image), keep_original=False)
    if data.save_as_copy or source.user_id != user.id:
        asset = m.Asset(user_id=user.id, title=source.title + ' · 编辑', category=source.category, source=source.source,
                        original_asset_id=source.original_asset_id or source.id, is_mock=source.is_mock, **stored)
        asset.original_key = source.original_key
        db.add(asset)
    else:
        asset = source
        asset.history = asset.history + [{'version': asset.version, 'key': asset.key, 'thumbnail_key': asset.thumbnail_key, 'edited_at': m.now(), 'parameters': data.model_dump()}]
        asset.key, asset.thumbnail_key = stored['key'], stored['thumbnail_key']
        asset.width, asset.height = image.width, image.height
        asset.version += 1
    db.commit()
    return svc.asset_json(db, asset, user)


@api.post('/exports')
async def export_upload(file: UploadFile = File(...), project_id: str = Form(...), operation_id: str = Form(..., max_length=150), reference_only: bool = Form(False), user=Depends(current_user), db: Session = Depends(get_db)):
    project = owned(db, m.Project, project_id, user)
    previous = svc.operation_get(db, user, 'export', operation_id, m.Asset)
    if previous:
        return svc.asset_json(db, previous, user)
    content = await receive_image(file)
    stored = storage.store_image(content, keep_original=False)
    if content[:2] == b'\xff\xd8':
        converted = storage.image_bytes(content).convert('RGB')
        output = io.BytesIO()
        converted.save(output, 'JPEG', quality=95)
        stored['key'] = storage.put(output.getvalue(), '.jpg')
        stored['original_key'] = stored['key']
    asset = m.Asset(user_id=user.id, title=project.title, category='environment', source='ai_reference' if reference_only else 'export', **stored)
    db.add(asset)
    svc.operation_add(db, user, 'export', operation_id, asset)
    if not reference_only:
        project.cover_asset_id = asset.id
    db.commit()
    return svc.asset_json(db, asset, user)
