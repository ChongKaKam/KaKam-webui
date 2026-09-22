from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from kakam_memory.app import create_app
from kakam_memory.config import Settings


class FakeRepository:
    def __init__(self):
        self.rows = {}
        self.revisions = {}
        self.jobs = set()
        self.recalls = 0

    def migrate(self):
        pass

    def revision(self, owner):
        return self.revisions.get(owner, 0)

    def list(self, owner):
        return list(self.rows.get(owner, {}).values())

    def add(self, owner, content, kind, vector, version):
        rows = self.rows.setdefault(owner, {})
        if any(r['content'] == content for r in rows.values()):
            return {'created': False}
        memory_id = str(uuid4())
        rows[memory_id] = dict(
            id=memory_id,
            content=content,
            kind=kind,
            pinned=False,
            updated_at=datetime.now(timezone.utc),
            expires_at=None,
        )
        self.revisions[owner] = self.revision(owner) + 1
        return {'created': True}

    def delete(self, owner, memory_id):
        deleted = self.rows.get(owner, {}).pop(str(memory_id), None)
        if deleted:
            self.revisions[owner] = self.revision(owner) + 1
        return bool(deleted)

    def recall(self, owner, *args):
        self.recalls += 1
        return self.list(owner)

    def enqueue(self, owner, chat_id, message_id, evidence):
        key = (owner, chat_id, message_id)
        if key in self.jobs:
            return False
        self.jobs.add(key)
        return True


class FakeProviders:
    async def embed(self, text, owner):
        return [1, 0, 0]


@pytest.fixture
def setup():
    repo = FakeRepository()
    cfg = Settings(
        database_url='unused',
        service_key='s' * 32,
        embedding_url='http://test/v1',
        embedding_model='test',
        embedding_dimension=3,
    )
    with TestClient(create_app(cfg, repo, FakeProviders())) as client:
        yield client, repo


def headers(owner='alice'):
    return {'Authorization': 'Bearer ' + 's' * 32, 'X-Memory-User': owner}


def test_service_auth(setup):
    client, _ = setup
    assert client.get('/v1/memories').status_code == 401
    assert client.get('/v1/memories', headers={'Authorization': 'Bearer ' + 's' * 32}).status_code == 400
    assert client.get('/v1/policies', headers=headers()).json()[0]['id'] == 'default'


def test_crud_isolation_cache_revision_and_preferences(setup):
    client, repo = setup
    assert client.post('/v1/memories', headers=headers(), json={'content': '我喜欢中文'}).json()['created']
    assert client.get('/v1/memories', headers=headers('bob')).json() == []
    body = {'query': '语言'}
    first = client.post('/v1/recall', headers=headers(), json=body).json()
    assert not first['cache_hit'] and len(first['memories']) == 1
    assert client.post('/v1/recall', headers=headers(), json=body).json()['cache_hit']
    assert not client.post('/v1/recall', headers=headers(), json={**body, 'days': 7}).json()['cache_hit']
    assert not client.post('/v1/recall', headers=headers(), json={**body, 'cache': False}).json()['cache_hit']
    assert client.post('/v1/recall', headers=headers('bob'), json=body).json()['memories'] == []
    mid = first['memories'][0]['id']
    assert client.delete('/v1/memories/' + mid, headers=headers('bob')).status_code == 404
    assert client.delete('/v1/memories/' + mid, headers=headers()).status_code == 200
    result = client.post('/v1/recall', headers=headers(), json=body).json()
    assert not result['cache_hit'] and result['memories'] == []


