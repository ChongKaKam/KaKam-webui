import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from kakam_memory.app import create_app
from kakam_memory.model_discovery import list_models
from test_admin import form, request

pytest_plugins = ['test_postgres', 'test_admin']


def mock_provider(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def test_discovery_draft_auth_no_save_and_no_model_required(repo, cfg, monkeypatch):
    calls = []

    def provider(req):
        calls.append(req)
        assert req.method == 'GET' and req.url.path == '/v1/models'
        return httpx.Response(
            200,
            json={
                'data': [
                    {'id': 'vector-fixture'},
                    {'id': 'summary-fixture'},
                    {'id': 'vector-fixture'},
                    {'id': 'draft-secret'},
                    {'id': ''},
                    {'id': None},
                    {'id': 'bad\nname'},
                ]
            },
        )

    mock_provider(monkeypatch, provider)
    with TestClient(create_app(cfg, repo)) as c:
        before = request(c).json()
        for kind in ('context', 'embedding'):
            draft = form(c, kind, model='', api_key_action='replace', api_key='draft-secret')
            result = request(c, 'POST', f'/{kind}/models', draft)
            assert result.status_code == 200
            assert result.headers['cache-control'] == 'no-store'
            assert result.json()['models'] == ['summary-fixture', 'vector-fixture']
            assert result.json()['ok'] and 'draft-secret' not in result.text
            assert calls[-1].headers['authorization'] == 'Bearer draft-secret'
        assert request(c).json() == before
        unsigned = {'Authorization': 'Bearer ' + 's' * 32, 'X-Memory-User': 'admin'}
        assert c.post('/v1/admin/config/context/models', json=draft, headers=unsigned).status_code == 403
        count = len(calls)
        assert (
            request(c, 'POST', '/context/models', form(c, model='', base_url='https://other.invalid')).status_code
            == 409
        )
        assert len(calls) == count  # retained secret never travels to a new origin
        assert request(c, 'POST', '/context/models', form(c, model='', base_url='')).status_code in (409, 422)


@pytest.mark.parametrize(
    'code, expected',
    [
        (401, 'authentication_failed'),
        (403, 'permission_denied'),
        (404, 'unsupported'),
        (405, 'unsupported'),
        (429, 'rate_limited'),
        (500, 'provider_error'),
    ],
)
def test_discovery_error_responses_are_sanitized(repo, cfg, monkeypatch, code, expected):
    mock_provider(monkeypatch, lambda req: httpx.Response(code, json={'error': 'private-provider-body'}))
    with TestClient(create_app(cfg, repo)) as c:
        result = request(c, 'POST', '/context/models', form(c, model=''))
        assert result.json()['status'] == expected and not result.json()['ok']
        assert result.json()['models'] == [] and 'private-provider-body' not in result.text


def test_discovery_empty_invalid_timeout_network_and_redirect(repo, cfg, monkeypatch):
    response = [httpx.Response(200, json={'data': []})]
    calls = []

    def provider(req):
        calls.append(req.url)
        if isinstance(response[0], Exception):
            raise response[0]
        return response[0]

    mock_provider(monkeypatch, provider)
    with TestClient(create_app(cfg, repo)) as c:
        draft = form(c, model='')
        empty = request(c, 'POST', '/context/models', draft).json()
        assert empty['ok'] and empty['models'] == []
        for value, status in [
            (httpx.Response(200, json={'not_data': []}), 'invalid_response'),
            (httpx.Response(200, text='not JSON'), 'invalid_response'),
            (httpx.Response(200, json={'data': [{'id': 'x' * 201}]}), 'invalid_response'),
            (httpx.ReadTimeout('private'), 'timeout'),
            (httpx.ConnectError('private'), 'connection_failed'),
            (httpx.Response(302, headers={'location': 'https://other.invalid/models'}), 'provider_error'),
        ]:
            response[0] = value
            result = request(c, 'POST', '/context/models', draft)
            assert result.json()['status'] == status and not result.json()['ok']
            assert 'private' not in result.text
        assert all(url.host == 'fixture.invalid' for url in calls)


def test_discovery_limits_size_and_count(monkeypatch):
    value = [httpx.Response(200, json={'data': [{'id': f'model-{n}'} for n in range(501)]})]
    mock_provider(monkeypatch, lambda req: value[0])
    config = {'base_url': 'https://fixture.invalid/v1', 'api_key': '', 'timeout_seconds': 1}
    result = asyncio.run(list_models(config))
    assert len(result['models']) == 500 and result['truncated']
    value[0] = httpx.Response(200, content=b' ' * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match='too large'):
        asyncio.run(list_models(config))
