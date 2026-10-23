import io
from urllib.parse import urlsplit, parse_qs
from PIL import Image
from app import storage


def test_preview_size_cache_and_revocation(client, users):
    image = Image.new('RGBA', (1800, 1200), (20, 110, 60, 130))
    content = io.BytesIO()
    image.save(content, 'PNG')
    uploaded = client.post('/api/v1/assets/upload', headers=users[0][1], files={'file': ('preview.png', content.getvalue(), 'image/png')}, data={'operation_id': 'preview-performance-test'})
    assert uploaded.status_code == 200
    asset = uploaded.json()
    previewUrl = asset['thumbnail_url']
    preview = client.get(previewUrl)
    assert preview.status_code == 200
    assert preview.headers['content-type'] == 'image/webp'
    assert preview.headers['cache-control'] == 'private, no-cache'
    with Image.open(io.BytesIO(preview.content)) as result:
        assert max(result.size) <= 640
        assert result.mode == 'RGBA'
    original = client.get(asset['url'])
    assert original.headers['cache-control'] == 'private, no-cache'
    assert client.get(asset['url'], headers={'If-None-Match': original.headers['etag']}).status_code == 304
    with Image.open(io.BytesIO(original.content)) as result:
        assert result.size == (1800, 1200)
        assert result.getpixel((0, 0)) == (20, 110, 60, 130)
    cached = client.get(previewUrl, headers={'If-None-Match': preview.headers['etag']})
    assert cached.status_code == 304
    assert cached.content == b''
    assert client.get(previewUrl.replace('preview=1', 'preview=0')).status_code == 403
    assert client.delete('/api/v1/assets/' + asset['id'], headers=users[0][1]).status_code == 200
    assert client.get(previewUrl, headers={'If-None-Match': preview.headers['etag']}).status_code == 404
    assert client.get(asset['url'], headers={'If-None-Match': original.headers['etag']}).status_code == 404


def test_preview_url_is_stable_without_extending_authorization(monkeypatch):
    clock = 1800000010
    monkeypatch.setattr(storage.time, 'time', lambda: clock)
    first = storage.url('private/example.png', 'asset', 'example', preview=True)
    clock += 40
    second = storage.url('private/example.png', 'asset', 'example', preview=True)
    assert first == second
    expires = int(parse_qs(urlsplit(second).query)['expires'][0])
    assert 0 < expires - clock <= 3600
