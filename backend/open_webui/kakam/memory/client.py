import hashlib
import hmac
import json
import os
import time

import httpx


def enabled():
    return os.getenv('KAKAM_MEMORY_ENABLED', 'false').lower() == 'true'


async def call(method, path, user_id, body=None, *, timeout=None, admin=False):
    url = os.getenv('KAKAM_MEMORY_SERVICE_URL', 'http://memory-api:8081').rstrip('/')
    key = os.getenv('KAKAM_MEMORY_SERVICE_KEY', '')
    if not key:
        raise RuntimeError('KAKAM_MEMORY_SERVICE_KEY is missing')
    timeout = timeout or max(0.1, min(30, int(os.getenv('KAKAM_MEMORY_TIMEOUT_MS', '1500')) / 1000))
    tenant = os.getenv('KAKAM_MEMORY_TENANT', 'default')
    headers = {'Authorization': f'Bearer {key}', 'X-Memory-User': user_id, 'X-Memory-Tenant': tenant}
    if admin:
        stamp = str(int(time.time()))
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        payload = f'{stamp}\n{tenant}:{user_id}\n{method}\n{path}\n{digest}'
        headers.update(
            {
                'X-Memory-Admin-Time': stamp,
                'X-Memory-Admin-Signature': hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest(),
            }
        )
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method,
            url + path,
            json=body,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()
