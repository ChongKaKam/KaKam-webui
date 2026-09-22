import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response

from open_webui.internal.db import get_async_session
from open_webui.models.chat_messages import ChatMessages
from open_webui.utils.auth import get_admin_user

from .service import SiteUsage, site_usage

router = APIRouter()


@router.get('/site', response_model=SiteUsage)
async def site_token_usage(response: Response, user=Depends(get_admin_user), db=Depends(get_async_session)):
    response.headers['Cache-Control'] = 'private, no-store'
    try:
        async with asyncio.timeout(6):
            return await site_usage(ChatMessages.get_token_usage_by_user, db)
    except TimeoutError:
        raise HTTPException(504, 'Usage statistics timed out') from None
