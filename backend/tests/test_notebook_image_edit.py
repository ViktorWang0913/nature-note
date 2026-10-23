from copy import deepcopy
import pytest
from fastapi import HTTPException
from app.notebook import ValidateImageEdit
from app import models as m, storage
from app.db import SessionLocal
from PIL import Image

imageEdit = {'cropX': 10, 'cropY': 5, 'cropW': 60, 'cropH': 80,
             'brightness': 130, 'contrast': 90, 'saturation': 75, 'filter': 'warm'}


def test_valid_image_adjustments_preserve_all_fields():
    element = {'id': 'material', 'imageEdit': deepcopy(imageEdit)}
    ValidateImageEdit(element)
    assert element['imageEdit'] == imageEdit


@pytest.mark.parametrize('field,value', [('cropX', 50), ('brightness', 201), ('contrast', True),
    ('saturation', float('nan')), ('filter', {}), ('cropH', -1)])
def test_invalid_image_adjustments_are_rejected(field, value):
    element = {'id': 'material', 'imageEdit': {**imageEdit, field: value}}
    with pytest.raises(HTTPException) as error:
        ValidateImageEdit(element)
    assert error.value.status_code == 422


def test_background_adjustment_is_forbidden():
    with pytest.raises(HTTPException):
        ValidateImageEdit({'id': 'background', 'imageEdit': imageEdit})


def test_adjustments_save_reload_and_keep_original_asset(client, users):
    user, headers = users[0]
    project = client.post('/api/v1/projects', headers=headers, json={'title': '素材编辑隔离验收'}).json()
    with SessionLocal() as db:
        stored = storage.store_image(storage.encode(Image.new('RGBA', (100, 100), (30, 120, 80, 200))))
        material = m.Asset(user_id=user['id'], title='素材', source='generated', category='plant', **stored)
        background = m.Asset(user_id=user['id'], title='背景', source='notebook_background', category='environment', **stored)
        db.add_all([material, background]);db.flush()
        task = m.Task(user_id=user['id'], kind='image_polish', status='succeeded',
                      input={'project_id': project['id'], 'mode': 'background-v1'}, saved_asset_id=background.id)
        db.add(task);db.commit()
        materialId, backgroundId, taskId = material.id, background.id, task.id
    materialElement = {'id': 'material', 'type': 'image', 'asset_id': materialId, 'x': 135, 'y': 420,
                       'width': 380, 'height': 320, 'rotation': 51, 'z': 1, 'imageEdit': imageEdit}
    layout = {'schema_version': 1, 'notebookVersion': 1, 'backgroundTaskId': taskId,
              'width': 1024, 'height': 1536, 'background': '#ffffff', 'elements': [
                  {'id': 'background', 'type': 'image', 'asset_id': backgroundId, 'x': 0, 'y': 0,
                   'width': 1024, 'height': 1536, 'rotation': 0, 'z': 0}, materialElement]}
    endpoint = '/api/v1/projects/' + project['id']
    response = client.patch(endpoint, headers=headers, json={'base_version': 1, 'layout': layout})
    assert response.status_code == 200, response.text
    reloaded = client.get(endpoint, headers=headers).json()['layout']['elements'][1]
    assert reloaded['imageEdit'] == imageEdit
    assert reloaded['rotation'] == 51 and reloaded['width'] == 380
    invalid = deepcopy(layout)
    invalid['elements'][1]['imageEdit']['cropX'] = 80
    assert client.patch(endpoint, headers=headers, json={'base_version': 2, 'layout': invalid}).status_code == 422
    with SessionLocal() as db:
        assert db.get(m.Asset, materialId).key == stored['key']
        assert storage.image_bytes(storage.read(stored['key'])).getpixel((50, 50)) == (30, 120, 80, 200)
