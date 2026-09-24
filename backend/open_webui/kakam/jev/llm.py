"""Open WebUI completion port: existing provider routing and model permissions."""

import asyncio
import json

from fastapi import Request
from starlette.responses import JSONResponse

from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.models import get_all_models, get_filtered_models

from .client import JevError


def supports_chat(model: dict) -> bool:
    # Native/provider metadata may explicitly contain null, not just omit keys.
    info = model.get('info') or {}
    meta = info.get('meta') or {}
    capabilities = meta.get('capabilities') or {}
    return bool(capabilities.get('chat', True))


async def prompt_models(request: Request, user) -> list[dict]:
    models = await get_all_models(request, user=user)
    models = await get_filtered_models(models, user)
    return [
        {'id': model['id'], 'name': model.get('name', model['id'])}
        for model in models
        if not model.get('pipe')
        and not model.get('direct')
        and model.get('owned_by') != 'arena'
        and supports_chat(model)
    ]


def completion_port(request: Request, user, model_id: str):
    async def complete(messages: list[dict[str, str]]) -> str:
        try:
            async with asyncio.timeout(90):
                response = await generate_chat_completion(
                    request=request,
                    user=user,
                    bypass_system_prompt=True,
                    form_data={
                        'model': model_id,
                        'messages': messages,
                        'stream': False,
                        'metadata': {'task': 'kakam_jev', 'user_id': user.id},
                    },
                )
            if isinstance(response, JSONResponse):
                if response.status_code >= 400:
                    raise ValueError('Completion failed')
                response = json.loads(response.body)
            if not isinstance(response, dict) or response.get('error'):
                raise ValueError('Invalid completion response')
            choice = response['choices'][0]
            content = choice['message'].get('content')
            if isinstance(content, list):
                content = '\n'.join(part['text'] for part in content if part.get('type') == 'text')
            if choice.get('finish_reason') == 'length' or not isinstance(content, str) or not content.strip():
                raise ValueError('Incomplete completion')
            return content
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise JevError('润色模型响应超时，请重试或更换模型。', 'llm_timeout', 504) from None
        except Exception:
            # Never expose upstream bodies, URLs, headers or credentials.
            raise JevError('润色模型调用失败，请检查模型权限或更换模型。', 'llm_error') from None

    return complete
