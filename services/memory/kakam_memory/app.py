import asyncio
import hmac
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .admin import router as admin_router
from .config import Settings
from .domain import SECRET, TTLCache, fingerprint, is_unexpired, select_memories, validate_content
from .manager import router as manager_router
from .policy import POLICY_REGISTRY
from .provider_config import ConfigStore
from .providers import Providers
from .repository import Repository


class Recall(BaseModel):
    query: str = Field(max_length=8000)
    days: int = Field(default=30, ge=7, le=30, description='Recent-memory ranking window, not retention')
    policy: Literal['default'] = 'default'
    cache: bool = True


class MemorySource(BaseModel):
    external_chat_id: str = Field(min_length=1, max_length=256)
    external_message_id: str = Field(min_length=1, max_length=256)


class NewMemory(BaseModel):
    content: str
    kind: Literal['profile', 'preference', 'instruction', 'fact', 'episode'] = 'fact'
    source: MemorySource | None = None

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
    expires_at: datetime | None
    version: int = 1
    tags: list[str] = Field(default_factory=list)


class RecallResult(BaseModel):
    policy: Literal['default']
    memories: list[MemoryRead]
    cache_hit: bool
    revision: int


def create_app(settings=None, repository=None, providers=None):
    cfg = settings or Settings()
    repo = repository or Repository(cfg.database_url)
    store = ConfigStore(repo, cfg) if hasattr(repo, 'connect') else None
    embedding_cache = TTLCache(capacity=512, ttl=300)
    cache = TTLCache(ttl=60)

    @asynccontextmanager
    async def lifespan(app):
        cfg.validate()
        await asyncio.to_thread(repo.migrate)
        yield

    app = FastAPI(title='KaKam Memory', lifespan=lifespan)

    def owner(
        authorization: str = Header(default=''),
        x_memory_user: str = Header(default=''),
        x_memory_tenant: str = Header(default='default'),
    ):
        if not cfg.service_key or not hmac.compare_digest(authorization, 'Bearer ' + cfg.service_key):
            raise HTTPException(401, 'Invalid service credential')
        if not x_memory_user or len(x_memory_user) > 256:
            raise HTTPException(400, 'Missing user identity')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', x_memory_tenant):
            raise HTTPException(400, 'Invalid tenant identity')
        return x_memory_tenant + ':' + x_memory_user

    async def resolve(user=Depends(owner)):
        effective = await asyncio.to_thread(store.effective, user) if store else cfg
        return effective, providers or Providers(effective, embedding_cache)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo input values (in particular provider API keys) in validation errors.
        return JSONResponse(status_code=422, content={'detail': 'Invalid Memory request fields'})

    app.include_router(manager_router(repo, owner, resolve))
    if store:
        app.include_router(admin_router(cfg, store, owner))

    @app.get('/health')
    def health():
        repo.revision('__health__')
        return {'status': 'ok'}

    @app.get('/v1/policies')
    def policies(user=Depends(owner)):
        return [p.manifest for p in POLICY_REGISTRY.values()]

    @app.get('/v1/memories', response_model=list[MemoryRead])
    def memories(user=Depends(owner)):
        return repo.list(user)

    @app.post('/v1/memories')
    async def add(body: NewMemory, user=Depends(owner), runtime=Depends(resolve)):
        cfg, provider = runtime
        vector = await provider.embed(body.content, user)
        kwargs = {'source': (body.source.external_chat_id, body.source.external_message_id)} if body.source else {}
        return await asyncio.to_thread(repo.add, user, body.content, body.kind, vector, cfg.embedding_version, **kwargs)

    @app.delete('/v1/memories/{memory_id}')
    def delete(memory_id: UUID, user=Depends(owner)):
        if not repo.delete(user, memory_id):
            raise HTTPException(404, 'Memory not found')
        return {'deleted': True}

    @app.post('/v1/recall', response_model=RecallResult)
    async def recall(body: Recall, user=Depends(owner), runtime=Depends(resolve)):
        cfg, provider = runtime
        revision = await asyncio.to_thread(repo.revision, user)
        # Do not send recognisable credentials to a second (embedding) provider.
        if SECRET.search(body.query):
            return {'policy': body.policy, 'memories': [], 'cache_hit': False, 'revision': revision}
        key = (
            user,
            body.policy,
            body.days,
            revision,
            cfg.config_revision,
            cfg.embedding_version,
            fingerprint(body.query),
        )
        rows = cache.get(key) if body.cache else None
        hit = rows is not None
        if rows is None:
            vector = await provider.embed(body.query or 'user preferences', user)
            rows = select_memories(await asyncio.to_thread(repo.recall, user, body.days, vector, cfg.embedding_version))
            if body.cache:
                cache.put(key, rows)
        # Expiry is rechecked on cache hits as well.
        now = datetime.now(timezone.utc)
        rows = [row for row in rows if is_unexpired(row, now)]
        return {'policy': body.policy, 'memories': rows, 'cache_hit': hit, 'revision': revision}

    @app.post('/v1/events/turn-completed', status_code=202)
    def turn(body: Turn, user=Depends(owner)):
        # Compatibility endpoint: completed turns are not permission to persist knowledge.
        return {'queued': False, 'reason': 'Use an explicit memory action or confirm a proposal'}

    return app


app = create_app()
