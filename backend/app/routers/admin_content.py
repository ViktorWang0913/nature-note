"""Read-only administrator views of users, generated images and saved designs."""
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_, literal

from .. import models as models, services, storage, billing
from ..admin_security import Admin, Audit
from ..db import get_db
from ..security import fail

# 路径与参数设置
api = APIRouter(prefix='/api/admin', tags=['admin-content'])
modelTypes = {'users': models.User, 'tasks': models.Task, 'generated': models.Task,
              'assets': models.Asset, 'projects': models.Project}
beijingZone = timezone(timedelta(hours=8))


def MediaUrl(kind, itemId, **parameters):
    return '/api/admin/content-media/' + kind + '/' + itemId + '?' + urlencode(parameters)


def UserInfo(database, userId):
    print('[开始] 内容作者类型')
    if userId is None:
        print('[分支] 公共素材；[结束] 内容作者类型，提前返回')
        return {'id': None, 'name': '公共素材', 'username': ''}
    print('[分支] 用户内容；[结束] 内容作者类型')
    user = database.get(models.User, userId)
    credential = database.scalar(select(models.WebCredential).where(models.WebCredential.user_id == userId))
    return {'id': userId, 'name': getattr(user, 'name', '未知用户'),
            'username': getattr(credential, 'username', '')}


def ChargeInfo(database, taskId):
    charge = database.get(models.Charge, taskId)
    print('[开始] 任务费用读取')
    if charge is None:
        print('[分支] 无费用记录；[结束] 任务费用读取，提前返回')
        return None
    print('[分支] 读取账面费用，不推断服务商余额；[结束] 任务费用读取')
    return {'task_id': taskId, 'state': charge.state, 'provider_id': charge.provider_id,
            'actual_micros': charge.actual_micros, 'reserved_micros': charge.reserved_micros,
            'model': charge.pricing.get('model'), 'evidence': charge.evidence}


def ContentRow(database, section, record):
    result = {'id': record.id, 'created_at': record.created_at,
              'updated_at': getattr(record, 'updated_at', record.created_at)}
    print('[开始] 内容列表记录类型')
    if section == 'users':
        print('[分支] 用户资料')
        result.update(UserInfo(database, record.id), active=record.active, deleted_at=record.deleted_at,
                      last_seen_at=record.last_seen_at)
    else:
        print('[分支] 用户创作内容')
        result.update(user_id=record.user_id, user=UserInfo(database, record.user_id))
        print('[开始] 创作内容类型')
        if section in {'tasks', 'generated'}:
            print('[分支] 生成任务')
            taskResult = record.result or {}
            result.update(kind=record.kind, status=record.status,
                          title=str(record.input.get('prompt') or record.input.get('question') or '图片任务')[:100],
                          saved_asset_id=record.saved_asset_id, is_mock=record.is_mock,
                          charge=ChargeInfo(database, record.id))
            print('[开始] 任务成图检查')
            if record.status == 'succeeded' and taskResult.get('image_key'):
                print('[分支] 提供受管理会话保护的成图')
                result['image_url'] = MediaUrl('task', record.id)
                result['thumbnail_url'] = MediaUrl('task', record.id, preview=1)
            else:
                print('[分支] 尚无成功成图')
            print('[结束] 任务成图检查')
        elif section == 'assets':
            print('[分支] 用户素材')
            result.update(title=record.title, source=record.source, width=record.width, height=record.height,
                          original_asset_id=record.original_asset_id,
                          image_url=MediaUrl('asset', record.id),
                          thumbnail_url=MediaUrl('asset', record.id, preview=1))
        else:
            print('[分支] 已保存作品')
            result.update(title=record.title, version=record.version,
                          design_mode=record.layout.get('designMode', 'notebook'),
                          width=record.layout.get('width'), height=record.layout.get('height'))
        print('[结束] 创作内容类型')
    print('[结束] 内容列表记录类型')
    return result


