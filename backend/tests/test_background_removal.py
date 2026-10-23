import pytest
from PIL import Image, ImageDraw
from app.cutout import RemoveBackground
from app import billing, jobs, models as m
from app.db import SessionLocal
from test_management import NewUser
from test_species_cutout import UploadPhoto, MockImages


@pytest.mark.parametrize('background', ['white', '#dddddd', '#d6ebc7'])
def test_border_connected_background_preserves_enclosed_white_details(background):
    picture = Image.new('RGB', (256, 256), background)
    drawing = ImageDraw.Draw(picture)
    drawing.ellipse((40, 30, 210, 230), fill='#385b32')
    drawing.ellipse((70, 70, 180, 180), fill='white')
    output = RemoveBackground(picture)
    assert output.size == picture.size
    assert output.getpixel((0, 0))[3] == 0
    assert output.getpixel((128, 128)) == (255, 255, 255, 255)
    assert output.getpixel((128, 210))[3] == 255
    assert output.getchannel('A').histogram()[1:255] != [0] * 254


def test_existing_transparency_is_preserved_exactly():
    picture = Image.new('RGBA', (100, 100))
    ImageDraw.Draw(picture).ellipse((20, 20, 80, 80), fill=(40, 80, 20, 255))
    assert RemoveBackground(picture).tobytes() == picture.tobytes()


def test_empty_subject_and_complex_border_are_rejected():
    with pytest.raises(ValueError, match='有效主体'):
        RemoveBackground(Image.new('RGB', (100, 100), 'white'))
    picture = Image.new('RGB', (100, 100), 'red')
    ImageDraw.Draw(picture).rectangle((50, 0, 99, 99), fill='blue')
    with pytest.raises(ValueError, match='背景过于复杂'):
        RemoveBackground(picture)


def test_cutout_failure_does_not_repeat_paid_generation(client, monkeypatch):
    _, headers = NewUser(client)
    photoId = UploadPhoto(client, headers)
    requests = MockImages(monkeypatch, Image.new('RGB', (100, 100), 'white'))
    response = client.post('/api/v1/tasks', headers=headers, json={
        'kind': 'image_generation', 'input': {'asset_id': photoId}})
    taskId = response.json()['id']
    task = client.get('/api/v1/tasks/' + taskId, headers=headers).json()
    assert task['status'] == 'failed'
    assert client.post('/api/v1/tasks/' + taskId + '/save', headers=headers).status_code != 200
    with SessionLocal() as db:
        charge = db.get(m.Charge, taskId)
        assert charge.actual_micros == 60000
        assert db.get(m.Task, taskId).result['_upstream_task_id'] == 'cutout-test-job'
    assert jobs.run_task(taskId) == 0
    assert [request.method for request in requests] == ['POST', 'GET']
