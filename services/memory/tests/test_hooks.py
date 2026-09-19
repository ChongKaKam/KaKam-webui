"""Adapter contract tests without booting the upstream DB/model stack."""

import asyncio
import importlib
import sys
import types
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def adapter(monkeypatch):
    from open_webui.kakam.memory import client

    chats = types.SimpleNamespace(
        is_chat_owner=AsyncMock(return_value=True),
        get_message_by_id_and_message_id=AsyncMock(return_value={'role': 'user', 'content': '请记住中文'}),
        upsert_message_to_chat_by_id_and_message_id=AsyncMock(),
    )
    modules = {
        'open_webui.models.chats': types.SimpleNamespace(Chats=chats),
        'open_webui.models.config': types.SimpleNamespace(Config=types.SimpleNamespace(get=AsyncMock(return_value={}))),
        'open_webui.utils.access_control': types.SimpleNamespace(has_permission=AsyncMock(return_value=True)),
    }
    # Load the REAL pure upstream system-message helper through its AST, avoiding
    # unrelated heavyweight model dependencies in this standalone test suite.
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[3] / 'backend/open_webui/utils/misc.py'
    tree = ast.parse(source.read_text())
    namespace = {}
    helper_names = {'add_or_update_system_message', 'get_system_message', 'update_message_content'}
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in helper_names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), namespace)
    modules['open_webui.utils.misc'] = types.SimpleNamespace(**namespace)
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    for name in ['open_webui.kakam.memory.auth', 'open_webui.kakam.memory.hooks', 'open_webui.kakam.memory.router']:
        monkeypatch.delitem(sys.modules, name, raising=False)
    hooks = importlib.import_module('open_webui.kakam.memory.hooks')
    # Reload ensures its relative imports use our per-test auth stub dependencies.
    monkeypatch.setenv('KAKAM_MEMORY_ENABLED', 'true')
    monkeypatch.setenv('KAKAM_MEMORY_RECALL_MODE', 'on')
    monkeypatch.setenv('KAKAM_MEMORY_WRITE_MODE', 'on')
    monkeypatch.setenv('KAKAM_MEMORY_TIMEOUT_MS', '100')
    monkeypatch.setattr(
        client,
        'call',
        AsyncMock(return_value={'cache_hit': True, 'memories': [{'kind': 'preference', 'content': '中文'}]}),
    )
    user = types.SimpleNamespace(id='alice', role='admin', settings={})
    metadata = {'chat_id': 'chat', 'message_id': 'reply', 'user_message_id': 'user-msg'}
    yield hooks, user, metadata, chats
    for name in ['open_webui.kakam.memory.auth', 'open_webui.kakam.memory.hooks', 'open_webui.kakam.memory.router']:
        sys.modules.pop(name, None)


def conversation():
    return {
        'model': 'test',
        'messages': [
            {'role': 'system', 'content': 'System'},
            {'role': 'user', 'content': 'old'},
            {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'call'}]},
            {'role': 'tool', 'content': 'result', 'tool_call_id': 'call'},
            {'role': 'user', 'content': 'current'},
        ],
    }


def test_context_order_preserves_session_tools_and_no_raw_event(adapter):
    hooks, user, meta, _ = adapter
    data = conversation()
    before = deepcopy(data)
    result = asyncio.run(hooks.prepare(None, data, user, meta, {}))
    assert result['messages'][1:] == before['messages'][1:]
    assert result['messages'][0]['content'].startswith('System')
    assert '<kakam_memory>' in result['messages'][0]['content']
    emitter = AsyncMock()
    asyncio.run(hooks.emit_composition(result, meta, emitter))
    event = emitter.call_args.args[0]
    assert event['type'] == 'kakam:memory' and event['data']['cache_hit']
    assert '中文' not in str(event) and 'memory_text' not in event['data']
    from open_webui.kakam.memory.details import lookup

    snapshot = lookup(event['data']['detail_id'], user.id)
    assert snapshot['details'].sections[1].kind == 'long_term'
    assert '中文' in snapshot['details'].sections[1].content


def test_timeout_fails_open(adapter):
    hooks, user, meta, _ = adapter

    async def slow(*args, **kwargs):
        await asyncio.sleep(2)

    hooks.client.call.side_effect = slow
    data = conversation()
    before = deepcopy(data)
    assert asyncio.run(hooks.prepare(None, data, user, meta, {})) == before
    assert meta['kakam_memory']['status'] == 'unavailable'


@pytest.mark.parametrize('chat_id', ['temporary:x', 'local:x', 'channel:x', None])
def test_temporary_and_channel_never_read_write(adapter, chat_id):
    hooks, user, meta, _ = adapter
    meta['chat_id'] = chat_id
    asyncio.run(hooks.prepare(None, conversation(), user, meta, {}))
    asyncio.run(hooks.after_turn(None, user, {}, meta, []))
    hooks.client.call.assert_not_called()


def test_ownership_permission_optout_and_shadow(adapter, monkeypatch):
    hooks, user, meta, chats = adapter
    chats.is_chat_owner.return_value = False
    asyncio.run(hooks.prepare(None, conversation(), user, meta, {}))
    hooks.client.call.assert_not_called()
    chats.is_chat_owner.return_value = True
    user.settings = {'ui': {'kakamMemory': {'enabled': False}}}
    asyncio.run(hooks.prepare(None, conversation(), user, meta, {}))
    hooks.client.call.assert_not_called()
    user.settings = {}
    monkeypatch.setattr(hooks, 'allowed', AsyncMock(return_value=False))
    asyncio.run(hooks.prepare(None, conversation(), user, meta, {}))
    hooks.client.call.assert_not_called()
    monkeypatch.setattr(hooks, 'allowed', AsyncMock(return_value=True))
    monkeypatch.setenv('KAKAM_MEMORY_RECALL_MODE', 'shadow')
    data = conversation()
    before = deepcopy(data)
    assert asyncio.run(hooks.prepare(None, data, user, meta, {})) == before
    assert meta['kakam_memory']['status'] == 'shadow'


