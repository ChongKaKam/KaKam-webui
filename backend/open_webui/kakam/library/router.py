from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from open_webui.internal.db import get_async_session
from open_webui.utils.auth import get_verified_user

from . import repository
from .schemas import ChatDetail, EntryPage, NoteDetail, Summary


async def private_response(response: Response):
    response.headers['Cache-Control'] = 'private, no-store'


router = APIRouter(dependencies=[Depends(private_response)])


async def notes_allowed(user, db):
    from open_webui.models.config import Config
    from open_webui.utils.access_control import has_permission

    return bool(await Config.get('notes.enable')) and (
        user.role == 'admin'
        or await has_permission(user.id, 'features.notes', await Config.get('user.permissions'), db=db)
    )


@router.get('/summary', response_model=Summary)
async def get_summary(user=Depends(get_verified_user), db=Depends(get_async_session)):
    return await repository.summary(db, user.id, await notes_allowed(user, db))


@router.get('/entries', response_model=EntryPage)
async def get_entries(
    kind: Literal['chat', 'file', 'note'],
    q: str = Query('', max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    before: int | None = Query(None, gt=0),
    chat_id: str | None = None,
    user=Depends(get_verified_user),
    db=Depends(get_async_session),
):
    if kind == 'note' and not await notes_allowed(user, db):
        raise HTTPException(403, 'Notes are disabled')
    return await repository.entries(db, user.id, kind, q, offset, limit, before, chat_id)


@router.get('/chats/{chat_id}', response_model=ChatDetail)
async def get_chat(chat_id: str, user=Depends(get_verified_user), db=Depends(get_async_session)):
    detail = await repository.chat_detail(db, user.id, chat_id)
    if detail is None:
        raise HTTPException(404, 'Chat not found')
    return detail


@router.get('/notes/{note_id}', response_model=NoteDetail)
async def get_note(note_id: str, user=Depends(get_verified_user), db=Depends(get_async_session)):
    if not await notes_allowed(user, db):
        raise HTTPException(403, 'Notes are disabled')
    detail = await repository.note_detail(db, user.id, note_id)
    if detail is None:
        raise HTTPException(404, 'Note not found')
    return detail
