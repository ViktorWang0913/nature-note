"""Validate editable vector content and bounded canvas rendering parameters."""
import math
import re
from .security import fail

# 参数设置
shapeKinds = {'rectangle', 'square', 'rounded', 'circle', 'ellipse', 'triangle', 'triangleDown',
              'diamond', 'pentagon', 'hexagon', 'hexagonPoint', 'star', 'line', 'arrow', 'doubleArrow'}
lineKinds = {'line', 'arrow', 'doubleArrow'}


def Number(value, minimum, maximum):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def Color(value, allowNone=False):
    return isinstance(value, str) and (bool(re.fullmatch(r'#[0-9a-fA-F]{6}', value)) or (allowNone and value == 'none'))


def ValidateOpacity(element):
    print('[开始] 不透明度检查')
    if not Number(element.get('opacity', 1), 0, 1) or (element['id'] == 'background' and element.get('opacity', 1) != 1):
        print('[分支] 不透明度无效；[结束] 不透明度检查，提前结束')
        fail(422, 'invalid_opacity', '不透明度须在 0% 至 100% 之间，生成背景保持不透明')
    print('[分支] 不透明度有效；[结束] 不透明度检查')


def ValidatePoints(points, minimum, maximum):
    print('[开始] 笔迹坐标校验')
    if not isinstance(points, list) or not minimum <= len(points) <= maximum:
        print('[分支] 坐标数量无效；[结束] 笔迹坐标校验，提前结束')
        fail(422, 'invalid_drawing', '笔迹坐标数量超出范围')
    print('[分支] 校验坐标；[结束] 笔迹坐标校验')
    print('[开始] 坐标循环')
    for pointIndex, point in enumerate(points, 1):
        print(f'[开始] 坐标 {pointIndex}/{len(points)}')
        print('[开始] 坐标范围')
        if not isinstance(point, dict) or not Number(point.get('x'), 0, 1) or not Number(point.get('y'), 0, 1):
            print('[分支] 非法坐标；[结束] 坐标范围；[结束] 坐标；[结束] 坐标循环，提前结束')
            fail(422, 'invalid_drawing', '笔迹坐标须在图层范围内')
        print('[分支] 坐标有效；[结束] 坐标范围')
        print(f'[结束] 坐标 {pointIndex}/{len(points)}')
    print('[结束] 坐标循环')


def ValidateDrawing(element):
    print('[开始] 绘图类型')
    if element['type'] == 'stroke':
        print('[分支] 自由笔画')
        stroke = element.get('stroke')
        print('[开始] 笔刷参数')
        if not isinstance(stroke, dict) or stroke.get('brush') not in {'pen', 'marker', 'dot'} or not Color(stroke.get('color')) or not Number(stroke.get('lineWidth'), 1, 80) or not Number(stroke.get('baseWidth'), 1, 10000) or not Number(stroke.get('baseHeight'), 1, 10000):
            print('[分支] 笔刷无效；[结束] 笔刷参数；[结束] 绘图类型，提前结束')
            fail(422, 'invalid_drawing', '画笔参数无效')
        print('[分支] 笔刷有效；[结束] 笔刷参数')
        ValidatePoints(stroke.get('points'), 1, 2048)
    else:
        print('[分支] 标准图形')
        shape = element.get('shape')
        print('[开始] 图形样式')
        if not isinstance(shape, dict) or shape.get('kind') not in shapeKinds or not Color(shape.get('fill'), True) or not Color(shape.get('stroke'), True) or not Number(shape.get('lineWidth'), 1, 40) or not Number(shape.get('radius'), 0, 50) or type(shape.get('dashed')) is not bool or type(shape.get('lockRatio')) is not bool or (shape['fill'] == 'none' and shape['stroke'] == 'none'):
            print('[分支] 样式无效；[结束] 图形样式；[结束] 绘图类型，提前结束')
            fail(422, 'invalid_drawing', '图形样式无效，填充和描边不能同时为空')
        print('[分支] 图形样式有效；[结束] 图形样式')
        print('[开始] 线条端点')
        if shape['kind'] in lineKinds:
            print('[分支] 检查两个端点')
            ValidatePoints(shape.get('points'), 2, 2)
            print('[开始] 线条颜色')
            if shape['stroke'] == 'none':
                print('[分支] 缺少线条颜色；[结束] 线条颜色；[结束] 线条端点；[结束] 绘图类型，提前结束')
                fail(422, 'invalid_drawing', '线条必须有描边颜色')
            print('[分支] 线条可见；[结束] 线条颜色')
        else:
            print('[分支] 封闭图形')
        print('[结束] 线条端点')
    print('[结束] 绘图类型')