def ListGenerated(database, keyword, userId, start, end, cursor):
    """Retain independently saved images even when their generation history is deleted."""
    taskRows = select(models.Task.id.label('id'), models.Task.user_id.label('user_id'),
                      models.Task.created_at.label('created_at'), literal('tasks').label('record_section'),
                      models.Task.input['prompt'].as_string().label('title')).where(
        models.Task.deleted == False, models.Task.status == 'succeeded',
        models.Task.kind.in_(['image_generation', 'image_polish']),
        models.Task.result['image_key'].as_string().is_not(None))
    linkedTask = select(models.Task.id).where(models.Task.saved_asset_id == models.Asset.id,
        models.Task.deleted == False, models.Task.status == 'succeeded',
        models.Task.kind.in_(['image_generation', 'image_polish']),
        models.Task.result['image_key'].as_string().is_not(None)).exists()
    assetRows = select(models.Asset.id.label('id'), models.Asset.user_id.label('user_id'),
                       models.Asset.created_at.label('created_at'), literal('assets').label('record_section'),
                       models.Asset.title.label('title')).where(models.Asset.deleted == False,
        models.Asset.source.in_(['generated', 'notebook_background']), ~linkedTask)
    contents = taskRows.union_all(assetRows).subquery()
    query = select(contents).join(models.User, models.User.id == contents.c.user_id).outerjoin(
        models.WebCredential, models.WebCredential.user_id == contents.c.user_id).where(models.User.deleted_at.is_(None))
    print('[开始] 生成图片搜索')
    if keyword:
        print('[分支] 查找图片标题、账号、昵称和编号')
        query = query.where(or_(contents.c.title.contains(keyword, autoescape=True),
            contents.c.id.contains(keyword, autoescape=True), models.User.name.contains(keyword, autoescape=True),
            models.WebCredential.username.contains(keyword, autoescape=True)))
    else:
        print('[分支] 不限制关键词')
    print('[结束] 生成图片搜索')
    print('[开始] 生成图片用户范围')
    if userId:
        print('[分支] 指定用户')
        query = query.where(contents.c.user_id == userId)
    else:
        print('[分支] 全部用户')
    print('[结束] 生成图片用户范围')
    print('[开始] 生成图片日期范围')
    if start:
        print('[分支] 起始日期')
        query = query.where(contents.c.created_at >= datetime.combine(start, time.min, beijingZone).astimezone(timezone.utc).isoformat())
    else:
        print('[分支] 无起始限制')
    print('[结束] 生成图片日期范围')
    print('[开始] 生成图片结束日期')
    if end:
        print('[分支] 结束日期')
        query = query.where(contents.c.created_at < datetime.combine(end + timedelta(days=1), time.min, beijingZone).astimezone(timezone.utc).isoformat())
    else:
        print('[分支] 无结束限制')
    print('[结束] 生成图片结束日期')

    def SerializeImage(row):
        record = database.get(modelTypes[row.record_section], row.id)
        result = ContentRow(database, row.record_section, record)
        result['record_section'] = row.record_section
        print('[开始] 独立保存图片标识')
        if row.record_section == 'assets':
            print('[分支] 原任务历史已移除，仍可查看独立素材')
            result['saved_asset_id'] = record.id
        else:
            print('[分支] 关联生成任务')
        print('[结束] 独立保存图片标识')
        return result

    return services.page(database, query.order_by(contents.c.created_at.desc(), contents.c.id,
                          contents.c.record_section), SerializeImage, cursor, limit=18, rows=True)


