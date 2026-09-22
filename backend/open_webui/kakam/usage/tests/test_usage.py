import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from usage.service import site_usage


def test_aggregates_all_users_and_both_token_directions():
    reader = AsyncMock(return_value={
        'alice': {'input_tokens': 100, 'output_tokens': 30, 'message_count': 2},
        'bob': {'input_tokens': 50, 'output_tokens': 20, 'message_count': 1},
    })
    result = asyncio.run(site_usage(reader, 'db'))
    assert result.model_dump() == {
        'input_tokens': 150, 'output_tokens': 50, 'total_tokens': 200,
        'recorded_messages': 3, 'recorded_users': 2,
    }
    reader.assert_awaited_once_with(db='db')


def test_empty_database_returns_zero():
    result = asyncio.run(site_usage(AsyncMock(return_value={}), 'db'))
    assert all(value == 0 for value in result.model_dump().values())


@pytest.fixture
def endpoint(monkeypatch):
    async def verified(authorization: str = Header(default='')):
        if authorization not in ('Bearer admin', 'Bearer user', 'Bearer pending'):
            raise HTTPException(401)
        who = authorization.split()[-1]
        if who != 'admin':
            raise HTTPException(403)
        return SimpleNamespace(id=who, role=who)

    async def database():
        yield 'database-session'

    reader = AsyncMock(return_value={'alice': {'input_tokens': 10, 'output_tokens': 20, 'message_count': 1}})
    for name, attrs in {
        'open_webui.utils.auth': {'get_admin_user': verified},
        'open_webui.internal.db': {'get_async_session': database},
        'open_webui.models.chat_messages': {'ChatMessages': SimpleNamespace(get_token_usage_by_user=reader)},
    }.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    sys.modules.pop('usage.router', None)
    router = importlib.import_module('usage.router')
    app = FastAPI()
    app.include_router(router.router, prefix='/api/custom/usage')
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, reader
    sys.modules.pop('usage.router', None)


def test_admin_only_and_no_caller_controlled_scope(endpoint):
    client, reader = endpoint
    assert client.get('/api/custom/usage/site').status_code == 401
    for role in ['pending', 'user']:
        assert client.get('/api/custom/usage/site', headers={'Authorization': f'Bearer {role}'}).status_code == 403
    reader.assert_not_called()
    response = client.get('/api/custom/usage/site?user_id=alice&days=1', headers={'Authorization': 'Bearer admin'})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.json()['total_tokens'] == 30
    assert 'alice' not in response.text
    reader.assert_awaited_once_with(db='database-session')
    assert client.get('/api/custom/usage/daily', headers={'Authorization': 'Bearer admin'}).status_code == 404


def test_failure_is_not_reported_as_zero(endpoint):
    client, reader = endpoint
    reader.side_effect = TimeoutError()
    response = client.get('/api/custom/usage/site', headers={'Authorization': 'Bearer admin'})
    assert response.status_code == 504
    assert 'total_tokens' not in response.json()
