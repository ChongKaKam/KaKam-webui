import os

import httpx


def enabled():
    return os.getenv('KAKAM_MEMORY_ENABLED', 'false').lower() == 'true'


async def call(method, path, user_id, body=None, *, timeout=None):
    url = os.getenv('KAKAM_MEMORY_SERVICE_URL', 'http://memory-api:8081').rstrip('/')
    key = os.getenv('KAKAM_MEMORY_SERVICE_KEY', '')
    if not key:
        raise RuntimeError('KAKAM_MEMORY_SERVICE_KEY is missing')
    timeout = timeout or max(0.1, min(30, int(os.getenv('KAKAM_MEMORY_TIMEOUT_MS', '1500')) / 1000))
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method, url + path, json=body, headers={'Authorization': f'Bearer {key}', 'X-Memory-User': user_id}
        )
        response.raise_for_status()
        return response.json()
