"""Reusable async Jev transport; depends only on httpx and typed contracts."""

import asyncio
import json
import time

import httpx
from pydantic import ValidationError

from .schemas import MODEL, EvaluationRequest, EvaluationResponse


class JevError(Exception):
    def __init__(self, message: str, code: str = 'provider_error', status: int = 502):
        super().__init__(message)
        self.code = code
        self.status = status


class JevClient:
    def __init__(self, base_url: str, api_key: str, *, transport=None, timeout: float = 35):
        self.base_url = base_url
        self._api_key = api_key
        self.transport = transport
        self.timeout = timeout

    async def _call(self, method: str, path: str, body=None):
        if not self._api_key:
            raise JevError('请先由管理员配置 Jev API Key。', 'not_configured', 409)
        # Do not follow redirects: a gateway must never forward this credential to another host.
        try:
            async with (
                asyncio.timeout(self.timeout),
                httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=10), transport=self.transport, follow_redirects=False
                ) as client,
            ):
                for attempt in range(3):
                    async with client.stream(
                        method,
                        f'{self.base_url}{path}',
                        json=body,
                        headers={'Authorization': f'Bearer {self._api_key}', 'Accept': 'application/json'},
                    ) as response:
                        if response.status_code in (429, 529) and attempt < 2:
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue
                        self._check_status(response.status_code)
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw) > 1_000_000:
                                raise JevError('Jev 响应超过大小限制。', 'invalid_response')
                        return json.loads(raw)
        except (httpx.TimeoutException, TimeoutError):
            raise JevError('Jev 响应超时，请稍后重试。', 'timeout', 504) from None
        except httpx.RequestError:
            raise JevError('无法连接 Jev，请检查 Base URL 和网络。', 'unavailable', 503) from None
        except (ValueError, UnicodeError):
            raise JevError('Jev 返回了无法解析的响应。', 'invalid_response') from None

    @staticmethod
    def _check_status(status: int):
        if 200 <= status < 300:
            return
        if status in (401, 403):
            raise JevError('Jev 鉴权失败，请管理员检查 API Key。', 'authentication')
        if status in (429, 529):
            raise JevError('Jev 当前繁忙或已达调用限额，请稍后重试。', 'rate_limited', 429)
        if status == 422:
            raise JevError('Jev 拒绝了判断请求，请调整输入后重试。', 'invalid_evaluation', 422)
        raise JevError(f'Jev 服务请求失败（HTTP {status}）。', 'provider_error')

    async def check_connection(self) -> int:
        started = time.monotonic()
        data = await self._call('GET', '/models')
        if (
            not isinstance(data, dict)
            or not isinstance(data.get('models'), list)
            or not any(isinstance(item, dict) and item.get('name') == MODEL for item in data['models'])
        ):
            raise JevError('连接已响应，但未提供 jev-latest 模型。', 'model_unavailable')
        return round((time.monotonic() - started) * 1000)

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResponse:
        data = await self._call('POST', '/systemone', request.model_dump(exclude_none=True))
        try:
            return EvaluationResponse.model_validate(data).validate_for(request)
        except (ValidationError, ValueError):
            raise JevError('Jev 响应与判断契约不一致，未展示无效结果。', 'invalid_response') from None
