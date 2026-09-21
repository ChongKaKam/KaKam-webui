"""Admin authentication adapter; provider configuration belongs to Memory Server."""

import json
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response

from open_webui.utils.auth import get_admin_user

from . import client

router = APIRouter(prefix='/admin/config')
ProviderKind = Literal['context', 'embedding']


async def proxy(method, path, user, response, body=None):
    response.headers['Cache-Control'] = 'no-store'
    if not client.enabled():
        raise HTTPException(503, '请先在部署配置中启用 KAKAM_MEMORY_ENABLED')
    if body is not None and len(json.dumps(body).encode()) > 20000:
        raise HTTPException(413, 'Configuration is too large')
    try:
        return await client.call(method, '/v1/admin/config' + path, user.id, body, timeout=65, admin=True)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in (409, 422, 503):
            # This private API returns only sanitized configuration errors, never upstream provider bodies.
            try:
                detail = exc.response.json().get('detail')
            except ValueError:
                detail = None
            raise HTTPException(
                code, detail if isinstance(detail, str) and len(detail) < 500 else 'Memory 配置请求失败'
            ) from None
        raise HTTPException(502, 'Memory 管理接口不可用；请确认服务版本及服务间鉴权配置') from None
    except (httpx.RequestError, RuntimeError):
        raise HTTPException(503, '无法连接 Memory 服务；请检查服务地址、密钥和运行状态') from None


@router.get('')
async def read(response: Response, user=Depends(get_admin_user)):
    return await proxy('GET', '', user, response)


@router.put('/{kind}')
async def save(kind: ProviderKind, body: dict, response: Response, user=Depends(get_admin_user)):
    return await proxy('PUT', f'/{kind}', user, response, body)


@router.post('/{kind}/reset')
async def reset(kind: ProviderKind, body: dict, response: Response, user=Depends(get_admin_user)):
    return await proxy('POST', f'/{kind}/reset', user, response, body)


@router.post('/{kind}/test')
async def test(kind: ProviderKind, body: dict, response: Response, user=Depends(get_admin_user)):
    return await proxy('POST', f'/{kind}/test', user, response, body)
