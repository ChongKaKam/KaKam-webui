"""Route contract tests isolate host dependencies; no database or provider calls."""

import importlib
import sys
import types
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from .service import ProbeError


@pytest.fixture
def endpoint():
    async def admin(authorization: str = Header(default='')):
        if authorization != 'Bearer admin-fixture':
            raise HTTPException(403, 'Admin required')
        return types.SimpleNamespace(role='admin')

    dependencies = {
        'open_webui.env': types.SimpleNamespace(AIOHTTP_CLIENT_SESSION_SSL=True),
        'open_webui.config': types.SimpleNamespace(IMAGE_URL_RESPONSE_MODELS_REGEX_PATTERN='^gpt-image'),
        'open_webui.utils.auth': types.SimpleNamespace(get_admin_user=admin),
        'open_webui.utils.session_pool': types.SimpleNamespace(get_session=AsyncMock(return_value=object())),
    }
    name = 'open_webui.kakam.images.router'
    previous = sys.modules.pop(name, None)
    try:
        with patch.dict(sys.modules, dependencies):
            module = importlib.import_module(name)
            app = FastAPI()
            app.include_router(module.router, prefix='/api/custom/images')
            with TestClient(app) as client:
                yield client, module
    finally:
        sys.modules.pop(name, None)
        if previous is not None:
            sys.modules[name] = previous


def body(**changes):
    return {'engine': 'openai', 'base_url': 'https://fixture.test/v1', 'model': 'image-one', **changes}


@pytest.mark.parametrize('auth', ['', 'Bearer normal-user-fixture'])
def test_unauthorized_requests_do_not_reach_provider(endpoint, auth):
    client, module = endpoint
    with patch.object(module, 'probe', AsyncMock()) as probe:
        assert client.post('/api/custom/images/probe', json=body(), headers={'Authorization': auth}).status_code == 403
        probe.assert_not_called()


def test_admin_probe_returns_result(endpoint):
    client, module = endpoint
    with patch.object(
        module, 'probe', AsyncMock(return_value={'models': [], 'complete': True, 'model_status': 'not_listed'})
    ):
        response = client.post(
            '/api/custom/images/probe', json=body(), headers={'Authorization': 'Bearer admin-fixture'}
        )
        assert response.status_code == 200
        assert response.json()['model_status'] == 'not_listed'


@pytest.mark.parametrize('error,status', [(ProbeError('没有返回图片', 422), 422), (TimeoutError(), 504)])
def test_generation_failure_is_not_success(endpoint, error, status):
    client, module = endpoint
    with patch.object(module, 'probe', AsyncMock(side_effect=error)):
        response = client.post(
            '/api/custom/images/probe', json=body(action='generate'), headers={'Authorization': 'Bearer admin-fixture'}
        )
        assert response.status_code == status
        if status == 504:
            assert '再次计费' in response.json()['detail']


def test_bad_input_rejected_before_provider(endpoint):
    client, module = endpoint
    with patch.object(module, 'probe', AsyncMock()) as probe:
        response = client.post(
            '/api/custom/images/probe', json=body(engine='unknown'), headers={'Authorization': 'Bearer admin-fixture'}
        )
        assert response.status_code == 422
        probe.assert_not_called()
