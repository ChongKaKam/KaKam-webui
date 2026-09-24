import asyncio
import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import JSON, BigInteger, Boolean, Column, String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from library import repository
from library.tools import MAX_BYTES, publish_artifact, validate_artifact

Base = declarative_base()


class Chat(Base):
    __tablename__ = 'chat'
    id = Column(String, primary_key=True)
    user_id = Column(String)
    title = Column(String)
    chat = Column(JSON)
    updated_at = Column(BigInteger)
    archived = Column(Boolean)
    current_message_id = Column(String)


class ChatFile(Base):
    __tablename__ = 'chat_file'
    id = Column(String, primary_key=True)
    chat_id = Column(String)
    file_id = Column(String)
    message_id = Column(String)


class File(Base):
    __tablename__ = 'file'
    id = Column(String, primary_key=True)
    user_id = Column(String)
    filename = Column(String)
    updated_at = Column(BigInteger)
    meta = Column(JSON)


class Note(Base):
    __tablename__ = 'note'
    id = Column(String, primary_key=True)
    user_id = Column(String)
    title = Column(String)
    data = Column(JSON)
    updated_at = Column(BigInteger)


class ChatMessage(Base):
    __tablename__ = 'chat_message'
    id = Column(String, primary_key=True)
    chat_id = Column(String)
    role = Column(String)
    content = Column(JSON)
    output = Column(JSON)
    files = Column(JSON)
    created_at = Column(BigInteger)
    parent_id = Column(String)


def install(monkeypatch, name, **attrs):
    module = ModuleType(name)
    module.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, module)


def test_repository_isolation_legacy_provenance_and_pagination(monkeypatch):
    monkeypatch.setattr(repository, 'models', lambda: (Chat, ChatFile, File, Note))
    install(monkeypatch, 'open_webui.models.chat_messages', ChatMessage=ChatMessage)

    async def run():
        engine = create_async_engine('sqlite+aiosqlite://')
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            db.add_all(
                [
                    Chat(
                        id='a',
                        user_id='alice',
                        title='100% plan',
                        updated_at=100,
                        chat={
                            'history': {
                                'currentId': 'old',
                                'messages': {'old': {'id': 'old', 'role': 'user', 'content': 'legacy'}},
                            }
                        },
                    ),
                    Chat(id='b', user_id='bob', title='private', updated_at=200, chat={}),
                    Chat(id='a2', user_id='alice', title='1000 plan', updated_at=200, chat={}),
                    ChatMessage(
                        id='a2-m1',
                        chat_id='a2',
                        role='assistant',
                        content='modern',
                        created_at=199,
                        files=[{'id': 'f1'}],
                    ),
                    File(
                        id='f1',
                        user_id='alice',
                        filename='one.html',
                        updated_at=100,
                        meta={'size': 42, 'data': {'kakam_artifact': True, 'chat_id': 'a2', 'message_id': 'm1'}},
                    ),
                    File(id='f2', user_id='alice', filename='two.md', updated_at=200, meta={'size': -1}),
                    File(id='f3', user_id='bob', filename='secret.pdf', updated_at=100, meta={'size': 999}),
                    ChatFile(id='ref1', chat_id='a', file_id='f1', message_id='old'),
                    ChatFile(id='ref2', chat_id='b', file_id='f1', message_id='private'),
                    Note(
                        id='n1',
                        user_id='alice',
                        title='HTML note',
                        updated_at=100 * 10**9,
                        data={'content': {'md': '<html>Hi</html>'}},
                    ),
                    Note(id='n2', user_id='bob', title='private note', updated_at=200 * 10**9, data={}),
                ]
            )
            await db.commit()
            stats = await repository.summary(db, 'alice', True)
            assert (stats.chats, stats.files, stats.notes, stats.file_bytes, stats.unknown_size_files) == (
                2,
                2,
                1,
                42,
                1,
            )
            assert (await repository.summary(db, 'alice', False)).notes == 0
            page = await repository.entries(db, 'alice', 'file', limit=1)
            assert page.total == 2 and page.items[0].id == 'f2'
            page = await repository.entries(db, 'alice', 'file', offset=1, limit=1)
            file = page.items[0]
            assert file.origin == 'generated'
            assert {s.chat_id for s in file.sources} == {'a', 'a2'}
            assert 'private' not in file.model_dump_json()
            assert (await repository.entries(db, 'alice', 'file', chat_id='b')).total == 0
            assert (await repository.entries(db, 'alice', 'file', chat_id='a2')).total == 1
            assert [r.id for r in (await repository.entries(db, 'alice', 'chat', q='100%')).items] == ['a']
            assert (await repository.entries(db, 'alice', 'file', before=150)).total == 1
            assert (await repository.entries(db, 'alice', 'note', before=150)).total == 1
            legacy = await repository.chat_detail(db, 'alice', 'a')
            assert legacy.messages[0].content == 'legacy' and legacy.current_message_id == 'old'
            modern = await repository.chat_detail(db, 'alice', 'a2')
            assert modern.messages[0].id == 'm1' and modern.messages[0].files == [{'id': 'f1'}]
            assert await repository.chat_detail(db, 'alice', 'b') is None
            assert await repository.note_detail(db, 'alice', 'n2') is None
            assert (await repository.note_detail(db, 'alice', 'n1')).content == '<html>Hi</html>'
        await engine.dispose()

    asyncio.run(run())


