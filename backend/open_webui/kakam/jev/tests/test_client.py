import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from open_webui.kakam.jev.client import JevClient, JevError
from open_webui.kakam.jev.schemas import EvaluationRequest
from test_contracts import answer_body, request_body


@pytest.mark.asyncio
async def test_exact_api_contract_authorization_and_model_list():
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'models': [{'name': 'jev-latest'}]})
        return httpx.Response(200, json=answer_body())

    client = JevClient('https://api.typesafe.ai/v1', 'secret-test-key', transport=httpx.MockTransport(handle))
    assert await client.check_connection() >= 0
    result = await client.evaluate(EvaluationRequest.model_validate(request_body()))
    assert str(calls[1].url) == 'https://api.typesafe.ai/v1/systemone'
    assert calls[1].headers['Authorization'] == 'Bearer secret-test-key'
    assert json.loads(calls[1].content) == {**request_body(), 'model': 'jev-latest'}
    assert result.answers['team'].choice == 'billing'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'status,code',
    [
        (401, 'authentication'),
        (403, 'authentication'),
        (422, 'invalid_evaluation'),
        (429, 'rate_limited'),
        (529, 'rate_limited'),
        (500, 'provider_error'),
        (307, 'provider_error'),
    ],
)
async def test_errors_are_sanitized_and_redirects_not_followed(status, code):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status,
            text='private-test-key and upstream diagnostics',
            headers={'Location': 'https://another-host.invalid/'},
        )

    client = JevClient('https://fixture.invalid/v1', 'private-test-key', transport=httpx.MockTransport(handle))
    with patch('open_webui.kakam.jev.client.asyncio.sleep', AsyncMock()):
        with pytest.raises(JevError) as caught:
            await client.evaluate(EvaluationRequest.model_validate(request_body()))
    assert caught.value.code == code
    assert 'private-test-key' not in str(caught.value)
    assert len(calls) == (3 if status in (429, 529) else 1)
    assert all(request.url.host == 'fixture.invalid' for request in calls)


@pytest.mark.asyncio
async def test_timeout_and_connection_errors_are_distinct():
    for error, code in [(httpx.ReadTimeout('secret'), 'timeout'), (httpx.ConnectError('secret'), 'unavailable')]:

        def handle(request):
            raise error

        client = JevClient('https://fixture.invalid/v1', 'key', transport=httpx.MockTransport(handle))
        with pytest.raises(JevError) as caught:
            await client.check_connection()
        assert caught.value.code == code
        assert 'secret' not in str(caught.value)


@pytest.mark.asyncio
async def test_unconfigured_never_calls_network():
    handler = AsyncMock()
    with pytest.raises(JevError, match='配置'):
        await JevClient('https://fixture.invalid/v1', '', transport=httpx.MockTransport(handler)).check_connection()
    handler.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_success_response_not_connected():
    client = JevClient(
        'https://fixture.invalid/v1',
        'key',
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'models': []})),
    )
    with pytest.raises(JevError) as caught:
        await client.check_connection()
    assert caught.value.code == 'model_unavailable'


@pytest.mark.asyncio
async def test_wrong_answer_ids_rejected():
    body = answer_body()
    body['answers'].pop('refund')
    client = JevClient(
        'https://fixture.invalid/v1',
        'key',
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    with pytest.raises(JevError) as caught:
        await client.evaluate(EvaluationRequest.model_validate(request_body()))
    assert caught.value.code == 'invalid_response'


@pytest.mark.asyncio
async def test_wall_clock_deadline_bounds_the_entire_provider_call():
    async def handle(request):
        await asyncio.sleep(10)
        return httpx.Response(200, json=answer_body())

    client = JevClient('https://fixture.invalid/v1', 'key', timeout=0.01, transport=httpx.MockTransport(handle))
    async with asyncio.timeout(1):
        with pytest.raises(JevError) as caught:
            await client.evaluate(EvaluationRequest.model_validate(request_body()))
    assert caught.value.code == 'timeout'
