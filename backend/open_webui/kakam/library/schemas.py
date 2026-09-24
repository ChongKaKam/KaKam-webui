from typing import Any, Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    chat_id: str
    title: str
    message_id: str | None = None


class Group(BaseModel):
    id: str
    name: str


class Entry(BaseModel):
    id: str
    kind: Literal['chat', 'file', 'note']
    title: str
    updated_at: int
    size: int | None = None
    content_type: str | None = None
    origin: Literal['generated', 'unknown'] = 'unknown'
    sources: list[Source] = Field(default_factory=list)
    archived: bool = False
    group: Group | None = None


class EntryPage(BaseModel):
    items: list[Entry]
    total: int


class Summary(BaseModel):
    chats: int
    files: int
    notes: int
    file_bytes: int
    unknown_size_files: int
    notes_enabled: bool


class Message(BaseModel):
    id: str
    role: str
    content: Any = ''
    output: list = Field(default_factory=list)
    files: list = Field(default_factory=list)
    timestamp: int = 0
    parent_id: str | None = None


class ChatDetail(BaseModel):
    id: str
    title: str
    messages: list[Message]
    current_message_id: str | None = None
    group: Group | None = None


class NoteDetail(BaseModel):
    id: str
    title: str
    content: str
