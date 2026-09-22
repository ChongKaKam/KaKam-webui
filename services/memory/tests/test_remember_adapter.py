import importlib
import sys
import types
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest_plugins = ['test_hooks']


def mount(adapter, monkeypatch):
    hooks, user, _, chats = adapter

    async def verified():
        return user

    monkeypatch.setitem(sys.modules, 'open_webui.utils.auth', types.SimpleNamespace(get_verified_user=verified))
    for name in ('open_webui.kakam.memory.router', 'open_webui.kakam.memory.manager'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module('open_webui.kakam.memory.router')
    chats.get_message_by_id_and_message_id.side_effect = lambda chat_id, message_id: {
        'answer': {'role': 'assistant', 'done': True, 'parentId': 'question'},
        'question': {'role': 'user', 'content': 'Question'},
    }.get(message_id)
    hooks.client.call.return_value = {'created': True, 'id': 'memory-id'}
    app = FastAPI()
    app.include_router(module.router, prefix='/api/custom/memory')
    return TestClient(app)


def body(**changes):
    return {
        'content': '用户确认保留的问答',
        'kind': 'episode',
        'source': {'external_chat_id': 'chat', 'external_message_id': 'answer'},
        **changes,
    }


def test_confirmed_memory_uses_authenticated_owner_and_verified_source(adapter, monkeypatch):
    c = mount(adapter, monkeypatch)
    hooks, _, _, chats = adapter
    result = c.post('/api/custom/memory', json=body(owner='bob', kind='instruction'))
    assert result.status_code == 200 and result.json()['created']
    assert hooks.client.call.call_args.args[:3] == ('POST', '/v1/memories', 'alice')
    sent = hooks.client.call.call_args.args[3]
    assert sent['kind'] == 'episode' and 'owner' not in sent
    assert sent['source'] == body()['source']
    chats.is_chat_owner.assert_awaited_once_with('chat', 'alice')


@pytest.mark.parametrize(
    'source',
    [
        {'external_chat_id': 'temporary:chat', 'external_message_id': 'answer'},
        {'external_chat_id': 'local:chat', 'external_message_id': 'answer'},
        {'external_chat_id': 'channel:chat', 'external_message_id': 'answer'},
        {'external_chat_id': 'chat', 'external_message_id': 'missing'},
        {'external_chat_id': 'chat', 'external_message_id': 'question'},
    ],
)
def test_invalid_source_cannot_write(adapter, monkeypatch, source):
    c = mount(adapter, monkeypatch)
    assert c.post('/api/custom/memory', json=body(source=source)).status_code in (404, 422)
    adapter[0].client.call.assert_not_called()


def test_other_users_chat_and_missing_permission_cannot_write(adapter, monkeypatch):
    c = mount(adapter, monkeypatch)
    hooks, user, _, chats = adapter
    chats.is_chat_owner.return_value = False
    assert c.post('/api/custom/memory', json=body()).status_code == 404
    chats.is_chat_owner.return_value = True
    user.role = 'user'
    monkeypatch.setattr(sys.modules['open_webui.kakam.memory.auth'], 'has_permission', AsyncMock(return_value=False))
    assert c.post('/api/custom/memory', json=body()).status_code == 403
    hooks.client.call.assert_not_called()


@pytest.mark.parametrize('mode', ['off', 'shadow'])
def test_disabled_writes_cannot_save(adapter, monkeypatch, mode):
    c = mount(adapter, monkeypatch)
    monkeypatch.setenv('KAKAM_MEMORY_WRITE_MODE', mode)
    assert c.post('/api/custom/memory', json=body()).status_code == 409
    adapter[0].client.call.assert_not_called()


@pytest.mark.parametrize(
    'answer',
    [
        {'role': 'assistant', 'done': False, 'parentId': 'question'},
        {'role': 'assistant', 'done': True, 'error': {'content': 'failure'}, 'parentId': 'question'},
        {'role': 'assistant', 'done': True, 'parentId': 'missing'},
    ],
)
def test_unfinished_failed_or_orphan_reply_is_rejected(adapter, monkeypatch, answer):
    c = mount(adapter, monkeypatch)
    adapter[3].get_message_by_id_and_message_id.side_effect = lambda chat, mid: answer if mid == 'answer' else None
    assert c.post('/api/custom/memory', json=body()).status_code == 422
    adapter[0].client.call.assert_not_called()


def test_service_failure_is_reported_without_success(adapter, monkeypatch):
    c = mount(adapter, monkeypatch)
    adapter[0].client.call.side_effect = httpx.ConnectError('offline')
    assert c.post('/api/custom/memory', json=body()).status_code == 503