@api.get('/explorer/{section}')
def ListContent(section: str, q: str = Query('', max_length=100),
                user_id: str = '', status: str = '', source: str = '',
                start: date | None = None, end: date | None = None,
                cursor: str | None = None, admin=Depends(Admin), database=Depends(get_db)):
    print('[开始] 日期范围校验')
    if start and end and start > end:
        print('[分支] 开始日期晚于结束日期；[结束] 日期范围校验，提前结束')
        fail(422, 'invalid_date_range', '开始日期不能晚于结束日期')
    print('[分支] 日期范围有效；[结束] 日期范围校验')
    print('[开始] 管理内容模块检查')
    if section not in modelTypes:
        print('[分支] 模块不存在；[结束] 管理内容模块检查，提前结束')
        fail(404, 'not_found', '内容模块不存在')
    print('[分支] 支持的内容模块；[结束] 管理内容模块检查')
    print('[开始] 合并生成结果与独立保存素材')
    if section == 'generated':
        print('[分支] 统一分页并去重；[结束] 合并生成结果与独立保存素材，提前返回')
        return ListGenerated(database, q, user_id, start, end, cursor)
    print('[分支] 普通内容列表；[结束] 合并生成结果与独立保存素材')
    model = modelTypes[section]
    print('[开始] 用户与内容查询')
    if section == 'users':
        print('[分支] 包含停用与注销账号，便于管理')
        query = select(model).outerjoin(models.WebCredential, models.WebCredential.user_id == model.id)
        ownerColumn = model.id
        nameColumn = model.name
    else:
        print('[分支] 仅列出未删除的用户内容')
        query = select(model).join(models.User, models.User.id == model.user_id).outerjoin(
            models.WebCredential, models.WebCredential.user_id == model.user_id).where(
            model.deleted == False, models.User.deleted_at.is_(None))
        ownerColumn = model.user_id
        nameColumn = models.User.name
    print('[结束] 用户与内容查询')
    print('[开始] 模块范围筛选')
    if section == 'assets':
        print('[分支] 上传与编辑素材，不混入生成结果和隐藏参考副本')
        query = query.where(model.source.not_in(['generated', 'notebook_background', 'ai_reference', 'public']))
    else:
        print('[分支] 保留模块全部记录')
    print('[结束] 模块范围筛选')
    print('[开始] 搜索与过滤')
    if q:
        print('[分支] 按账号、名称、标题或编号搜索')
        textColumn = getattr(model, 'title', model.id)
        query = query.where(or_(model.id.contains(q, autoescape=True), nameColumn.contains(q, autoescape=True),
                                models.WebCredential.username.contains(q, autoescape=True),
                                textColumn.contains(q, autoescape=True)))
    else:
        print('[分支] 无关键词')
    print('[结束] 搜索与过滤')
    print('[开始] 所属用户筛选')
    if user_id:
        print('[分支] 当前用户')
        query = query.where(ownerColumn == user_id)
    else:
        print('[分支] 全部用户')
    print('[结束] 所属用户筛选')
    print('[开始] 状态筛选')
    if status and section == 'tasks':
        print('[分支] 任务状态')
        query = query.where(model.status == status)
    elif source and section == 'assets':
        print('[分支] 素材来源')
        query = query.where(model.source == source)
    else:
        print('[分支] 不限制状态')
    print('[结束] 状态筛选')
    dateColumn = getattr(model, 'updated_at', model.created_at)
    print('[开始] 日期下限')
    if start:
        print('[分支] 北京时间起始日期')
        query = query.where(dateColumn >= datetime.combine(start, time.min, beijingZone).astimezone(timezone.utc).isoformat())
    else:
        print('[分支] 不限制起始日期')
    print('[结束] 日期下限')
    print('[开始] 日期上限')
    if end:
        print('[分支] 包含北京时间结束日期')
        query = query.where(dateColumn < datetime.combine(end + timedelta(days=1), time.min, beijingZone).astimezone(timezone.utc).isoformat())
    else:
        print('[分支] 不限制结束日期')
    print('[结束] 日期上限')
    return services.page(database, query.order_by(dateColumn.desc(), model.id),
                         lambda record: ContentRow(database, section, record), cursor, limit=18)