def test_old_durable_memory_survives_cache_hits_but_expiry_still_applies(setup, monkeypatch):
    import kakam_memory.app as module

    client, repo = setup
    repo.add('default:alice', 'old but relevant', 'fact', [], '')
    row = next(iter(repo.rows['default:alice'].values()))
    row['updated_at'] = datetime.now(timezone.utc) - timedelta(days=365)
    body = {'query': '', 'days': 7}
    for hit in (False, True):
        response = client.post('/v1/recall', headers=headers(), json=body).json()
        assert response['cache_hit'] == hit
        assert response['memories'][0]['expires_at'] is None
    # A different query avoids the durable-result cache; explicit expiry must be
    # rechecked when that result subsequently comes from cache.
    now = datetime.now(timezone.utc)
    row['expires_at'] = now + timedelta(minutes=1)
    body['query'] = 'expiry'
    assert client.post('/v1/recall', headers=headers(), json=body).json()['memories']

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return now + timedelta(minutes=2)

    monkeypatch.setattr(module, 'datetime', Later)
    response = client.post('/v1/recall', headers=headers(), json=body).json()
    assert response['cache_hit'] and response['memories'] == []


@pytest.mark.parametrize(
    'body', [{'query': 'q', 'days': 6}, {'query': 'q', 'days': 31}, {'query': 'q', 'policy': 'unknown'}]
)
def test_invalid_policy_window(setup, body):
    client, _ = setup
    assert client.post('/v1/recall', headers=headers(), json=body).status_code == 422


def test_jobs_idempotent_private_and_secrets_rejected(setup):
    client, _ = setup
    body = {'chat_id': 'chat', 'message_id': 'msg', 'evidence': '请记住：中文'}
    assert not client.post('/v1/events/turn-completed', headers=headers(), json=body).json()['queued']
    assert not client.post('/v1/events/turn-completed', headers=headers(), json=body).json()['queued']
    assert not client.post('/v1/events/turn-completed', headers=headers('bob'), json=body).json()['queued']
    for update in [{'chat_id': 'temporary:1'}, {'chat_id': 'channel:1'}, {'evidence': 'password: 123'}]:
        assert not client.post('/v1/events/turn-completed', headers=headers(), json={**body, **update}).json()['queued']
    assert client.post('/v1/memories', headers=headers(), json={'content': 'api-key: sensitive'}).status_code == 422
    assert client.post('/v1/recall', headers=headers(), json={'query': 'api-key: sensitive'}).json()['memories'] == []


def test_manual_episode_preserves_opaque_source_and_owner(setup, monkeypatch):

    client, repo = setup
    original = repo.add
    seen = []

    def with_source(owner, content, kind, vector, version, source=None):
        seen.append((owner, kind, source))
        return original(owner, content, kind, vector, version)

    monkeypatch.setattr(repo, 'add', with_source)
    body = {'content': '用户确认保留的问答：备份数据库。', 'kind': 'episode',
            'source': {'external_chat_id': 'opaque-chat', 'external_message_id': 'opaque-answer'}}
    assert client.post('/v1/memories', headers=headers(), json=body).json()['created']
    assert seen == [('default:alice', 'episode', ('opaque-chat', 'opaque-answer'))]
    assert not client.post('/v1/memories', headers=headers(), json=body).json()['created']
    assert client.get('/v1/memories', headers=headers('bob')).json() == []
    tenant = {**headers(), 'X-Memory-Tenant': 'other'}
    assert client.get('/v1/memories', headers=tenant).json() == []
    assert client.post('/v1/memories', headers=tenant, json=body).json()['created']


def test_remember_rejects_secrets_and_oversize_before_embedding(setup, monkeypatch):
    from unittest.mock import AsyncMock, Mock

    client, repo = setup
    saved = Mock(wraps=repo.add)
    embedding = AsyncMock(return_value=[1, 0, 0])
    monkeypatch.setattr(FakeProviders, 'embed', embedding)
    monkeypatch.setattr(repo, 'add', saved)
    for text in ['password: private-value', 'a' * 2001, '']:
        response = client.post('/v1/memories', headers=headers(), json={'content': text, 'kind': 'episode'})
        assert response.status_code == 422
        assert text not in response.text if text else True
    saved.assert_not_called()
    embedding.assert_not_called()
