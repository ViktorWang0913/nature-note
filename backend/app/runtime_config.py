"""Database runtime configuration; encrypted credentials and per-task snapshots."""
import base64
import hashlib
from cryptography.fernet import Fernet
from .config import settings
from . import models as m


def Cipher():
    digest = hashlib.sha256(('nature-runtime-v1:' + settings().secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def Encode(values):
    return dict(values, api_key=Cipher().encrypt(values['api_key'].encode()).decode())


def Decode(values):
    return dict(values, api_key=Cipher().decrypt(values['api_key'].encode()).decode())


def ReadProvider(db, providerId):
    record = db.get(m.PlatformControl, 'runtime:' + providerId, populate_existing=True)
    print('[开始] 服务配置来源')
    if record:
        print('[分支] 数据库实时配置；[结束] 服务配置来源')
        return Decode(record.value)
    else:
        print('[分支] 初始环境配置；[结束] 服务配置来源')
    prefix = {'image': 'image', 'qwen': 'multimodal'}[providerId]
    cfg = settings()
    return {'base_url': getattr(cfg, prefix + '_api_base_url').strip().rstrip('/'),
            'model': getattr(cfg, prefix + '_api_model').strip(),
            'api_key': getattr(cfg, prefix + '_api_key').strip(), 'revision': 0}


def Snapshot(db, task, values):
    db.add(m.PlatformControl(id='task-api:' + task.id, value=Encode(values)))


def ReadTaskProvider(db, task, providerId):
    record = db.get(m.PlatformControl, 'task-api:' + task.id)
    print('[开始] 任务配置快照检查')
    if record:
        print('[分支] 使用提交时配置；[结束] 任务配置快照检查')
        return Decode(record.value)
    else:
        print('[分支] 历史任务使用原环境凭据及账单模型；[结束] 任务配置快照检查')
    # Legacy tasks predate runtime editing. They must never switch to a new admin key.
    prefix = {'image': 'image', 'qwen': 'multimodal'}[providerId]
    charge = db.get(m.Charge, task.id)
    pricing = charge.pricing if charge else {}
    cfg = settings()
    return {'base_url': pricing.get('base_url', getattr(cfg, prefix + '_api_base_url')),
            'model': pricing.get('model', getattr(cfg, prefix + '_api_model')),
            'api_key': getattr(cfg, prefix + '_api_key')}


def ReadMap(db):
    record = db.get(m.PlatformControl, 'runtime:map', populate_existing=True)
    print('[开始] 地图配置来源')
    if record:
        print('[分支] 管理员配置；[结束] 地图配置来源')
        return record.value
    else:
        print('[分支] 初始环境配置；[结束] 地图配置来源')
        return {'map_key': settings().tencent_map_web_key.strip(), 'revision': 0}