@pytest.fixture
def endpoint(monkeypatch):
    async def verified(authorization: str = Header(default='')):
        if not authorization:
            raise HTTPException(401)
        role = authorization.removeprefix('Bearer ')
        if role not in ('user', 'admin'):
            raise HTTPException(403)
        return SimpleNamespace(id='current-user', role=role)

    async def database():
        yield 'db'

    install(monkeypatch, 'open_webui.utils.auth', get_verified_user=verified)
    install(monkeypatch, 'open_webui.internal.db', get_async_session=database)
    sys.modules.pop('library.router', None)
    module = importlib.import_module('library.router')
    monkeypatch.setattr(module, 'notes_allowed', AsyncMock(return_value=True))
    listing = AsyncMock(return_value={'items': [], 'total': 0})
    monkeypatch.setattr(repository, 'entries', listing)
    monkeypatch.setattr(repository, 'chat_detail', AsyncMock(return_value=None))
    monkeypatch.setattr(repository, 'note_detail', AsyncMock(return_value=None))
    app = FastAPI()
    app.include_router(module.router, prefix='/api/custom/library')
    with TestClient(app) as client:
        yield client, module, listing
    sys.modules.pop('library.router', None)


def test_routes_require_verified_owner_and_bound_queries(endpoint):
    client, _, listing = endpoint
    base = '/api/custom/library/entries?kind=file'
    assert client.get(base).status_code == 401
    assert client.get(base, headers={'Authorization': 'Bearer pending'}).status_code == 403
    for role in ('admin', 'user'):
        response = client.get(base + '&user_id=someone-else', headers={'Authorization': f'Bearer {role}'})
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'private, no-store'
        assert listing.call_args.args[1] == 'current-user'
    for invalid in ('&limit=101', '&offset=-1', '&q=' + 'x' * 201, '&before=0'):
        assert client.get(base + invalid, headers={'Authorization': 'Bearer user'}).status_code == 422
    assert client.get('/api/custom/library/chats/foreign', headers={'Authorization': 'Bearer admin'}).status_code == 404
    assert client.get('/api/custom/library/notes/foreign', headers={'Authorization': 'Bearer user'}).status_code == 404


def test_notes_feature_permissions_are_preserved(endpoint):
    client, module, _ = endpoint
    module.notes_allowed.return_value = False
    for path in ('/entries?kind=note', '/notes/id'):
        assert client.get('/api/custom/library' + path, headers={'Authorization': 'Bearer user'}).status_code == 403


@pytest.mark.parametrize(
    'name,content',
    [
        ('../bad.html', 'a'),
        ('a\\b.md', 'a'),
        ('a\n.html', 'a'),
        ('a.exe', 'a'),
        ('a.md', ''),
        ('a.md', 'a' * (MAX_BYTES + 1)),
    ],
    ids=['path', 'backslash', 'control', 'extension', 'empty', 'oversize'],
)
def test_publisher_rejects_unsafe_or_unbounded_files(name, content):
    with pytest.raises(ValueError):
        validate_artifact(name, content)


def test_website_delivery_requires_html_source_not_markdown():
    for content in ('# Your website\nHere is the plan', '```html\n<html>Hi</html>\n```'):
        with pytest.raises(ValueError):
            validate_artifact('site.html', content)
    data, mime = validate_artifact('site.html', '<!doctype html><html><body>Hi</body></html>')
    assert mime == 'text/html' and data.startswith(b'<!doctype html>')


def test_publisher_persists_before_emitting_and_checks_ownership(monkeypatch):
    chats = SimpleNamespace(
        get_chat_by_id_and_user_id=AsyncMock(return_value=object()),
        insert_chat_files=AsyncMock(return_value=[object()]),
    )
    upload = AsyncMock(return_value=SimpleNamespace(id='file-id'))
    permitted = AsyncMock(return_value=True)
    install(monkeypatch, 'open_webui.models.chats', Chats=chats)
    install(monkeypatch, 'open_webui.models.config', Config=SimpleNamespace(get=AsyncMock(return_value={})))
    install(
        monkeypatch, 'open_webui.models.users', UserModel=SimpleNamespace(model_validate=lambda u: SimpleNamespace(**u))
    )
    install(monkeypatch, 'open_webui.routers.files', upload_file_handler=upload)
    install(monkeypatch, 'open_webui.utils.access_control', has_permission=permitted)
    install(
        monkeypatch,
        'open_webui.utils.chat_id',
        is_saved_chat_id=lambda cid: bool(cid) and not cid.startswith(('temporary:', 'local:', 'channel:')),
    )
    import json

    async def run():
        emitter = AsyncMock()
        params = {
            'filename': '网页.html',
            'content': '<html>你好</html>',
            '__request__': object(),
            '__user__': {'id': 'alice', 'role': 'user'},
            '__metadata__': {'chat_id': 'chat', 'message_id': 'm'},
            '__event_emitter__': emitter,
        }
        result = json.loads(await publish_artifact(**params))
        assert result['status'] == 'success' and result['download_url'].endswith('?attachment=true')
        assert result['expires_at'] is None and result['size'] == len(params['content'].encode())
        assert upload.call_args.kwargs['process'] is False
        assert upload.call_args.kwargs['metadata']['chat_id'] == 'chat'
        assert emitter.call_args.args[0]['data']['files'][0]['name'] == '网页.html'
        # Event failures must not misreport a persisted file as missing.
        emitter.side_effect = RuntimeError('socket offline')
        result = json.loads(await publish_artifact(**params))
        assert result['status'] == 'success' and result['attachment_emitted'] is False
        upload.reset_mock()
        chats.get_chat_by_id_and_user_id.return_value = None
        assert 'error' in json.loads(await publish_artifact(**params))
        assert not upload.called
        chats.get_chat_by_id_and_user_id.return_value = object()
        permitted.return_value = False
        assert 'error' in json.loads(await publish_artifact(**params))
        assert not upload.called
        params['__metadata__']['chat_id'] = 'temporary:chat'
        assert 'error' in json.loads(await publish_artifact(**params))

    asyncio.run(run())
