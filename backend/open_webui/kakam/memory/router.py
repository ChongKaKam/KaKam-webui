from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from open_webui.utils.auth import get_verified_user

from . import client
from .activity import MemoryActivity, get_activity
from .auth import require_permission
from .details import ContextDetails, lookup
from .remember import MemorySource, verify_source

router = APIRouter()


class NewMemory(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    kind: Literal['profile', 'preference', 'instruction', 'fact', 'episode'] = 'fact'
    source: MemorySource | None = None


async def proxy(method, path, user, body=None):
    await require_permission(user)
    if not client.enabled():
        raise HTTPException(503, 'KaKam Memory is not enabled on this server')
    try:
        return await client.call(method, path, user.id, body, timeout=30)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 404:
            raise HTTPException(404, 'Memory not found') from None
        if code == 409:
            raise HTTPException(409, 'Memory changed or writes disabled; refresh and retry') from None
        if code in (400, 422):
            raise HTTPException(422, 'Memory was rejected: check content and sensitive information') from None
        raise HTTPException(503, 'Memory service unavailable') from None
    except (httpx.HTTPError, RuntimeError, ValueError):
        raise HTTPException(503, 'Memory service unavailable') from None


@router.get('/policies')
async def policies(user=Depends(get_verified_user)):
    await require_permission(user)
    if not client.enabled():
        return {'enabled': False, 'available': False, 'policies': []}
    try:
        items = await proxy('GET', '/v1/policies', user)
        return {'enabled': True, 'available': True, 'policies': items}
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        return {'enabled': True, 'available': False, 'policies': []}


@router.get('')
async def memories(user=Depends(get_verified_user)):
    return await proxy('GET', '/v1/memories', user)


@router.post('')
async def add(body: NewMemory, user=Depends(get_verified_user)):
    from .manager import writable

    writable()
    await require_permission(user)
    if body.source:
        await verify_source(body.source, user)
    payload = body.model_dump(exclude_none=True)
    if body.source:
        payload['kind'] = 'episode'
    return await proxy('POST', '/v1/memories', user, payload)


@router.get('/activity', response_model=MemoryActivity)
async def activity(days: int = Query(default=30, ge=7, le=180), user=Depends(get_verified_user)):
    await require_permission(user)
    # Saved counts remain readable when the independent Memory service is down.
    return await get_activity(user.id, days)


@router.delete('/{memory_id}')
async def delete(memory_id: UUID, user=Depends(get_verified_user)):
    from .manager import writable

    writable()
    return await proxy('DELETE', f'/v1/memories/{memory_id}', user)


@router.get('/context/{snapshot_id}', response_model=ContextDetails)
async def context_details(snapshot_id: UUID, response: Response, user=Depends(get_verified_user)):
    from open_webui.models.chats import Chats

    await require_permission(user)
    response.headers['Cache-Control'] = 'no-store'
    item = lookup(str(snapshot_id), user.id)
    if not item or not await Chats.is_chat_owner(item['chat_id'], user.id):
        raise HTTPException(404, 'Context preview expired or unavailable', headers={'Cache-Control': 'no-store'})
    details = item['details']
    # A model's administrator-provided System prompt is not a public contract.
    if user.role != 'admin':
        for section in details.sections:
            if section.kind == 'system':
                section.content = ''
                section.restricted = True
                section.truncated = False
    return details
