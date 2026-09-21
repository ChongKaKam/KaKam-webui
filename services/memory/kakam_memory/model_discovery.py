"""Bounded, read-only OpenAI-compatible model discovery. IDs are not capability claims."""

import asyncio
import json

import httpx

from .domain import SECRET


async def list_models(config):
    timeout = min(config['timeout_seconds'], 20)
    key = config['api_key']
    headers = {'Authorization': f'Bearer {key}'} if key else {}
    async with asyncio.timeout(timeout), httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        async with client.stream('GET', config['base_url'] + '/models', headers=headers) as response:
            response.raise_for_status()
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > 1024 * 1024:
                    raise ValueError('Model list is too large')
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('data'), list):
        raise ValueError('Invalid model list')
    ids = set()
    for item in data['data']:
        model = item.get('id') if isinstance(item, dict) else None
        if (
            isinstance(model, str)
            and 0 < len(model) <= 200
            and model.strip()
            and not any(ord(c) < 32 or ord(c) == 127 for c in model)
            and not SECRET.search(model)
            and not (key and key in model)
        ):
            ids.add(model.strip())
    if data['data'] and not ids:
        raise ValueError('No valid model IDs')
    return {'models': sorted(ids)[:500], 'truncated': len(ids) > 500 or bool(data.get('has_more'))}
