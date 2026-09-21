import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import replace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from kakam_memory.app import create_app
from kakam_memory.config import Settings
from kakam_memory.provider_config import ConfigStore
from kakam_memory.providers import Providers

pytest_plugins = ['test_postgres']


def headers(method='GET', path='/v1/admin/config', body=None, tenant='default', stamp=None):
    stamp = str(int(time.time()) if stamp is None else stamp)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    value = f'{stamp}\n{tenant}:admin\n{method}\n{path}\n{digest}'
    return {
        'Authorization': 'Bearer ' + 's' * 32,
        'X-Memory-User': 'admin',
        'X-Memory-Tenant': tenant,
        'X-Memory-Admin-Time': stamp,
        'X-Memory-Admin-Signature': hmac.new(b's' * 32, value.encode(), hashlib.sha256).hexdigest(),
    }


def request(c, method='GET', suffix='', body=None, tenant='default'):
    path = '/v1/admin/config' + suffix
    return c.request(method, path, json=body, headers=headers(method, path, body, tenant))


@pytest.fixture
def cfg():
    return Settings(
        database_url='unused',
        service_key='s' * 32,
        config_encryption_key='ab' * 32,
        embedding_url='https://fixture.invalid/v1',
        embedding_model='vector',
        embedding_dimension=3,
        embedding_key='environment-secret',
        context_url='https://fixture.invalid/v1',
        context_model='summary',
        context_key='context-secret',
    )


def form(c, kind='context', **changes):
    value = request(c).json()['providers'][kind]
    return {k: v for k, v in value.items() if k not in ('source', 'api_key_set')} | changes


def test_signed_auth_encryption_isolation_restart_and_reset(repo, cfg):
    with TestClient(create_app(cfg, repo)) as c:
        assert c.get('/v1/admin/config').status_code == 401
        ordinary = {'Authorization': 'Bearer ' + 's' * 32, 'X-Memory-User': 'user'}
        assert c.get('/v1/admin/config', headers=ordinary).status_code == 403
        assert c.get('/v1/admin/config', headers=headers(stamp=1)).status_code == 403
        initial = request(c)
        assert initial.headers['cache-control'] == 'no-store'
        assert 'environment-secret' not in initial.text and initial.json()['write_enabled']
        body = form(c, api_key_action='replace', api_key='saved-secret', protocol='responses')
        invalid_signature = headers('PUT', '/v1/admin/config/context', {**body, 'model': 'tampered'})
        assert c.put('/v1/admin/config/context', json=body, headers=invalid_signature).status_code == 403
        saved = request(c, 'PUT', '/context', body)
        assert saved.status_code == 200 and 'saved-secret' not in saved.text
        assert saved.json()['providers']['context']['source'] == 'database'
        assert request(c, tenant='other').json()['providers']['context']['source'] == 'environment'
        with repo.connect() as db:
            row = db.execute('SELECT encrypted_payload FROM memory_provider_config').fetchone()
            assert 'saved-secret' not in row['encrypted_payload'] and 'summary' not in row['encrypted_payload']
            audit = db.execute('SELECT * FROM memory_config_event').fetchall()
            assert len(audit) == 1 and 'saved-secret' not in str(audit)
        with pytest.raises(HTTPException):
            ConfigStore(repo, cfg).decrypt('other:admin', 'context', row['encrypted_payload'])
        assert request(c, 'PUT', '/context', body).status_code == 409  # stale revision
    with TestClient(create_app(cfg, repo)) as c:
        assert request(c).json()['providers']['context']['protocol'] == 'responses'
        assert ConfigStore(repo, cfg).effective('default:user').context_key == 'saved-secret'
        body = form(c, base_url='https://new.invalid/v1')
        assert request(c, 'POST', '/context/test', body).status_code == 409  # retained key must not travel
        assert request(c, 'PUT', '/context', body).status_code == 409
        reset = request(c, 'POST', '/context/reset', {'revision': 1})
        assert reset.json()['providers']['context']['source'] == 'environment'
        assert reset.json()['providers']['context']['revision'] == 2
        assert ConfigStore(repo, cfg).effective('default:user').context_key == 'context-secret'


