import asyncio

from fastapi import APIRouter, Depends, HTTPException

from open_webui.config import IMAGE_URL_RESPONSE_MODELS_REGEX_PATTERN
from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL
from open_webui.utils.auth import get_admin_user
from open_webui.utils.session_pool import get_session

from .schemas import ImageProbe
from .service import ProbeError, probe
from .transport import fetch_json

router = APIRouter()


@router.post('/probe')
async def probe_images(form: ImageProbe, user=Depends(get_admin_user)):
    session = await get_session()

    async def fetch(method, url, **kwargs):
        return await fetch_json(session, method, url, ssl=AIOHTTP_CLIENT_SESSION_SSL, **kwargs)

    try:
        async with asyncio.timeout(120 if form.action == 'generate' else 25):
            return await probe(form, fetch, IMAGE_URL_RESPONSE_MODELS_REGEX_PATTERN)
    except TimeoutError:
        raise HTTPException(
            504,
            '测试超时；生成请求可能已被供应商处理，重试可能再次计费。'
            if form.action == 'generate'
            else '模型列表探测超时。',
        ) from None
    except ProbeError as exc:
        raise HTTPException(exc.status, str(exc)) from None
