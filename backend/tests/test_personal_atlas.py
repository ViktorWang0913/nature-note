import io
from PIL import Image
from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from test_management import NewUser


def UploadPhoto(client, headers, color):
    imageBytes = io.BytesIO()
    Image.new('RGB', (32, 32), color).save(imageBytes, format='PNG')
    response = client.post('/api/v1/assets/upload', headers=headers,
        files={'file': ('observation.png', imageBytes.getvalue(), 'image/png')}, data={'operation_id': m.uid()})
    assert response.status_code == 200, response.text
    return response.json()


def test_private_atlas_empty_confirmation_merge_and_reclassification(client, users):
    firstUser, firstHeaders = NewUser(client)
    secondUser, secondHeaders = NewUser(client)
    assert client.get('/api/v1/atlas', headers=firstHeaders).json()['items'] == []
    firstPhoto = UploadPhoto(client, firstHeaders, '#135724')
    secondPhoto = UploadPhoto(client, firstHeaders, '#246813')
    assert firstPhoto['category'] == 'unclassified'
    assert client.get('/api/v1/assets?unfiled=true', headers=firstHeaders).json()['items']
    payload = {'asset_id': firstPhoto['id'], 'species_name': '白头鹎', 'scientific_name': 'Pycnonotus sinensis'}
    confirmation = client.post('/api/v1/observations', headers=firstHeaders, json=payload)
    assert confirmation.status_code == 200, confirmation.text
    record = confirmation.json()
    assert client.post('/api/v1/observations', headers=firstHeaders, json=payload).json()['id'] == record['id']
    secondRecord = client.post('/api/v1/observations', headers=firstHeaders, json={**payload, 'asset_id': secondPhoto['id'], 'species_name': '白头翁'}).json()
    assert secondRecord['species_id'] == record['species_id']
    atlas = client.get('/api/v1/atlas', headers=firstHeaders).json()['items']
    assert len(atlas) == 1 and atlas[0]['photo_count'] == 2
    assert client.get('/api/v1/atlas', headers=secondHeaders).json()['items'] == []
    assert client.get('/api/v1/species/' + record['species_id'], headers=secondHeaders).status_code == 404
    otherPhoto = UploadPhoto(client, secondHeaders, '#123987')
    assert client.post('/api/v1/observations', headers=secondHeaders, json={**payload, 'asset_id': otherPhoto['id'], 'species_id': record['species_id']}).status_code == 404
    changed = client.patch('/api/v1/observations/' + record['id'], headers=firstHeaders, json={'species_name': '麻雀', 'scientific_name': 'Passer montanus'})
    assert changed.status_code == 200, changed.text
    assert changed.json()['species_id'] != record['species_id']
    assert len(client.get('/api/v1/atlas', headers=firstHeaders).json()['items']) == 2
    assert client.delete('/api/v1/observations/' + record['id'], headers=firstHeaders).status_code == 200
    assert len(client.get('/api/v1/atlas', headers=firstHeaders).json()['items']) == 1
    assert client.get('/api/v1/assets/' + firstPhoto['id'], headers=firstHeaders).status_code == 200
    assert client.get('/api/v1/observations/' + record['id'], headers=firstHeaders).status_code in (404, 405)
    with SessionLocal() as db:
        assert db.scalar(select(m.Archive).where(m.Archive.resource_id == record['id'])) is not None
    restored = client.post('/api/v1/observations', headers=firstHeaders, json=payload)
    assert restored.status_code == 200 and restored.json()['id'] == record['id']
    assert client.put('/api/v1/species/' + record['species_id'] + '/cover', headers=firstHeaders, json={'asset_id': secondPhoto['id']}).status_code == 200
    assert client.put('/api/v1/species/' + record['species_id'] + '/cover', headers=firstHeaders, json={'asset_id': otherPhoto['id']}).status_code == 422


def test_generated_assets_cannot_be_observations(client, users):
    user, headers = users[0]
    with SessionLocal() as db:
        asset = m.Asset(user_id=user['id'], source='generated', key='test', original_key='test', thumbnail_key='test', width=1, height=1)
        db.add(asset)
        db.commit()
        assetId = asset.id
    response = client.post('/api/v1/observations', headers=headers, json={'asset_id': assetId, 'species_name': '测试物种'})
    assert response.status_code == 422
