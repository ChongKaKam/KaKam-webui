import importlib
import json
import sys
import types
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from open_webui.kakam.jev.client import JevError
from open_webui.kakam.jev.schemas import ConnectionInput, EvaluationResponse
from test_contracts import answer_body, plan_body, request_body


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.delenv('KAKAM_JEV_API_KEY', raising=False)
    monkeypatch.delenv('KAKAM_JEV_BASE_URL', raising=False)
    storage = {}

    class Config:
        @staticmethod
        async def get(key):
            return storage.get(key)

        @staticmethod
        async def upsert(values):
            storage.update(values)

    async def verified(authorization: str = Header(default='')):
        if authorization not in ('Bearer admin', 'Bearer user'):
            raise HTTPException(401, 'Login required')
        return types.SimpleNamespace(id='user-id', role=authorization.removeprefix('Bearer '))

    async def admin(authorization: str = Header(default='')):
        user = await verified(authorization)
        if user.role != 'admin':
            raise HTTPException(403, 'Admin required')
        return user

    complete = AsyncMock(side_effect=[json.dumps(plan_body()), '{"summary":"已完成判断。"}'])
    dependencies = {
        'open_webui.models.config': types.SimpleNamespace(Config=Config),
        'open_webui.utils.auth': types.SimpleNamespace(get_admin_user=admin, get_verified_user=verified),
        'open_webui.kakam.jev.llm': types.SimpleNamespace(
            prompt_models=AsyncMock(return_value=[{'id': 'allowed', 'name': 'Allowed model'}]),
            completion_port=lambda *args: complete,
        ),
    }
    names = ['open_webui.kakam.jev.config', 'open_webui.kakam.jev.router']
    previous = {name: sys.modules.pop(name, None) for name in names}
    try:
        with patch.dict(sys.modules, dependencies):
            module = importlib.import_module(names[1])
            config = importlib.import_module(names[0])
            app = FastAPI()
            app.include_router(module.router, prefix='/api/custom/jev')
            with TestClient(app) as client:
                yield client, module, config, storage, complete
    finally:
        for name, value in previous.items():
            sys.modules.pop(name, None)
            if value is not None:
                sys.modules[name] = value


def save(client, **fields):
    return client.put('/api/custom/jev/config', headers={'Authorization': 'Bearer admin'}, json=fields)


@pytest.mark.parametrize(
    'method,path,body',
    [
        ('get', '/config', None),
        ('put', '/config', {'api_key': 'secret'}),
        ('post', '/test', {}),
    ],
)
@pytest.mark.parametrize('authorization,status', [('', 401), ('Bearer user', 403)])
def test_settings_are_admin_only(endpoint, method, path, body, authorization, status):
    client, *_ = endpoint
    assert (
        client.request(
            method, '/api/custom/jev' + path, json=body, headers={'Authorization': authorization}
        ).status_code
        == status
    )


def test_save_preserve_clear_and_internal_reuse(endpoint):
    client, _, config, storage, _ = endpoint
    response = save(client, base_url='https://api.typesafe.ai', api_key='fixture-private-key')
    assert response.status_code == 200
    assert response.json() == {'base_url': 'https://api.typesafe.ai/v1', 'has_api_key': True, 'model': 'jev-latest'}
    assert 'fixture-private-key' not in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert save(client).status_code == 200
    assert storage[config.CONFIG_KEY]['api_key'] == 'fixture-private-key'
    read = client.get('/api/custom/jev/config', headers={'Authorization': 'Bearer admin'})
    assert 'fixture-private-key' not in read.text
    assert save(client, clear_api_key=True).json()['has_api_key'] is False
    assert storage[config.CONFIG_KEY]['api_key'] is None


def test_url_change_cannot_accidentally_leak_existing_key(endpoint):
    client, _, config, storage, _ = endpoint
    save(client, api_key='fixture-private-key')
    assert save(client, base_url='https://other.invalid').status_code == 422
    assert storage[config.CONFIG_KEY]['base_url'] == 'https://api.typesafe.ai/v1'
    assert save(client, base_url='https://other.invalid', api_key='new-key').status_code == 200


