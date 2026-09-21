import json

import aiohttp

from .service import ProbeError


async def fetch_json(session, method, url, *, ssl=True, **kwargs):
    try:
        async with session.request(method, url, allow_redirects=False, ssl=ssl, **kwargs) as response:
            if not 200 <= response.status < 300:
                message = {
                    401: '认证或访问权限未通过，请检查 API Key 和模型权限。',
                    403: '认证或访问权限未通过，请检查 API Key 和模型权限。',
                    404: '接口或模型不存在；部分供应商不提供 models 接口，请核对 Base URL。',
                    429: '供应商限制了请求，请检查配额或稍后重试。',
                }.get(response.status, f'供应商返回 HTTP {response.status}，请核对配置及服务状态。')
                raise ProbeError(message, 502)
            # A single image can be large; bound reads without logging or persisting payloads.
            content = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                content.extend(chunk)
                if len(content) > 32 * 1024 * 1024:
                    raise ProbeError('测试响应超过大小限制，未读取或保存完整结果。', 502)
            try:
                return json.loads(content)
            except (ValueError, UnicodeError):
                raise ProbeError('供应商未返回有效 JSON，请检查 Base URL。', 502) from None
    except TimeoutError:
        raise ProbeError('连接或模型验证超时，请稍后重试。', 504) from None
    except aiohttp.ClientError:
        raise ProbeError('无法连接供应商，请检查地址、网络和 TLS 证书。', 502) from None
    except ValueError:
        raise ProbeError('请求地址或凭据格式不正确，请检查配置。', 400) from None
