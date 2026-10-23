from copy import deepcopy
import pytest
from PIL import Image
from app import models, storage
from app.db import SessionLocal

# 参数设置
blankLayout = {'schema_version': 1, 'notebookVersion': 1, 'designMode': 'manual',
               'width': 1080, 'height': 1080, 'background': '#ffffff', 'elements': []}
strokeElement = {'id': 'stroke', 'type': 'stroke', 'x': -10, 'y': 40, 'width': 300, 'height': 200,
                 'rotation': 30, 'z': 1, 'opacity': 0.35, 'locked': True,
                 'stroke': {'brush': 'marker', 'color': '#527c65', 'lineWidth': 28, 'baseWidth': 300,
                            'baseHeight': 200, 'points': [{'x': 0.1, 'y': 0.1}, {'x': 0.9, 'y': 0.8}]}}
shapeElement = {'id': 'shape', 'type': 'shape', 'x': 200, 'y': 200, 'width': 200, 'height': 100,
                'rotation': -10, 'z': 2, 'opacity': 0.8,
                'shape': {'kind': 'rounded', 'fill': 'none', 'stroke': '#416b55', 'lineWidth': 3,
                          'dashed': True, 'radius': 25, 'lockRatio': False}}


def test_DrawingRoundTripDimensionsAndVersionConflict(client, users):
    _, headers = users[0]
    layout = {**deepcopy(blankLayout), 'elements': [deepcopy(strokeElement), deepcopy(shapeElement)]}
    response = client.post('/api/v1/projects', headers=headers, json={'title': '手绘笔记', 'layout': layout})
    assert response.status_code == 200, response.text
    project = response.json()
    endpoint = '/api/v1/projects/' + project['id']
    assert client.get(endpoint, headers=headers).json()['layout'] == layout
    assert client.get(endpoint, headers=users[1][1]).status_code == 404
    layout['width'] = 1920
    assert client.patch(endpoint, headers=headers, json={'base_version': 1, 'layout': layout}).status_code == 200
    assert client.patch(endpoint, headers=headers, json={'base_version': 1, 'layout': layout}).status_code == 409
    assert client.get(endpoint, headers=headers).json()['layout']['width'] == 1920


@pytest.mark.parametrize('kind', ['rectangle', 'square', 'rounded', 'circle', 'ellipse', 'triangle', 'triangleDown', 'diamond', 'pentagon', 'hexagon', 'hexagonPoint', 'star', 'line', 'arrow', 'doubleArrow'])
def test_AllShapeKindsPersist(client, users, kind):
    element = deepcopy(shapeElement)
    element['shape']['kind'] = kind
    element['shape']['points'] = [{'x': 0, 'y': 0.5}, {'x': 1, 'y': 0.5}]
    response = client.post('/api/v1/projects', headers=users[0][1], json={'layout': {**blankLayout, 'elements': [element]}})
    assert response.status_code == 200, response.text
    assert response.json()['layout']['elements'][0] == element


@pytest.mark.parametrize('section,field,value', [
    ('stroke', 'lineWidth', 0), ('stroke', 'lineWidth', 81), ('stroke', 'lineWidth', True),
    ('stroke', 'color', 'url(https://invalid)'), ('stroke', 'brush', 'invalid'),
    ('stroke', 'baseWidth', 0), ('stroke', 'points', []), ('stroke', 'points', [{'x': -1, 'y': 0}]),
    ('shape', 'kind', 'invalid'), ('shape', 'lineWidth', 0), ('shape', 'radius', 51),
    ('shape', 'dashed', 'yes'), ('shape', 'lockRatio', 1), ('shape', 'stroke', 'none')])
def test_InvalidDrawingRejected(client, users, section, field, value):
    element = deepcopy({'stroke': strokeElement, 'shape': shapeElement}[section])
    element[section][field] = value
    response = client.post('/api/v1/projects', headers=users[0][1], json={'layout': {**blankLayout, 'elements': [element]}})
    assert response.status_code == 422


@pytest.mark.parametrize('opacity', [-0.1, 1.1, True, '50'])
def test_InvalidOpacityRejected(client, users, opacity):
    element = {**deepcopy(strokeElement), 'opacity': opacity}
    assert client.post('/api/v1/projects', headers=users[0][1], json={'layout': {**blankLayout, 'elements': [element]}}).status_code == 422


@pytest.mark.parametrize('width', [99, 4097, 1024.5, True])
def test_InvalidManualCanvasRejected(client, users, width):
    assert client.post('/api/v1/projects', headers=users[0][1], json={'layout': {**blankLayout, 'width': width}}).status_code == 422


def test_ExcessiveStrokePointsRejected(client, users):
    element = deepcopy(strokeElement)
    element['stroke']['points'] = [{'x': 0.5, 'y': 0.5}] * 2049
    assert client.post('/api/v1/projects', headers=users[0][1], json={'layout': {**blankLayout, 'elements': [element]}}).status_code == 422


def test_GpsNotebookAcceptsDrawingButRetainsBackgroundRules(client, users):
    user, headers = users[0]
    project = client.post('/api/v1/projects', headers=headers, json={'title': 'GPS 手绘覆盖验收'}).json()
    with SessionLocal() as database:
        asset = models.Asset(user_id=user['id'], title='隔离背景', source='notebook_background',
                             **storage.store_image(storage.encode(Image.new('RGB', (1024, 1536), '#eeeeee'))))
        database.add(asset)
        database.flush()
        task = models.Task(user_id=user['id'], kind='image_polish', status='succeeded',
                           input={'project_id': project['id'], 'mode': 'background-v1'}, saved_asset_id=asset.id)
        database.add(task)
        database.commit()
        assetId, taskId = asset.id, task.id
    background = {'id': 'background', 'type': 'image', 'asset_id': assetId, 'x': 0, 'y': 0,
                  'width': 1024, 'height': 1536, 'rotation': 0, 'z': 0}
    layout = {'schema_version': 1, 'notebookVersion': 1, 'width': 1024, 'height': 1536,
              'background': '#ffffff', 'backgroundTaskId': taskId,
              'elements': [background, deepcopy(strokeElement), deepcopy(shapeElement)]}
    endpoint = '/api/v1/projects/' + project['id']
    response = client.patch(endpoint, headers=headers, json={'base_version': 1, 'layout': layout})
    assert response.status_code == 200, response.text
    assert response.json()['layout']['elements'][1]['stroke'] == strokeElement['stroke']
    invalidLayout = deepcopy(layout)
    invalidLayout['width'] = 1080
    assert client.patch(endpoint, headers=headers, json={'base_version': 2, 'layout': invalidLayout}).status_code == 422
    invalidLayout = deepcopy(layout)
    invalidLayout['elements'][0]['opacity'] = 0.5
    assert client.patch(endpoint, headers=headers, json={'base_version': 2, 'layout': invalidLayout}).status_code == 422
