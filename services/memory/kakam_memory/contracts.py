"""Versioned Manager contracts, independent of any chat application's schema."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .domain import validate_content

Kind = Literal['profile', 'preference', 'instruction', 'fact', 'episode']


class SessionSettings(BaseModel):
    automatic_recall: bool = True
    auto_compact: bool = True
    token_budget: int = Field(default=12000, ge=2000, le=100000)
    keep_messages: int = Field(default=8, ge=4, le=40)


class Scope(BaseModel):
    policy: str = Field(default='default', max_length=64)
    selections: dict[UUID, Literal['prefer', 'exclude']] = Field(default_factory=dict, max_length=200)
    settings: SessionSettings = Field(default_factory=SessionSettings)


class Prepare(BaseModel):
    session_id: str = Field(min_length=1, max_length=256)
    query: str = Field(max_length=8000)
    days: int = Field(default=30, ge=7, le=30, description='Recent-memory ranking window, not retention')
    cache: bool = True
    explicit_recall: bool = False


class Proposal(BaseModel):
    content: str
    kind: Kind = 'fact'
    evidence: str = Field(min_length=1, max_length=8000)
    source_message_id: str = Field(min_length=1, max_length=256)

    @field_validator('content')
    @classmethod
    def safe(cls, value):
        return validate_content(value)


class Decision(BaseModel):
    approve: bool


class Edit(BaseModel):
    content: str
    kind: Kind = 'fact'
    tags: list[str] = Field(default_factory=list, max_length=12)
    version: int = Field(ge=1)

    @field_validator('content')
    @classmethod
    def safe(cls, value):
        return validate_content(value)

    @field_validator('tags')
    @classmethod
    def bounded_tags(cls, values):
        if any(not v.strip() or len(v) > 40 for v in values):
            raise ValueError('Tags must contain 1–40 characters')
        return list(dict.fromkeys(v.strip() for v in values))


class Message(BaseModel):
    id: str = Field(default='', max_length=256)
    role: Literal['user', 'assistant', 'tool', 'system', 'developer']
    text: str = Field(default='', max_length=200000)
    tool_calls: list[str] = Field(default_factory=list, max_length=100)
    tool_call_id: str = Field(default='', max_length=256)


class Compact(BaseModel):
    session_id: str = Field(min_length=1, max_length=256)
    messages: list[Message] = Field(max_length=1000)


class Collection(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: UUID | None = None


class Membership(BaseModel):
    collection_id: UUID
    include: bool = True


class Handoff(BaseModel):
    source: str = Field(min_length=1, max_length=40000)