def test_key_missing_wrong_key_clear_validation_and_embedding_guard(repo, cfg):
    with TestClient(create_app(replace(cfg, config_encryption_key=''), repo)) as c:
        assert not request(c).json()['write_enabled']
        assert request(c, 'PUT', '/context', form(c)).status_code == 503
    with TestClient(create_app(cfg, repo)) as c:
        invalid = form(c, api_key='do-not-echo' * 1000)
        response = request(c, 'PUT', '/context', invalid)
        assert response.status_code == 422 and 'do-not-echo' not in response.text
        assert request(c, 'PUT', '/context', form(c, owner='victim')).status_code == 422
        assert request(c, 'PUT', '/context', form(c, base_url='http://169.254.169.254')).status_code == 422
        assert request(c, 'PUT', '/context', form(c, api_key_action='clear')).status_code == 200
        assert not request(c).json()['providers']['context']['api_key_set']
        assert ConfigStore(repo, cfg).effective('default:user').context_key == ''
        repo.add('default:alice', 'keep', 'fact', [1, 0, 0], cfg.embedding_version)
        changed = form(c, 'embedding', model='new-vector')
        assert request(c, 'PUT', '/embedding', changed).status_code == 409
        assert request(c, 'PUT', '/embedding', changed | {'acknowledge_reindex': True}).status_code == 200
        assert request(c, 'POST', '/embedding/reset', {'revision': 1}).status_code == 409
        assert repo.recall('default:alice', 30, [1, 0, 0], 'new-space') == []
        assert len(repo.list('default:alice')) == 1
    with TestClient(create_app(replace(cfg, config_encryption_key='cd' * 32), repo)) as c:
        response = request(c)
        assert response.status_code == 503 and 'restore the original encryption key' in response.text


def test_hot_reload_probes_and_sanitized_failures(repo, cfg, monkeypatch):
    calls = []
    failure = [None]

    def provider(request):
        calls.append((request.url.path, request.headers.get('authorization'), json.loads(request.content)))
        if failure[0] == 'timeout':
            raise httpx.ReadTimeout('do-not-echo', request=request)
        if failure[0]:
            return httpx.Response(failure[0], json={'error': 'do-not-echo'})
        if request.url.path.endswith('/embeddings'):
            return httpx.Response(200, json={'data': [{'embedding': [1, 0, 0]}]})
        if request.url.path.endswith('/responses'):
            return httpx.Response(
                200,
                json={
                    'status': 'completed',
                    'output': [
                        {'type': 'reasoning', 'summary': []},
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': 'Synthetic summary'}],
                        },
                    ],
                },
            )
        return httpx.Response(
            200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': 'Synthetic summary'}}]}
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(provider), **kw))
    with TestClient(create_app(cfg, repo)) as c:
        ordinary = {'Authorization': 'Bearer ' + 's' * 32, 'X-Memory-User': 'alice'}
        query = {'query': 'same query'}
        assert not c.post('/v1/recall', json=query, headers=ordinary).json()['cache_hit']
        assert c.post('/v1/recall', json=query, headers=ordinary).json()['cache_hit']
        assert (
            request(
                c, 'PUT', '/embedding', form(c, 'embedding', api_key_action='replace', api_key='new-secret')
            ).status_code
            == 200
        )
        assert not c.post('/v1/recall', json=query, headers=ordinary).json()['cache_hit']
        assert calls[-1][1] == 'Bearer new-secret'
        for protocol in ('chat_completions', 'responses'):
            before_test = request(c).json()
            draft = form(c, protocol=protocol)
            tested = request(c, 'POST', '/context/test', draft)
            assert tested.json()['ok'] and not calls[-1][2]['store']
            assert calls[-1][0].endswith('/responses' if protocol == 'responses' else '/chat/completions')
            assert request(c).json() == before_test
            assert request(c, 'PUT', '/context', draft).status_code == 200
            assert ConfigStore(repo, cfg).effective('default:alice').context_protocol == protocol
        for code, status in (
            (401, 'authentication_failed'),
            (403, 'permission_denied'),
            (404, 'not_found'),
            (429, 'rate_limited'),
            (500, 'provider_error'),
            ('timeout', 'timeout'),
        ):
            failure[0] = code
            result = request(c, 'POST', '/embedding/test', form(c, 'embedding'))
            assert result.json()['status'] == status and not result.json()['ok']
            assert 'do-not-echo' not in result.text and 'new-secret' not in result.text


@pytest.mark.parametrize('protocol', ['responses', 'chat_completions'])
def test_incomplete_summary_is_not_accepted(cfg, monkeypatch, protocol):
    data = (
        {'status': 'incomplete', 'output': []}
        if protocol == 'responses'
        else {'choices': [{'finish_reason': 'length', 'message': {'content': 'partial'}}]}
    )
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        'AsyncClient',
        lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=data)), **kw),
    )
    with pytest.raises(ValueError, match='Incomplete'):
        asyncio.run(Providers(replace(cfg, context_protocol=protocol)).summarize('', 'test'))
