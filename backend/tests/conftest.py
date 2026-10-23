import os
import tempfile
from pathlib import Path
import pytest

TEST_DIR = Path(tempfile.mkdtemp(prefix='nature-note-api-test-'))
os.environ.update(APP_ENV='development', DATABASE_URL='sqlite:///' + (TEST_DIR / 'nature.db').as_posix(), SECRET_KEY='test-secret-which-is-at-least-thirty-two-characters', ENABLE_DEV_AUTH='true', STORAGE_BACKEND='local', STORAGE_DIR=str(TEST_DIR / 'files'), PUBLIC_BASE_URL='http://testserver', QUEUE_BACKEND='inline')
os.environ.update(IMAGE_API_KEY='', MULTIMODAL_API_KEY='', WECHAT_APP_ID='', WECHAT_APP_SECRET='', WECHAT_MODERATION_ENABLED='false')

from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from app.main import app
from app.seed import seed


@pytest.fixture(scope='session')
def client():
    command.upgrade(Config('alembic.ini'), 'head')
    seed()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope='session')
def users(client):
    result = []
    for name in ['observer-a', 'observer-b']:
        response = client.post('/api/v1/auth/dev', json={'device_id': name})
        assert response.status_code == 200, response.text
        user = response.json()
        result.append((user['user'], {'Authorization': 'Bearer ' + user['access_token']}))
    return result
