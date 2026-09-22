"""Verify opaque chat provenance for an explicitly confirmed manual Memory write."""

from fastapi import HTTPException
from pydantic import BaseModel, Field


class MemorySource(BaseModel):
    external_chat_id: str = Field(min_length=1, max_length=256)
    external_message_id: str = Field(min_length=1, max_length=256)


async def verify_source(source: MemorySource, user):
    from open_webui.models.chats import Chats
    from open_webui.utils.chat_id import is_saved_chat_id

    chat_id, message_id = source.external_chat_id, source.external_message_id
    if not is_saved_chat_id(chat_id) or not await Chats.is_chat_owner(chat_id, user.id):
        raise HTTPException(404, 'Chat not found')
    answer = await Chats.get_message_by_id_and_message_id(chat_id, message_id)
    if not answer or answer.get('role') != 'assistant' or not answer.get('done', True) or answer.get('error'):
        raise HTTPException(422, '请等待回答完成，并选择一条已保存的正常回复。')
    parent = answer.get('parentId')
    question = await Chats.get_message_by_id_and_message_id(chat_id, parent) if parent else None
    if not question or question.get('role') != 'user':
        raise HTTPException(422, '无法确认这条回答对应的用户问题，请刷新聊天后重试。')
