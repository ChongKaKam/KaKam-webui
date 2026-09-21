"""Real PostgreSQL integration tests; providers are deterministic, not external LLMs."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kakam_memory.app import create_app
from kakam_memory.config import Settings
from kakam_memory.contracts import Message
from kakam_memory.manager import safe_cut
from test_api import headers

pytest_plugins = ['test_postgres']


class Provider:
    calls = 0

    async def embed(self, text, owner):
        self.calls += 1
        return [1, 0, 0]

    async def summarize(self, previous, source):
        return '用户在实现记忆服务；保留原始消息，确认后保存知识。'


def client_for(repo, provider=None):
    cfg = Settings(
        database_url='unused',
        service_key='s' * 32,
        embedding_url='http://fixture/v1',
        embedding_model='test',
        embedding_dimension=3,
        context_url='http://fixture/v1',
        context_model='test',
    )
    return TestClient(create_app(cfg, repo, provider or Provider()))


def test_tenant_scope_cache_confirmation_and_relations(repo):
    with client_for(repo) as c:
        a = headers()
        tenant = {**a, 'X-Memory-Tenant': 'other'}
        mid = c.post('/v1/memories', headers=a, json={'content': '中文回答'}).json()['id']
        assert c.get('/v1/memories', headers=tenant).json() == []
        assert c.get('/v1/memories', headers={**a, 'X-Memory-Tenant': 'bad:tenant'}).status_code == 400
        path = '/v1/manager/sessions/chat'
        view = c.get(path, headers=a).json()
        scope = view['session']
        body = {'session_id': 'chat', 'query': '语言'}
        first = c.post('/v1/manager/prepare-turn', headers=a, json=body).json()
        assert first['memories'][0]['id'] == mid
        assert c.post('/v1/manager/prepare-turn', headers=a, json=body).json()['cache_hit']
        scope['selections'] = {mid: 'exclude'}
        assert c.put(path, headers=a, json=scope).status_code == 200
        assert c.put(path, headers=tenant, json=scope).status_code == 404
        result = c.post('/v1/manager/prepare-turn', headers=a, json=body).json()
        assert not result['cache_hit'] and not result['memories']
        scope['selections'] = {mid: 'prefer'}
        scope['settings']['automatic_recall'] = False
        c.put(path, headers=a, json=scope)
        assert c.post('/v1/manager/prepare-turn', headers=a, json=body).json()['memories'][0]['id'] == mid
        # Proposals are not written until an authenticated user confirms.
        proposal = {'content': '使用 PostgreSQL', 'evidence': '请记住使用 PostgreSQL', 'source_message_id': 'm1'}
        pid = c.post(path + '/proposals', headers=a, json=proposal).json()['id']
        assert len(c.get('/v1/memories', headers=a).json()) == 1
        decision = f'/v1/manager/proposals/{pid}/decision'
        assert c.post(decision, headers=tenant, json={'approve': True}).status_code == 404
        result = c.post(decision, headers=a, json={'approve': True}).json()
        assert result['state'] == 'applied'
        assert c.post(decision, headers=a, json={'approve': True}).json() == result
        assert len(c.get('/v1/memories', headers=a).json()) == 2
        scope['selections'] = {mid: 'exclude'}
        c.put(path, headers=a, json=scope)
        assert c.post('/v1/manager/prepare-turn', headers=a, json=body).json()['memories'] == []
        explicit = c.post('/v1/manager/prepare-turn', headers=a, json={**body, 'explicit_recall': True}).json()
        assert [m['id'] for m in explicit['memories']] == [result['id']]
        cid = c.post('/v1/manager/collections', headers=a, json={'name': '项目'}).json()['id']
        assert (
            c.post('/v1/manager/collections', headers=tenant, json={'name': '偷看', 'parent_id': cid}).status_code
            == 404
        )
        relation = f'/v1/manager/memories/{mid}/collection'
        assert c.put(relation, headers=tenant, json={'collection_id': cid}).status_code == 404
        assert c.put(relation, headers=a, json={'collection_id': cid}).status_code == 200
        assert c.get(path, headers=a).json()['relations'] == [{'memory_id': mid, 'collection_id': cid}]
        assert c.get(path, headers=tenant).json()['operations'] == []
        c.delete('/v1/memories/' + mid, headers=a)
        assert not c.post('/v1/manager/prepare-turn', headers=a, json=body).json()['memories']
        cleaned = c.get(path, headers=a).json()['session']
        assert mid not in cleaned['selections']
        assert c.put(path, headers=a, json=cleaned).status_code == 200


def test_edit_version_expiry_and_secret_guard(repo):
    with client_for(repo) as c:
        a = headers()
        mid = c.post('/v1/memories', headers=a, json={'content': '中文'}).json()['id']
        path = '/v1/manager/memories/' + mid
        body = {'content': '英文', 'kind': 'preference', 'version': 1, 'tags': ['语言']}
        assert c.patch(path, headers=headers('bob'), json=body).status_code == 404
        assert c.patch(path, headers=a, json=body).json()['version'] == 2
        assert c.patch(path, headers=a, json=body).status_code == 409
        assert c.patch(path, headers=a, json={**body, 'content': 'password: secret', 'version': 2}).status_code == 422
        with repo.connect() as db:
            assert db.execute('SELECT count(*) AS n FROM memory_version').fetchone()['n'] == 1
        c.delete('/v1/memories/' + mid, headers=a)
        with repo.connect() as db:
            assert db.execute('SELECT count(*) AS n FROM memory_version').fetchone()['n'] == 0


def test_compaction_checkpoint_and_modified_history(repo):
    with client_for(repo) as c:
        a = headers()
        path = '/v1/manager/sessions/chat'
        scope = c.get(path, headers=a).json()['session']
        scope['settings'].update(token_budget=2000, keep_messages=4)
        c.put(path, headers=a, json=scope)
        messages = [
            {'id': str(i), 'role': 'user' if i % 2 == 0 else 'assistant', 'text': '中文内容' * 150} for i in range(12)
        ]
        request = {'session_id': 'chat', 'messages': messages}
        result = c.post('/v1/manager/compact-context', headers=a, json=request).json()
        assert result['state'] == 'compacted' and result['cut'] == 8
        # Different principal has no checkpoint, even for identical session IDs.
        assert c.get(path, headers=headers('bob')).json()['compaction']['summary'] == ''
        scope['settings']['auto_compact'] = False
        c.put(path, headers=a, json=scope)
        assert c.post('/v1/manager/compact-context', headers=a, json=request).json()['cut'] == 8
        messages[0]['text'] = 'Edited source invalidates checkpoint'
        assert c.post('/v1/manager/compact-context', headers=a, json=request).json()['cut'] == 0
        assert c.get('/v1/memories', headers=a).json() == []


def test_tool_pair_cut():
    messages = [
        Message(role='user', text='question'),
        Message(role='assistant', tool_calls=['c']),
        Message(role='user', text='not a safe boundary'),
        Message(role='tool', tool_call_id='c'),
        Message(role='user', text='safe'),
        Message(role='assistant'),
        Message(role='user'),
    ]
    assert safe_cut(messages, 4) == 0
    assert safe_cut(messages, 2) == 4


@pytest.mark.parametrize('repo', [False], indirect=True)
def test_upgrade_preserves_records_and_stops_unapproved_jobs(repo):
    with repo.connect() as db:
        db.execute((Path(__file__).parents[1] / 'migrations/001_initial.sql').read_text())
    added = repo.add('alice', 'legacy memory', 'fact', [1, 0, 0], 'v1')
    repo.enqueue('alice', 'chat', 'm1', 'unapproved evidence')
    repo.migrate()
    repo.migrate()
    assert repo.list('default:alice')[0]['id'].__str__() == added['id']
    assert repo.list('alice') == []
    with repo.connect() as db:
        row = db.execute('SELECT owner,status,evidence FROM memory_job').fetchone()
        assert row == {'owner': 'default:alice', 'status': 'done', 'evidence': ''}


def test_handoff_never_persists_knowledge(repo):
    with client_for(repo) as c:
        a = headers()
        source = '{"conversation":[{"role":"user","content":"继续工作"}],"limitations":[]}'
        result = c.post('/v1/manager/sessions/chat/handoff', headers=a, json={'source': source})
        assert result.status_code == 200 and 'memory_policy' in result.json()['source']
        assert c.get('/v1/memories', headers=a).json() == []
        assert (
            c.post('/v1/manager/sessions/chat/handoff', headers=a, json={'source': 'password: secret'}).status_code
            == 422
        )


def test_provider_failure_does_not_commit_compaction(repo):
    class FailingProvider(Provider):
        async def summarize(self, previous, source):
            raise TimeoutError()

    with client_for(repo, FailingProvider()) as c:
        a = headers()
        scope = c.get('/v1/manager/sessions/chat', headers=a).json()['session']
        scope['settings'].update(token_budget=2000, keep_messages=4)
        c.put('/v1/manager/sessions/chat', headers=a, json=scope)
        messages = [{'role': 'user' if i % 2 == 0 else 'assistant', 'text': 'text ' * 1000} for i in range(10)]
        result = c.post(
            '/v1/manager/compact-context', headers=a, json={'session_id': 'chat', 'messages': messages}
        ).json()
        assert result['state'] == 'model_unavailable' and result['cut'] == 0
        assert c.get('/v1/manager/sessions/chat', headers=a).json()['compaction']['summary'] == ''
