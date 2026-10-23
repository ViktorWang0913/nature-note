import io
import time
import uuid
import hashlib
from threading import Semaphore
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from PIL import Image, ImageOps
from .config import settings
from .security import sign, fail

Image.MAX_IMAGE_PIXELS = 40_000_000
previewSlots = Semaphore(4)
previewSize = (640, 640)


def local_path(key):
    root = Path(settings().storage_dir).resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root) or '..' in PurePosixPath(key).parts:
        fail(400, 'invalid_file', '文件路径无效')
    return path


def cos():
    from qcloud_cos import CosConfig, CosS3Client
    cfg = settings()
    return CosS3Client(CosConfig(Region=cfg.cos_region, SecretId=cfg.cos_secret_id, SecretKey=cfg.cos_secret_key, Scheme='https'))


def put(data: bytes, suffix='.png', public=False):
    key = ('public/' if public else 'private/') + uuid.uuid4().hex + suffix
    if settings().storage_backend == 'local':
        path = local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    else:
        cos().put_object(Bucket=settings().cos_bucket, Body=data, Key=key, ContentType='image/png' if suffix == '.png' else 'image/jpeg')
    return key


def read(key):
    if settings().storage_backend == 'local':
        return local_path(key).read_bytes()
    return cos().get_object(Bucket=settings().cos_bucket, Key=key)['Body'].get_raw_stream().read()


def Delete(key, allowPublic=False):
    print('[开始] 私有文件删除检查')
    if not key.startswith('private/') and not (allowPublic and key.startswith('public/')):
        print('[分支] 不能从用户清理任务删除公共资源')
        raise ValueError('只能清理用户私有文件')
    else:
        print('[分支] 私有文件')
    print('[结束] 私有文件删除检查')
    print('[开始] 文件后端选择')
    if settings().storage_backend == 'local':
        print('[分支] 删除工作目录内已验证的单个文件')
        local_path(key).unlink(missing_ok=True)
    else:
        print('[分支] 删除私有 COS 对象')
        cos().delete_object(Bucket=settings().cos_bucket, Key=key)
    print('[结束] 文件后端选择')


def url(key, resourceType='', resourceId='', preview=False):
    if not key:
        return ''
    expires = int(time.time()) // 1800 * 1800 + 3600
    payload = key + ':' + str(expires) + ':' + resourceType + ':' + resourceId
    variant = ':preview' * bool(preview)
    return f'{settings().public_base_url}/api/v1/files/{quote(key)}?expires={expires}&resource_type={quote(resourceType)}&resource_id={quote(resourceId)}&preview={int(preview)}&signature={sign(payload + variant)}'


def PreviewPath(key):
    # 原图键不可变；尺寸与编码版本包含在缓存键中，编辑图片后自动换键。
    cacheKey = hashlib.sha256(('webp-640-v1:' + key).encode()).hexdigest()
    cachePath = local_path('_previews/' + cacheKey + '.webp')
    print('[开始] 已有预览快速读取')
    if cachePath.exists():
        print('[分支] 命中缓存，不等待其他图片转换；[结束] 已有预览快速读取，提前结束')
        return cachePath
    else:
        print('[分支] 尚无预览')
    print('[结束] 已有预览快速读取')
    with previewSlots:
        print('[开始] 预览文件缓存')
        if not cachePath.exists():
            print('[分支] 首次生成小尺寸预览，保留原图')
            image = image_bytes(read(key))
            image.thumbnail(previewSize)
            cachePath.parent.mkdir(parents=True, exist_ok=True)
            tempPath = cachePath.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            image.save(tempPath, 'WEBP', quality=80, method=4)
            tempPath.replace(cachePath)
        else:
            print('[分支] 复用已有预览文件')
        print('[结束] 预览文件缓存')
    return cachePath


def image_bytes(data):
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValueError()
            if original.width * original.height > 40_000_000:
                raise ValueError()
            image = ImageOps.exif_transpose(original).convert('RGBA')
            image.load()
            return image
    except Exception:
        fail(422, 'invalid_image', '请选择有效的 JPG、PNG 或 WebP 图片（最高 4000 万像素）')


def encode(image):
    stream = io.BytesIO()
    image.save(stream, 'PNG')
    return stream.getvalue()


def store_image(data, public=False, keep_original=True):
    image = image_bytes(data)
    key = put(encode(image), public=public)
    original = put(data, '.jpg' if data[:2] == b'\xff\xd8' else '.png', public=False) if keep_original else key
    thumb = image.copy()
    thumb.thumbnail((480, 480))
    return {'key': key, 'original_key': original, 'thumbnail_key': put(encode(thumb), public=public), 'width': image.width, 'height': image.height}
