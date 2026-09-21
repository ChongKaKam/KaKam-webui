"""Run with pytest; all provider responses are fixtures, never billable requests."""

import asyncio
import base64
from unittest.mock import AsyncMock

import aiohttp
import pytest
from pydantic import ValidationError

from .schemas import ImageProbe
from .service import ProbeError, probe
from .transport import fetch_json

PNG = base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()


def form(**changes):
    return ImageProbe(
        **{
            'engine': 'openai',
            'base_url': 'https://provider.test/v1',
            'api_key': 'private-test-key',
            'model': 'image-one',
            **changes,
        }
    )


def run(value):
    return asyncio.run(value)


@pytest.mark.parametrize(
    'url',
    [
        'ftp://host',
        'https://user:pass@host',
        'https://host?key=secret',
        'https://host/#fragment',
        'https://host:bad',
        'https://host:99999',
    ],
)
def test_invalid_urls_are_rejected(url):
    with pytest.raises(ValidationError):
        form(base_url=url)


def test_key_is_redacted_in_schema_repr():
    assert 'private-test-key' not in repr(form())


def test_models_checks_real_list_and_does_not_generate():
    fetch = AsyncMock(return_value={'data': [{'id': 'image-one'}, {'id': 'text-only'}]})
    result = run(probe(form(), fetch))
    assert result['model_status'] == 'available'
    assert result['complete']
    assert fetch.call_args.args == ('GET', 'https://provider.test/v1/models')
    assert fetch.call_args.kwargs['headers']['Authorization'] == 'Bearer private-test-key'
    assert fetch.await_count == 1


@pytest.mark.parametrize('data,status', [({'data': []}, 'not_listed'), ({'data': [], 'has_more': True}, 'unknown')])
def test_model_absence_requires_complete_list(data, status):
    assert run(probe(form(), AsyncMock(return_value=data)))['model_status'] == status


def test_gemini_models_follow_pages_and_use_separate_auth():
    fetch = AsyncMock(
        side_effect=[
            {'models': [{'name': 'models/text'}], 'nextPageToken': 'next'},
            {'models': [{'name': 'models/image-one'}]},
        ]
    )
    result = run(probe(form(engine='gemini', model='models/image-one'), fetch))
    assert result['model_status'] == 'available'
    assert fetch.call_args.kwargs['params'] == {'pageToken': 'next'}
    assert fetch.call_args.kwargs['headers'] == {'x-goog-api-key': 'private-test-key'}
    assert result['models'][1]['id'] == 'image-one'


def test_unending_pagination_is_bounded():
    fetch = AsyncMock(return_value={'models': [], 'nextPageToken': 'same'})
    assert not run(probe(form(engine='gemini'), fetch))['complete']
    assert fetch.await_count == 10


def test_invalid_model_response_is_not_a_connection_success():
    with pytest.raises(ProbeError, match='列表格式'):
        run(probe(form(), AsyncMock(return_value={'error': 'hidden'})))


def test_generation_uses_one_image_and_current_parameters():
    fetch = AsyncMock(return_value={'data': [{'b64_json': PNG}]})
    assert run(
        probe(
            form(
                action='generate',
                api_version='preview',
                size='1024x1024',
                params={'n': 99, 'model': 'wrong', 'prompt': 'wrong', 'quality': 'low', 'stream': True},
            ),
            fetch,
        )
    ) == {'generated': True}
    assert fetch.call_args.args == ('POST', 'https://provider.test/v1/images/generations')
    payload = fetch.call_args.kwargs['json']
    assert payload['n'] == 1 and payload['model'] == 'image-one'
    assert payload['quality'] == 'low' and payload['size'] == '1024x1024'
    assert payload['response_format'] == 'b64_json'
    assert 'stream' not in payload and payload['prompt'] != 'wrong'
    assert fetch.call_args.kwargs['params'] == {'api-version': 'preview'}


def test_url_response_model_uses_native_format_rule():
    fetch = AsyncMock(return_value={'data': [{'url': 'https://images.test/result.png'}]})
    run(probe(form(action='generate', model='custom-image'), fetch, '^custom-image'))
    assert 'response_format' not in fetch.call_args.kwargs['json']


@pytest.mark.parametrize(
    'method,response',
    [
        ('predict', {'predictions': [{'bytesBase64Encoded': PNG}]}),
        ('generateContent', {'candidates': [{'content': {'parts': [{'inlineData': {'data': PNG}}]}}]}),
    ],
)
def test_gemini_generation_protocol(method, response):
    fetch = AsyncMock(return_value=response)
    assert run(probe(form(engine='gemini', action='generate', method=method), fetch))['generated']
    assert fetch.call_args.args[1].endswith(f'/models/image-one:{method}')
    if method == 'predict':
        assert fetch.call_args.kwargs['json']['parameters']['sampleCount'] == 1


@pytest.mark.parametrize(
    'payload',
    [
        None,
        {},
        {'data': None},
        {'data': [None]},
        {'data': [{'b64_json': 'not an image'}]},
        {'data': [{'url': 'javascript:bad'}]},
        {'choices': [{'message': {'content': 'done'}}]},
    ],
)
def test_no_image_is_not_reported_as_generation_success(payload):
    with pytest.raises(ProbeError, match='没有返回图片'):
        run(probe(form(action='generate'), AsyncMock(return_value=payload)))


def test_empty_model_never_calls_provider():
    fetch = AsyncMock()
    with pytest.raises(ProbeError):
        run(probe(form(action='generate', model=''), fetch))
    fetch.assert_not_called()


class Response:
    def __init__(self, status=200, body=b'{"data": []}'):
        self.status, self.body, self.content = status, body, self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        yield self.body


class Session:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def request(self, *args, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def test_transport_disables_redirects_and_parses_json():
    session = Session(Response())
    assert run(fetch_json(session, 'GET', 'https://fixture.test')) == {'data': []}
    assert session.kwargs['allow_redirects'] is False


@pytest.mark.parametrize('status', [301, 401, 403, 404, 429, 500])
def test_upstream_errors_do_not_echo_secrets(status):
    with pytest.raises(ProbeError) as error:
        run(fetch_json(Session(Response(status, b'private-test-key')), 'GET', 'https://fixture.test'))
    assert 'private-test-key' not in str(error.value)
    assert error.value.status == 502


@pytest.mark.parametrize('body', [b'<html>secret</html>', b'x' * (32 * 1024 * 1024 + 1)])
def test_invalid_or_oversized_response_fails(body):
    with pytest.raises(ProbeError):
        run(fetch_json(Session(Response(body=body)), 'GET', 'https://fixture.test'))


@pytest.mark.parametrize(
    'error,status', [(TimeoutError(), 504), (aiohttp.ClientError('secret'), 502), (ValueError('secret'), 400)]
)
def test_network_errors_are_sanitized(error, status):
    with pytest.raises(ProbeError) as result:
        run(fetch_json(Session(error=error), 'GET', 'https://fixture.test'))
    assert result.value.status == status
    assert 'secret' not in str(result.value)
