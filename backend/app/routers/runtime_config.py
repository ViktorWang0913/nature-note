"""Administrator-only runtime settings, never exposing model credentials."""
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, Response
from pydantic import Field
from sqlalchemy import update
from .. import models as m, billing, runtime_config as runtime
from ..db import get_db
from ..schemas import Input
from ..security import fail
from ..admin_security import Admin, Audit
from .admin import PricingInput

api = APIRouter(prefix='/api/admin/runtime', tags=['administration'])


class ServiceInput(Input):
    revision: int = Field(ge=0)
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=150)
    api_key: str = Field(default='', max_length=2000)
    pricing: PricingInput


class MapInput(Input):
    revision: int = Field(ge=0)
    map_key: str = Field(max_length=200)


def CheckProvider(providerId):
    print('[开始] 服务类型检查')
    if providerId not in {'image', 'qwen'}:
        print('[分支] 未知服务；[结束] 服务类型检查；提前拒绝')
        fail(404, 'not_found', '服务不存在')
    else:
        print('[分支] 有效服务；[结束] 服务类型检查')


def SaveVersion(db, recordId, revision, values):
    # Insert and conditional UPDATE share the transaction with pricing and audit.
    billing.InsertOnce(db, m.PlatformControl, {'id': recordId, 'value': {'revision': 0}})
    changed = db.execute(update(m.PlatformControl).where(m.PlatformControl.id == recordId,
        m.PlatformControl.value['revision'].as_integer() == revision).values(value=values))
    print('[开始] 配置版本检查')
    if changed.rowcount != 1:
        print('[分支] 其他窗口已更新；[结束] 配置版本检查；提前拒绝')
        fail(409, 'config_changed', '配置已被其他窗口更新，请刷新后再保存')
    else:
        print('[分支] 配置版本一致；[结束] 配置版本检查')


@api.get('/services/{providerId}')
def GetService(providerId: str, response: Response, admin=Depends(Admin), db=Depends(get_db)):
    CheckProvider(providerId)
    values = runtime.ReadProvider(db, providerId)
    control = db.get(m.PlatformControl, 'pricing:' + providerId)
    prices = control.value if control else billing.Pricing(db, providerId)
    response.headers['Cache-Control'] = 'no-store'
    return {'base_url': values['base_url'], 'model': values['model'], 'revision': values['revision'],
            'key_configured': bool(values['api_key']), 'pricing': prices,
            'source': 'admin' if values['revision'] else 'env'}


@api.put('/services/{providerId}')
def SaveService(providerId: str, data: ServiceInput, admin=Depends(Admin), db=Depends(get_db)):
    CheckProvider(providerId)
    baseUrl = data.base_url.strip().rstrip('/')
    modelName = data.model.strip()
    parts = urlsplit(baseUrl)
    print('[开始] 服务地址校验')
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or not modelName:
        print('[分支] 地址或模型无效；[结束] 服务地址校验；提前拒绝')
        fail(422, 'invalid_service', '请填写完整模型名及不含密钥、查询参数的 HTTPS API 地址')
    else:
        print('[分支] 服务地址有效；[结束] 服务地址校验')
    prior = runtime.ReadProvider(db, providerId)
    print('[开始] 服务商切换检查')
    if urlsplit(prior['base_url']).netloc != parts.netloc and not data.api_key.strip():
        print('[分支] 更换服务商需提供新密钥；[结束] 服务商切换检查；提前拒绝')
        fail(422, 'new_key_required', '更换服务商地址时请填写该服务商的 API Key')
    else:
        print('[分支] 服务商未变或已提供新密钥；[结束] 服务商切换检查')
    key = data.api_key.strip() or prior['api_key']
    print('[开始] 服务密钥检查')
    if not key:
        print('[分支] 缺少密钥；[结束] 服务密钥检查；提前拒绝')
        fail(422, 'missing_key', '首次配置请填写 API Key')
    else:
        print('[分支] 使用新密钥或保留原值；[结束] 服务密钥检查')
    values = {'base_url': baseUrl, 'model': modelName, 'api_key': key,
              'revision': data.revision + 1, 'updated_at': m.now()}
    SaveVersion(db, 'runtime:' + providerId, data.revision, runtime.Encode(values))
    prices = data.pricing.model_dump(mode='json') | {'model': modelName, 'base_url': baseUrl, 'updated_at': m.now()}
    billing.InsertOnce(db, m.PlatformControl, {'id': 'pricing:' + providerId, 'value': {}})
    db.get(m.PlatformControl, 'pricing:' + providerId).value = prices
    Audit(db, admin.id, 'runtime_service_changed', providerId,
          {'model': modelName, 'base_url': baseUrl, 'revision': values['revision'], 'key_changed': bool(data.api_key.strip())})
    db.commit()
    return {'saved': True, 'revision': values['revision'], 'applies_to': 'new_tasks'}


@api.get('/map')
def GetMap(response: Response, admin=Depends(Admin), db=Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return runtime.ReadMap(db)


@api.put('/map')
def SaveMap(data: MapInput, admin=Depends(Admin), db=Depends(get_db)):
    values = {'map_key': data.map_key.strip(), 'revision': data.revision + 1}
    SaveVersion(db, 'runtime:map', data.revision, values)
    Audit(db, admin.id, 'runtime_map_changed', 'map', {'configured': bool(values['map_key']), 'revision': values['revision']})
    db.commit()
    return {'saved': True, 'revision': values['revision']}