def test_write_uses_persisted_user_not_injected_or_assistant_text(adapter):
    hooks, user, meta, chats = adapter
    asyncio.run(hooks.after_turn(None, user, {}, meta, [{'role': 'assistant', 'content': 'invented'}]))
    args = hooks.client.call.call_args.args
    assert args[1] == '/v1/events/turn-completed'
    assert args[2] == 'alice' and args[3]['evidence'] == '请记住中文'
    chats.get_message_by_id_and_message_id.return_value = {'role': 'assistant', 'content': 'invented'}
    hooks.client.call.reset_mock()
    asyncio.run(hooks.after_turn(None, user, {}, meta, []))
    hooks.client.call.assert_not_called()


def test_composition_persisted_without_content_and_error_turn_not_written(adapter):
    hooks, user, meta, chats = adapter
    meta['kakam_composition'] = {'segments': [{'kind': 'system', 'characters': 30}]}
    chats.get_message_by_id_and_message_id.return_value = {
        'role': 'assistant',
        'meta': {'other': True},
        'error': 'provider failed',
    }
    asyncio.run(hooks.after_turn(None, user, {}, meta, []))
    saved = chats.upsert_message_to_chat_by_id_and_message_id.call_args.args[2]
    assert saved['meta']['other'] is True
    assert saved['meta']['kakamMemory'] == meta['kakam_composition']
    hooks.client.call.assert_not_called()


def test_bff_uses_authenticated_user_not_browser_identity(adapter, monkeypatch):
    hooks, user, _, _ = adapter
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient

    async def verified(authorization: str = Header(default='')):
        if authorization != 'Bearer test-login':
            raise HTTPException(401)
        return user

    monkeypatch.setitem(sys.modules, 'open_webui.utils.auth', types.SimpleNamespace(get_verified_user=verified))
    router = importlib.import_module('open_webui.kakam.memory.router')
    app = FastAPI()
    app.include_router(router.router, prefix='/api/custom/memory')
    hooks.client.call.return_value = []
    with TestClient(app) as client:
        assert client.get('/api/custom/memory').status_code == 401
        response = client.get(
            '/api/custom/memory', headers={'Authorization': 'Bearer test-login', 'X-Memory-User': 'victim'}
        )
        assert response.status_code == 200
        assert hooks.client.call.call_args.args[2] == 'alice'
        from open_webui.kakam.memory.details import remember

        snapshot = remember('alice', 'chat', 'reply', {'system': ['admin secret'], 'current': ['user text']})
        path = f'/api/custom/memory/context/{snapshot}'
        headers = {'Authorization': 'Bearer test-login'}
        assert client.get(path).status_code == 401
        result = client.get(path, headers=headers)
        assert result.status_code == 200 and result.headers['cache-control'] == 'no-store'
        assert result.json()['sections'][0]['content'] == 'admin secret'
        user.role = 'user'
        result = client.get(path, headers=headers)
        assert result.json()['sections'][0]['restricted'] is True
        assert 'admin secret' not in result.text
        assert result.json()['sections'][1]['content'] == 'user text'
        user.id = 'bob'
        assert client.get(path, headers=headers).status_code == 404
        user.id = 'alice'
        chats = adapter[3]
        chats.is_chat_owner.return_value = False
        assert client.get(path, headers=headers).status_code == 404
        chats.is_chat_owner.return_value = True
        user.role = 'admin'
        from open_webui.kakam.memory.activity import summarize

        read_activity = AsyncMock(return_value=summarize([], 30))
        monkeypatch.setattr(router, 'get_activity', read_activity)
        monkeypatch.setenv('KAKAM_MEMORY_ENABLED', 'false')
        headers = {'Authorization': 'Bearer test-login', 'X-Memory-User': 'victim'}
        assert client.get('/api/custom/memory/activity?days=30', headers=headers).status_code == 200
        read_activity.assert_awaited_once_with('alice', 30)
        assert client.get('/api/custom/memory/activity').status_code == 401
        assert client.get('/api/custom/memory/activity?days=181', headers=headers).status_code == 422
        monkeypatch.setattr(router, 'require_permission', AsyncMock(side_effect=HTTPException(403)))
        assert client.get('/api/custom/memory', headers={'Authorization': 'Bearer test-login'}).status_code == 403
        assert client.get('/api/custom/memory/activity', headers=headers).status_code == 403
        assert client.get(path, headers=headers).status_code == 403


def test_preview_failure_does_not_break_chat(adapter, monkeypatch):
    hooks, user, meta, _ = adapter
    data = asyncio.run(hooks.prepare(None, conversation(), user, meta, {}))

    def fail(*args, **kwargs):
        raise RuntimeError('preview failure')

    monkeypatch.setattr(hooks, 'remember', fail)
    emitter = AsyncMock()
    asyncio.run(hooks.emit_composition(data, meta, emitter))
    assert 'detail_id' not in emitter.call_args.args[0]['data']
    assert len(emitter.call_args.args[0]['data']['segments']) == 4
