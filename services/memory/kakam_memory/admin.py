"""Administrator-only provider configuration; never expose provider responses or keys."""

import asyncio
import hashlib
import hmac
import json
import time
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .provider_config import ConfigView, ProbeResult, ProviderForm, ProviderKind, ResetForm
from .providers import Providers


def router(cfg, store, owner):
    api = APIRouter(prefix='/v1/admin/config')

    async def administrator(request: Request, response: Response, user=Depends(owner)):
        response.headers['Cache-Control'] = 'no-store'
        stamp = request.headers.get('x-memory-admin-time', '')
        try:
            valid_time = -5 <= time.time() - int(stamp) <= 60
        except ValueError:
            valid_time = False
        try:
            body = await request.json() if await request.body() else None
        except ValueError:
            raise HTTPException(400, 'Invalid JSON request') from None
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        payload = f'{stamp}\n{user}\n{request.method}\n{request.url.path}\n{digest}'
        expected = hmac.new(cfg.service_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not valid_time or not hmac.compare_digest(expected, request.headers.get('x-memory-admin-signature', '')):
            raise HTTPException(403, 'A signed administrator request is required')
        return user

    @api.get('', response_model=ConfigView)
    def read(user=Depends(administrator)):
        return store.view(user)

    @api.put('/{kind}', response_model=ConfigView)
    def save(kind: ProviderKind, body: ProviderForm, user=Depends(administrator)):
        return store.save(user, kind, body)

    @api.post('/{kind}/reset', response_model=ConfigView)
    def reset(kind: ProviderKind, body: ResetForm, user=Depends(administrator)):
        return store.save(user, kind, body, reset=True)

    @api.post('/{kind}/test', response_model=ProbeResult)
    async def test(kind: ProviderKind, body: ProviderForm, user=Depends(administrator)):
        value = await asyncio.to_thread(store.candidate, user, kind, body)
        # Probe the draft, without persisting or using private conversation data.
        value['enabled'] = True
        effective = await asyncio.to_thread(store.settings_for, user, kind, value)
        provider = Providers(effective)
        start = time.monotonic()
        status, message, http_status = 'ready', '连接成功，返回格式已验证', None
        try:
            if kind == 'context':
                await provider.summarize('', 'Synthetic connection test: the next step is to verify configuration.')
            else:
                await provider.embed(f'Memory configuration check {uuid4()}', user)
        except httpx.HTTPStatusError as exc:
            http_status = exc.response.status_code
            status, message = {
                401: ('authentication_failed', 'API Key 无效或已过期'),
                403: ('permission_denied', 'API Key 无权访问此模型或服务'),
                404: ('not_found', '检查 Base URL、模型名称和 API 协议'),
                429: ('rate_limited', '请求限流或额度不足'),
            }.get(http_status, ('provider_error', '模型服务拒绝请求；请核对模型、协议和参数支持'))
        except (httpx.TimeoutException, TimeoutError):
            status, message = 'timeout', '请求超时；检查网络或调整超时时间'
        except httpx.RequestError:
            status, message = 'connection_failed', '无法连接模型服务；检查地址、DNS、TLS 或网络'
        except (ValueError, KeyError, IndexError, TypeError):
            status, message = 'invalid_response', '返回格式、向量维度或摘要不符合要求；也可能模型未配置'
        return {
            'ok': status == 'ready',
            'status': status,
            'message': message,
            'http_status': http_status,
            'elapsed_ms': round((time.monotonic() - start) * 1000),
        }

    return api
