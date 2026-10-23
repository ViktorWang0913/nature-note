"""Validate editable notebooks without accepting remote URLs or private foreign assets."""
import re
import math
from copy import deepcopy
from . import models as m, services as svc
from .security import fail


def Validate(db, layout, user, project):
    retainedIds = svc.ProjectAssetIds(project)
    svc.validate_layout(db, layout, user, retainedIds)
    manualDesign = project.layout.get('designMode') == 'manual'
    print('[开始] 设计模式检查')
    if (layout.get('designMode') == 'manual') != manualDesign or not re.fullmatch(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?', str(layout.get('background', ''))):
        print('[分支] 模式或背景颜色无效；[结束] 设计模式检查，提前结束')
        fail(422, 'invalid_design_mode', '设计模式不可更改，背景须为有效颜色')
    print('[分支] 保留作品模式；[结束] 设计模式检查')
    print('[开始] 新版笔记结构检查')
    if layout.get('notebookVersion') != 1 or (not manualDesign and (layout['width'] != 1024 or layout['height'] != 1536)) or (manualDesign and (type(layout['width']) is not int or type(layout['height']) is not int or not 100 <= layout['width'] <= 4096 or not 100 <= layout['height'] <= 4096)) or not (0 if manualDesign else 1) <= len(layout['elements']) <= 200:
        print('[分支] 画布结构无效；[结束] 新版笔记结构检查，提前结束')
        fail(422, 'invalid_notebook', '请使用新版竖版自然笔记')
    print('[分支] 新版竖版画布；[结束] 新版笔记结构检查')
    background = next((element for element in layout['elements'] if element['id'] == 'background'), {})
    task = db.get(m.Task, layout.get('backgroundTaskId', ''))
    print('[开始] 背景来源检查')
    if manualDesign:
        print('[分支] 手动画板不需要生成任务')
        print('[开始] 手动画板背景检查')
        if background or layout.get('backgroundTaskId'):
            print('[分支] 禁止伪造生成背景；[结束] 手动画板背景检查，提前结束')
            fail(422, 'invalid_background', '手动画板使用独立背景颜色')
        print('[分支] 空白或彩色画板；[结束] 手动画板背景检查')
    elif not task or task.user_id != user.id or task.input.get('project_id') != project.id or task.input.get('mode') != 'background-v1' or task.status != 'succeeded' or task.saved_asset_id != background.get('asset_id') or not task.saved_asset_id or any(background.get(key) != value for key, value in {'type': 'image', 'x': 0, 'y': 0, 'width': 1024, 'height': 1536, 'rotation': 0, 'z': 0}.items()):
        print('[分支] 背景不可用；[结束] 背景来源检查，提前结束')
        fail(422, 'invalid_background', '背景必须来自本笔记已完成的生成任务')
    print('[分支] 背景有效且固定；[结束] 背景来源检查')
    result = deepcopy(layout)
    assetIds = []
    print(f"[开始] 排版元素校验，共 {len(result['elements'])} 项")
    for elementIndex, element in enumerate(result['elements'], 1):
        print(f"[开始] 元素 {elementIndex}/{len(result['elements'])}")
        print('[开始] 元素尺寸与类型检查')
        if element['type'] not in {'image', 'text', 'stroke', 'shape'} or element.get('parent_id') or not 1 <= element['width'] <= 10000 or not 1 <= element['height'] <= 10000 or (element['id'] != 'background' and element['z'] <= 0):
            print('[分支] 元素无效；[结束] 元素尺寸与类型检查，提前结束校验')
            fail(422, 'invalid_element', '排版元素格式无效')
        print('[分支] 元素有效；[结束] 元素尺寸与类型检查')
        from .drawing import ValidateOpacity
        ValidateOpacity(element)
        element.pop('url', None)
        print('[开始] 素材或文字校验')
        if element['type'] == 'image':
            print('[分支] 图片必须是可访问的公共或生成素材')
            ValidateImageEdit(element)
            asset = svc.asset_access(db, element.get('asset_id'), user, retainedIds)
            print('[开始] 图片来源检查')
            if element['id'] != 'background' and ((not manualDesign and asset.user_id is not None and asset.source != 'generated') or (manualDesign and asset.source in {'ai_reference', 'notebook_background'})):
                print('[分支] 禁止原始照片；[结束] 图片来源检查，提前结束校验')
                fail(422, 'invalid_material', '请选择生成素材或公共素材')
            print('[分支] 素材来源正确；[结束] 图片来源检查')
            assetIds.append(asset.id)
        elif element['type'] in {'stroke', 'shape'}:
            print('[分支] 校验可编辑笔迹与图形')
            from .drawing import ValidateDrawing
            ValidateDrawing(element)
        else:
            print('[分支] 校验有限文字样式')
            fontSize = element.get('fontSize', 42)
            print('[开始] 文字样式边界检查')
            if not isinstance(element.get('text'), str) or len(element['text']) > 2000 or not isinstance(fontSize, (int, float)) or not 8 <= fontSize <= 240 or element.get('fontFamily', 'sans-serif') not in {'sans-serif', 'serif', 'monospace'} or element.get('fontWeight', 'normal') not in {'normal', 'bold'} or element.get('textAlign', 'left') not in {'left', 'center', 'right'} or not re.fullmatch(r'#[0-9a-fA-F]{6}', element.get('color', '#253d32')) or not re.fullmatch(r'(transparent|#[0-9a-fA-F]{6})', element.get('textBackground', 'transparent')):
                print('[分支] 样式无效；[结束] 文字样式边界检查，提前结束校验')
                fail(422, 'invalid_text', '文字内容或样式超出范围')
            print('[分支] 文字样式有效；[结束] 文字样式边界检查')
        print('[结束] 素材或文字校验')
        print('[开始] 元素变换属性检查')
        if any(type(element.get(fieldName, False)) is not bool for fieldName in ('locked', 'flipX', 'flipY')):
            print('[分支] 变换属性无效；[结束] 元素变换属性检查，提前结束')
            fail(422, 'invalid_element', '锁定和翻转须为布尔值')
        print('[分支] 变换属性有效；[结束] 元素变换属性检查')
        print(f"[结束] 元素 {elementIndex}/{len(result['elements'])}")
    print('[结束] 排版元素校验')
    return result, sorted(set(assetIds))


def ValidateImageEdit(element):
    print('[开始] 画布图片调整校验')
    if 'imageEdit' not in element:
        print('[分支] 原始素材；[结束] 画布图片调整校验，提前结束')
        return
    print('[分支] 校验可恢复的调整参数；[结束] 画布图片调整校验')
    imageEdit = element['imageEdit']
    limits = {'cropX': (0, 90), 'cropY': (0, 90), 'cropW': (10, 100), 'cropH': (10, 100),
              'brightness': (0, 200), 'contrast': (0, 200), 'saturation': (0, 200)}
    print('[开始] 调整字段结构')
    if element['id'] == 'background' or not isinstance(imageEdit, dict) or set(imageEdit) != set(limits) | {'filter'}:
        print('[分支] 无效调整字段；[结束] 调整字段结构，提前结束')
        fail(422, 'invalid_image_edit', '素材调整参数无效，背景不可修改')
    print('[分支] 调整字段完整；[结束] 调整字段结构')
    print('[开始] 调整数值范围')
    for fieldIndex, (fieldName, (minimum, maximum)) in enumerate(limits.items(), 1):
        print(f'[开始] 调整字段 {fieldIndex}/{len(limits)}：{fieldName}')
        fieldValue = imageEdit[fieldName]
        print('[开始] 数值有效性')
        if type(fieldValue) not in (int, float) or not math.isfinite(fieldValue) or not minimum <= fieldValue <= maximum:
            print('[分支] 数值无效；[结束] 数值有效性；[结束] 调整字段；[结束] 调整数值范围，提前结束')
            fail(422, 'invalid_image_edit', '素材调整数值超出范围')
        print('[分支] 数值有效；[结束] 数值有效性')
        print(f'[结束] 调整字段 {fieldIndex}/{len(limits)}')
    print('[结束] 调整数值范围')
    print('[开始] 裁剪与滤镜检查')
    if imageEdit['cropX'] + imageEdit['cropW'] > 100 or imageEdit['cropY'] + imageEdit['cropH'] > 100 or imageEdit['filter'] not in ['none', 'warm', 'cool', 'grayscale']:
        print('[分支] 裁剪或滤镜无效；[结束] 裁剪与滤镜检查，提前结束')
        fail(422, 'invalid_image_edit', '裁剪范围或滤镜无效')
    print('[分支] 裁剪与滤镜有效；[结束] 裁剪与滤镜检查')
