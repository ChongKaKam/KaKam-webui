import importlib
import sys
import types
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from open_webui.kakam.jev.client import JevError


@pytest.fixture
def adapter():
    generate = AsyncMock(
        return_value={'choices': [{'message': {'content': '{"kind":"clarification","message":"Which?"}'}}]}
    )
    models = AsyncMock(return_value=[{'id': 'visible'}, {'id': 'private'}])
    filtered = AsyncMock(
        return_value=[
            {'id': 'visible'},
            {'id': 'pipe', 'pipe': True},
            {'id': 'direct', 'direct': True},
            {'id': 'arena', 'owned_by': 'arena'},
        ]
    )
    dependencies = {
        'open_webui.utils.chat': types.SimpleNamespace(generate_chat_completion=generate),
        'open_webui.utils.models': types.SimpleNamespace(get_all_models=models, get_filtered_models=filtered),
    }
    name = 'open_webui.kakam.jev.llm'
    previous = sys.modules.pop(name, None)
    try:
        with patch.dict(sys.modules, dependencies):
            yield importlib.import_module(name), generate, filtered
    finally:
        sys.modules.pop(name, None)
        if previous:
            sys.modules[name] = previous


@pytest.mark.asyncio
async def test_model_list_uses_native_permissions_and_excludes_client_only_models(adapter):
    module, _, filtered = adapter
    user = types.SimpleNamespace(id='user-id')
    assert await module.prompt_models(object(), user) == [{'id': 'visible', 'name': 'visible'}]
    assert filtered.call_args.args[1] is user


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'metadata',
    [
        {'info': None},
        {'info': {'meta': None}},
        {'info': {'meta': {'capabilities': None}}},
    ],
)
async def test_nullable_metadata_does_not_break_authorized_model_list(adapter, metadata):
    module, _, filtered = adapter
    filtered.return_value = [
        {'id': 'nullable', **metadata},
        {'id': 'chat', 'name': 'Chat model'},
        {'id': 'embedding', 'info': {'meta': {'capabilities': {'chat': False}}}},
        {'id': 'direct', 'direct': True, **metadata},
    ]
    assert await module.prompt_models(object(), types.SimpleNamespace(id='user-id')) == [
        {'id': 'nullable', 'name': 'nullable'},
        {'id': 'chat', 'name': 'Chat model'},
    ]


@pytest.mark.asyncio
async def test_dispatch_preserves_user_and_permission_check_without_chat_extensions(adapter):
    module, generate, _ = adapter
    user = types.SimpleNamespace(id='user-id')
    messages = [{'role': 'system', 'content': 'Compile'}]
    result = await module.completion_port(object(), user, 'visible')(messages)
    assert 'clarification' in result
    args = generate.call_args.kwargs
    assert args['user'] is user
    assert 'bypass_filter' not in args
    assert args['bypass_system_prompt'] is True
    assert args['form_data']['messages'] == messages
    assert args['form_data']['stream'] is False
    assert 'chat_id' not in args['form_data']
    assert 'tools' not in args['form_data']


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [HTTPException(403, 'secret provider detail'), TimeoutError('secret')])
async def test_llm_errors_are_sanitized(adapter, failure):
    module, generate, _ = adapter
    generate.side_effect = failure
    with pytest.raises(JevError) as error:
        await module.completion_port(object(), types.SimpleNamespace(id='id'), 'visible')([])
    assert 'secret' not in str(error.value)