def test_test_uses_draft_and_does_not_save_it(endpoint):
    client, module, config, storage, _ = endpoint
    save(client, api_key='old-key')
    provider = AsyncMock(evaluate=AsyncMock(return_value=EvaluationResponse.model_validate(answer_body())))
    factory = AsyncMock(return_value=provider)
    with patch.object(module, 'get_jev_client', factory):
        response = client.post(
            '/api/custom/jev/test', headers={'Authorization': 'Bearer admin'}, json={'api_key': 'new-key'}
        )
    assert response.status_code == 200
    assert response.json()['connected'] is True
    assert factory.call_args.args[0].api_key.get_secret_value() == 'new-key'
    assert storage[config.CONFIG_KEY]['api_key'] == 'old-key'
    assert 'new-key' not in response.text


def test_failed_probe_cannot_show_connected(endpoint):
    client, module, *_ = endpoint
    provider = AsyncMock(evaluate=AsyncMock(side_effect=JevError('Jev 鉴权失败', 'authentication')))
    with patch.object(module, 'get_jev_client', AsyncMock(return_value=provider)):
        response = client.post(
            '/api/custom/jev/test', headers={'Authorization': 'Bearer admin'}, json={'api_key': 'bad-key'}
        )
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'authentication'


def test_status_is_safe_for_regular_users(endpoint):
    client, module, *_ = endpoint
    save(client, api_key='fixture-private-key')
    provider = AsyncMock(check_connection=AsyncMock(return_value=17))
    with patch.object(module, 'get_jev_client', AsyncMock(return_value=provider)):
        response = client.get('/api/custom/jev/status', headers={'Authorization': 'Bearer user'})
    assert response.json()['connected'] is True
    assert 'base_url' not in response.json()
    assert 'fixture-private-key' not in response.text


def test_authentication_required_for_evaluation_and_turn(endpoint):
    client, *_ = endpoint
    assert client.post('/api/custom/jev/evaluate', json=request_body()).status_code == 401
    assert (
        client.post(
            '/api/custom/jev/turn',
            json={'model_id': 'allowed', 'messages': [{'role': 'user', 'content': 'Evaluate this'}]},
        ).status_code
        == 401
    )


def test_forbidden_prompt_model_never_calls_llm(endpoint):
    client, _, _, _, complete = endpoint
    save(client, api_key='key')
    response = client.post(
        '/api/custom/jev/turn',
        headers={'Authorization': 'Bearer user'},
        json={'model_id': 'forbidden', 'messages': [{'role': 'user', 'content': 'Evaluate this'}]},
    )
    assert response.status_code == 403
    complete.assert_not_called()


def test_sse_route_full_flow_and_direct_endpoint(endpoint):
    client, module, _, _, _ = endpoint
    save(client, api_key='key')
    provider = AsyncMock(evaluate=AsyncMock(return_value=EvaluationResponse.model_validate(answer_body())))
    with patch.object(module, 'get_jev_client', AsyncMock(return_value=provider)):
        response = client.post(
            '/api/custom/jev/turn',
            headers={'Authorization': 'Bearer user'},
            json={'model_id': 'allowed', 'messages': [{'role': 'user', 'content': '请选择团队、评分并判断是否退款'}]},
        )
        direct = client.post('/api/custom/jev/evaluate', headers={'Authorization': 'Bearer user'}, json=request_body())
    assert direct.status_code == 200
    assert response.headers['X-Accel-Buffering'] == 'no'
    assert response.headers['content-type'].startswith('text/event-stream')
    events = [
        json.loads(line.removeprefix('data: ')) for line in response.text.splitlines() if line.startswith('data:')
    ]
    assert events[-1] == {'type': 'stage', 'stage': 'done'}
    assert next(e for e in events if e['type'] == 'result')['response']['answers']['severity']['score'] == 1.25


@pytest.mark.asyncio
async def test_internal_client_reads_updated_credentials(endpoint):
    _, _, config, storage, _ = endpoint
    await config.save_connection(ConnectionInput(api_key='first-key'))
    first = await config.get_jev_client()
    await config.save_connection(ConnectionInput(api_key='second-key'))
    second = await config.get_jev_client()
    assert first._api_key == 'first-key'
    assert second._api_key == 'second-key'
    assert len(storage) == 1


def test_invalid_imported_configuration_can_be_repaired_without_forwarding_old_key(endpoint):
    client, _, config, storage, _ = endpoint
    storage[config.CONFIG_KEY] = {'base_url': 'file:///invalid', 'api_key': 'old-private-key'}
    assert save(client).status_code == 422
    assert save(client, api_key='replacement-key').status_code == 200
    assert storage[config.CONFIG_KEY]['api_key'] == 'replacement-key'
    assert storage[config.CONFIG_KEY]['base_url'] == 'https://api.typesafe.ai/v1'