@api.get('/explorer/{section}/{itemId}')
def ContentDetail(section: str, itemId: str, admin=Depends(Admin), database=Depends(get_db)):
    print('[开始] 详情类型检查')
    if section not in modelTypes:
        print('[分支] 类型不存在；[结束] 详情类型检查，提前结束')
        fail(404, 'not_found', '内容不存在')
    print('[分支] 已知类型；[结束] 详情类型检查')
    record = database.get(modelTypes[section], itemId)
    print('[开始] 详情有效性')
    if record is None or getattr(record, 'deleted', False):
        print('[分支] 内容不存在或已删除；[结束] 详情有效性，提前结束')
        fail(404, 'not_found', '内容不存在或已删除')
    print('[分支] 内容仍存在；[结束] 详情有效性')
    result = ContentRow(database, section, record)
    print('[开始] 内容所属账号检查')
    if section != 'users' and record.user_id and getattr(database.get(models.User, record.user_id), 'deleted_at', None):
        print('[分支] 账号已注销；[结束] 内容所属账号检查，提前结束')
        fail(404, 'not_found', '所属账号已注销，请通过删除归档查看')
    print('[分支] 可以查看；[结束] 内容所属账号检查')
    print('[开始] 详情字段补充')
    if section == 'projects':
        print('[分支] 复用完整已保存画布，所有图片改用受保护的管理接口')
        layout = deepcopy(record.layout)
        elements = layout.get('elements', [])
        print(f'[开始] 作品图片链接，共 {len(elements)} 项')
        for elementIndex, element in enumerate(elements, 1):
            print(f'[开始] 元素 {elementIndex}/{len(elements)}')
            element.pop('url', None)
            print('[开始] 图片元素检查')
            if element.get('type') == 'image' and element.get('asset_id'):
                print('[分支] 绑定作品版本及关联素材')
                element['url'] = MediaUrl('project', itemId, asset_id=element['asset_id'], version=record.version)
            else:
                print('[分支] 非图片元素')
            print('[结束] 图片元素检查')
            print(f'[结束] 元素 {elementIndex}/{len(elements)}')
        print('[结束] 作品图片链接')
        result['layout'] = layout
    elif section in {'tasks', 'generated'}:
        print('[分支] 展示输入、结果、异常及费用，排除内部密钥配置')
        result.update(prompt=str(record.input.get('prompt') or record.input.get('question') or ''),
                      error=record.error, answer=(record.result or {}).get('answer') or (record.result or {}).get('text'),
                      upstream_id=(record.result or {}).get('provider_task_id') or (record.result or {}).get('_upstream_task_id'),
                      project_id=record.input.get('project_id'), references=[])
        referenceIds = list(dict.fromkeys([record.input.get('asset_id')] + list(record.input.get('asset_ids') or [])))
        print(f'[开始] 参考图核对，共 {len(referenceIds)} 项')
        for referenceIndex, referenceId in enumerate(referenceIds, 1):
            print(f'[开始] 参考图 {referenceIndex}/{len(referenceIds)}')
            asset = database.get(models.Asset, referenceId or '')
            print('[开始] 参考归属检查')
            if asset and not asset.deleted and asset.user_id in {None, record.user_id}:
                print('[分支] 同用户或公共参考图')
                result['references'].append({'id': asset.id, 'title': asset.title, 'url': MediaUrl('asset', asset.id)})
            else:
                print('[分支] 参考图已移除或不可用')
            print('[结束] 参考归属检查')
            print(f'[结束] 参考图 {referenceIndex}/{len(referenceIds)}')
        print('[结束] 参考图核对')
        # Existing tasks lack reliable execution-start timestamps; do not fabricate queue duration.
        result['timing_note'] = '提交与最后更新时间可查；历史记录未记录精确开始时间，暂不拆分排队与处理耗时。'
        print('[开始] 已结束任务耗时')
        if record.status in {'succeeded', 'failed'}:
            print('[分支] 提交至最终状态更新的总时长')
            result['duration_seconds'] = round(max(0, (datetime.fromisoformat(record.updated_at) -
                                                       datetime.fromisoformat(record.created_at)).total_seconds()), 1)
        else:
            print('[分支] 任务尚未完成或已取消，不推断最终耗时')
        print('[结束] 已结束任务耗时')
    elif section == 'users':
        print('[分支] 账户创作数量及今日已有额度，不创建新预算')
        result['counts'] = {}
        print('[开始] 用户内容计数，共 3 项')
        for countIndex, (label, countModel) in enumerate(
                [('tasks', models.Task), ('assets', models.Asset), ('projects', models.Project)], 1):
            print(f'[开始] 计数 {countIndex}/3')
            result['counts'][label] = database.scalar(select(func.count()).select_from(countModel).where(
                countModel.user_id == itemId, countModel.deleted == False))
            print(f'[结束] 计数 {countIndex}/3')
        print('[结束] 用户内容计数')
        result['budgets'] = []
        budgets = database.scalars(select(models.DailyBudget).where(models.DailyBudget.identity_key == billing.Identity(record),
                                                                  models.DailyBudget.day == billing.Day())).all()
        print(f'[开始] 今日额度，共 {len(budgets)} 项')
        for budgetIndex, budget in enumerate(budgets, 1):
            print(f'[开始] 额度 {budgetIndex}/{len(budgets)}')
            result['budgets'].append({'provider_id': budget.provider_id, 'limit_micros': budget.limit_micros,
                                     'held_micros': budget.held_micros, 'spent_micros': budget.spent_micros})
            print(f'[结束] 额度 {budgetIndex}/{len(budgets)}')
        print('[结束] 今日额度')
    else:
        print('[分支] 素材信息已完整')
    print('[结束] 详情字段补充')
    Audit(database, admin.id, 'content_viewed', itemId, {'kind': section})
    database.commit()
    return result


