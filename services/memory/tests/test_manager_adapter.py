import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest_plugins = ['test_hooks']


def mount(adapter, monkeypatch):
    hooks, user, meta, chats = adapter

    async def verified():
        return user

    monkeypatch.setitem(sys.modules, 'open_webui.utils.auth', types.SimpleNamespace(get_verified_user=verified))
    for name in ('open_webui.kakam.memory.router', 'open_webui.kakam.memory.manager'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = importlib.import_module('open_webui.kakam.memory.manager')
    monkeypatch.setattr(module, 'proxy', AsyncMock(return_value={'state': 'pending'}))
    app = FastAPI()
    app.include_router(module.router)
    return module, TestClient(app)


def test_bff_proposals_use_original_evidence_and_ownership(adapter, monkeypatch):
    hooks, user, meta, chats = adapter
    module, c = mount(adapter, monkeypatch)
    body = {'content': '中文', 'source_message_id': 'm1', 'evidence': 'forged', 'owner': 'victim', 'approve': True}
    assert c.post('/manager/sessions/chat/proposals', json=body).status_code == 200
    args = module.proxy.call_args.args
    assert args[2].id == 'alice'
    assert args[3]['evidence'] == '请记住中文'
    assert 'approve' not in args[3] and 'owner' not in args[3]
    chats.is_chat_owner.return_value = False
    assert c.get('/manager/sessions/chat').status_code == 404
    assert c.put('/manager/sessions/chat', json={}).status_code == 404
    assert c.post('/manager/sessions/chat/proposals', json=body).status_code == 404
    chats.is_chat_owner.return_value = True
    monkeypatch.setenv('KAKAM_MEMORY_WRITE_MODE', 'off')
    assert c.post('/manager/sessions/chat/proposals', json=body).status_code == 409


def test_adapter_compacts_original_messages_without_system_leak(adapter, monkeypatch):
    hooks, user, meta, _ = adapter
    module, _ = mount(adapter, monkeypatch)
    source = [
        {'role': 'system', 'content': 'private administrator prompt'},
        {'role': 'user', 'content': 'old question'},
        {
            'role': 'assistant',
            'output': [
                {'type': 'reasoning', 'content': [{'text': 'hidden reasoning'}]},
                {'type': 'message', 'content': [{'type': 'output_text', 'text': 'public answer'}]},
            ],
        },
        {'role': 'user', 'content': 'latest question'},
    ]
    hooks.client.call.return_value = {'cut': 2, 'summary': 'summary', 'state': 'compacted'}
    fallback = AsyncMock()
    result, summary, _ = asyncio.run(
        module.compact_messages(None, user, source, meta, 'test', {}, '', fallback=fallback)
    )
    assert result == [source[0], source[-1]]
    assert '<kakam_session_summary>' in summary
    payload = hooks.client.call.call_args.args[3]
    assert 'private administrator' not in str(payload) and 'hidden reasoning' not in str(payload)
    assert payload['messages'][1]['text'] == 'public answer'
    from open_webui.kakam.memory.composition import split_context

    summary_text = meta['kakam_session_summary']
    classified = split_context([{'role': 'system', 'content': 'system\n' + summary_text}], summary_text=summary_text)
    assert classified['session'] == [summary_text] and summary_text not in str(classified['system'])
    fallback.assert_not_called()
    hooks.client.call.side_effect = RuntimeError('offline')
    result = asyncio.run(module.compact_messages(None, user, source, meta, 'test', {}, '', fallback=fallback))
    assert result[0] == source and meta['kakam_compaction']['state'] == 'unavailable'
    assert module.normalize_message({'role': 'user', 'content': [{'type': 'image_url'}]}) is None
