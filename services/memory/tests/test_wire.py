"""Actual HTTP bridge -> Memory API -> HTTP embedding fixture -> PostgreSQL.

This validates transport/config/auth wiring, not a production model provider.
"""

import asyncio
import socket
import threading
import time
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI, Request
from kakam_memory.app import create_app
from kakam_memory.config import Settings
from open_webui.kakam.memory import client

pytest_plugins = ['test_postgres']


@contextmanager
def serving(app):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError('Test server failed to start')
            time.sleep(0.02)
        assert server.started
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()


def test_real_http_bridge(repo, monkeypatch):
    upstream = FastAPI()
    requests = []

    @upstream.post('/v1/embeddings')
    async def embeddings(request: Request):
        body = await request.json()
        assert request.headers['Authorization'] == 'Bearer fixture-only'
        requests.append(body)
        return {'data': [{'embedding': [1, 0, 0]}]}

    with serving(upstream) as provider_url:
        cfg = Settings(
            database_url='unused',
            service_key='s' * 32,
            embedding_url=provider_url + '/v1',
            embedding_key='fixture-only',
            embedding_model='test',
            embedding_dimension=3,
            config_encryption_key='ab' * 32,
        )
        with serving(create_app(cfg, repo)) as memory_url:
            monkeypatch.setenv('KAKAM_MEMORY_SERVICE_URL', memory_url)
            monkeypatch.setenv('KAKAM_MEMORY_SERVICE_KEY', 's' * 32)
            monkeypatch.setenv('KAKAM_MEMORY_TENANT', 'wire')

            async def run():
                config = await client.call('GET', '/v1/admin/config', 'admin', admin=True)
                assert config['write_enabled'] and config['providers']['embedding']['api_key_set']
                view = config['providers']['embedding']
                form = {k: v for k, v in view.items() if k not in ('source', 'api_key_set')}
                saved = await client.call('PUT', '/v1/admin/config/embedding', 'admin', form, admin=True)
                assert saved['providers']['embedding']['source'] == 'database'
                added = await client.call('POST', '/v1/memories', 'alice', {'content': '中文回答'})
                assert added['created']
                recalled = await client.call(
                    'POST', '/v1/manager/prepare-turn', 'alice', {'session_id': 'chat', 'query': '语言'}
                )
                assert recalled['memories'][0]['id'] == added['id']
                assert await client.call('GET', '/v1/memories', 'bob') == []
                probe = await client.call('POST', '/v1/manager/probe', 'alice')
                assert probe['embedding'] == 'ready'

            asyncio.run(run())
        # API process recreation keeps data (not an in-process demonstration cache).
        with serving(create_app(cfg, repo)) as memory_url:
            monkeypatch.setenv('KAKAM_MEMORY_SERVICE_URL', memory_url)
            assert asyncio.run(client.call('GET', '/v1/memories', 'alice'))[0]['content'] == '中文回答'
        assert len(requests) >= 3