@api.get('/content-media/{kind}/{itemId}')
def ContentMedia(kind: str, itemId: str, asset_id: str = '', version: int | None = None,
                 preview: bool = False, admin=Depends(Admin), database=Depends(get_db)):
    key = ''
    ownerId = None
    print('[开始] 管理图片授权')
    if kind == 'task':
        print('[分支] 未删除的成功任务')
        task = database.get(models.Task, itemId)
        print('[开始] 任务图片检查')
        if task and not task.deleted and task.status == 'succeeded':
            print('[分支] 读取任务结果')
            key = (task.result or {}).get('image_key', '')
            ownerId = task.user_id
        else:
            print('[分支] 无可用结果')
        print('[结束] 任务图片检查')
    elif kind == 'project':
        print('[分支] 校验已保存作品的图片引用')
        project = database.get(models.Project, itemId)
        asset = database.get(models.Asset, asset_id)
        print('[开始] 作品图片归属与版本')
        if project and not project.deleted and asset and asset.id in services.ProjectAssetIds(project) and asset.user_id in {None, project.user_id} and version == project.version:
            print('[分支] 允许读取当前作品保留的素材')
            key, ownerId = asset.key, project.user_id
        else:
            print('[分支] 作品已更新、素材无引用或归属不符')
        print('[结束] 作品图片归属与版本')
    elif kind == 'asset':
        print('[分支] 未删除素材')
        asset = database.get(models.Asset, itemId)
        print('[开始] 素材存在检查')
        if asset and not asset.deleted:
            print('[分支] 当前素材')
            key, ownerId = asset.key, asset.user_id
        else:
            print('[分支] 素材已删除')
        print('[结束] 素材存在检查')
    else:
        print('[分支] 未知媒体类型')
    print('[结束] 管理图片授权')
    owner = database.get(models.User, ownerId or '')
    print('[开始] 图片可用范围')
    if not key or (ownerId and (not owner or owner.deleted_at)):
        print('[分支] 图片不可访问；[结束] 图片可用范围，提前结束')
        fail(404, 'media_unavailable', '图片已移除或作品版本已变化，请刷新')
    print('[分支] 已验证管理权限及内容关联；[结束] 图片可用范围')
    Audit(database, admin.id, 'media_viewed', itemId, {'kind': kind, 'preview': preview})
    database.commit()
    headers = {'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'}
    print('[开始] 图片响应尺寸')
    if preview:
        print('[分支] 生成或读取缩略图；[结束] 图片响应尺寸，提前返回')
        return FileResponse(storage.PreviewPath(key), media_type='image/webp', headers=headers)
    print('[分支] 原始图片；[结束] 图片响应尺寸')
    return Response(storage.read(key), media_type='image/jpeg' if key.endswith(('.jpg', '.jpeg')) else 'image/png',
                    headers=headers)
