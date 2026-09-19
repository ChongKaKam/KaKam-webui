import asyncio
import hmac
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .domain import POLICIES, SECRET, TTLCache, fingerprint, select_memories, validate_content
from .providers import Providers
from .repository import Repository


class Recall(BaseModel):
    query: str = Field(max_length=8000)
    days: int = Field(default=30, ge=7, le=30)
    policy: Literal['default'] = 'default'
    cache: bool = True


class NewMemory(BaseModel):
    content: str
    kind: Literal['profile', 'preference', 'instruction', 'fact', 'episode'] = 'fact'

    @field_validator('content')
    @classmethod
    def safe_content(cls, value):
        return validate_content(value)


class Turn(BaseModel):
    chat_id: str = Field(min_length=1, max_length=256)
    message_id: str = Field(min_length=1, max_length=256)
    evidence: str = Field(min_length=1, max_length=8000)


class MemoryRead(BaseModel):
    id: UUID
    kind: Literal['profile', 'preference', 'instruction', 'fact', 'episode']
    content: str
    pinned: bool = False
    expires_at: datetime


class RecallResult(BaseModel):
    policy: Literal['default']
    memories: list[MemoryRead]
    cache_hit: bool
    revision: int


def create_app(settings=None, repository=None, providers=None):
    cfg = settings or Settings()
    repo = repository or Repository(cfg.database_url)
    provider = providers or Providers(cfg)
    cache = TTLCache(ttl=60)

    @asynccontextmanager
    async def lifespan(app):
        cfg.validate()
        await asyncio.to_thread(repo.migrate)
        yield

    app = FastAPI(title='KaKam Memory', lifespan=lifespan)

    def owner(authorization: str = Header(default=''), x_memory_user: str = Header(default='')):
        if not cfg.service_key or not hmac.compare_digest(authorization, 'Bearer ' + cfg.service_key):
            raise HTTPException(401, 'Invalid service credential')
        if not x_memory_user or len(x_memory_user) > 256:
            raise HTTPException(400, 'Missing user identity')
        return x_memory_user

    @app.get('/health')
    def health():
        repo.revision('__health__')
        return {'status': 'ok'}

    @app.get('/v1/policies')
    def policies(user=Depends(owner)):
        return POLICIES

    @app.get('/v1/memories', response_model=list[MemoryRead])
    def memories(user=Depends(owner)):
        return repo.list(user)

    @app.post('/v1/memories')
    async def add(body: NewMemory, user=Depends(owner)):
        vector = await provider.embed(body.content, user)
        return await asyncio.to_thread(repo.add, user, body.content, body.kind, vector, cfg.embedding_version)

    @app.delete('/v1/memories/{memory_id}')
    def delete(memory_id: UUID, user=Depends(owner)):
        if not repo.delete(user, memory_id):
            raise HTTPException(404, 'Memory not found')
        return {'deleted': True}

    @app.post('/v1/recall', response_model=RecallResult)
    async def recall(body: Recall, user=Depends(owner)):
        revision = await asyncio.to_thread(repo.revision, user)
        # Do not send recognisable credentials to a second (embedding) provider.
        if SECRET.search(body.query):
            return {'policy': body.policy, 'memories': [], 'cache_hit': False, 'revision': revision}
        key = (user, body.policy, body.days, revision, cfg.embedding_version, fingerprint(body.query))
        rows = cache.get(key) if body.cache else None
        hit = rows is not None
        if rows is None:
            vector = await provider.embed(body.query or 'user preferences', user)
            rows = select_memories(await asyncio.to_thread(repo.recall, user, body.days, vector, cfg.embedding_version))
            if body.cache:
                cache.put(key, rows)
        # Expiry is rechecked on cache hits as well.
        now = datetime.now(timezone.utc)
        rows = [row for row in rows if row['expires_at'] > now and row['updated_at'] >= now - timedelta(days=body.days)]
        return {'policy': body.policy, 'memories': rows, 'cache_hit': hit, 'revision': revision}

    @app.post('/v1/events/turn-completed', status_code=202)
    def turn(body: Turn, user=Depends(owner)):
        if body.chat_id.startswith(('temporary:', 'local:', 'channel:')) or SECRET.search(body.evidence):
            return {'queued': False}
        return {'queued': repo.enqueue(user, body.chat_id, body.message_id, body.evidence)}

    return app


app = create_app()
