import asyncio
import datetime as dt
import sys
import types
from contextlib import asynccontextmanager

import pytest
from open_webui.kakam.memory.activity import KINDS, summarize

NOW = dt.datetime(2026, 9, 19, 12, tzinfo=dt.timezone.utc)


def report(counts=(10, 20, 60, 10)):
    return {'kakamMemory': {'segments': [dict(kind=kind, characters=count) for kind, count in zip(KINDS, counts)]}}


def test_activity_sums_counts_and_zero_fills_utc_days():
    rows = [(report(), NOW.timestamp()), (report((0, 0, 100, 0)), NOW.timestamp())]
    result = summarize(rows, 7, NOW)
    assert result.requests == 2 and result.total_characters == 200
    assert result.characters['session'] == 160
    assert len(result.heatmap) == 7 and result.heatmap[0].date == '2026-09-13'
    assert result.heatmap[0].requests == 0 and result.heatmap[-1].requests == 2


def test_activity_skips_legacy_invalid_and_outside_window():
    bad = report((-1, 20, 30, 40))
    rows = [
        (None, NOW.timestamp()),
        ({}, NOW.timestamp()),
        (bad, NOW.timestamp()),
        (report(), (NOW - dt.timedelta(days=7)).timestamp()),
        (report(), (NOW + dt.timedelta(days=1)).timestamp()),
        (report(), None),
    ]
    assert summarize(rows, 7, NOW).requests == 0
    assert summarize([], 30, NOW, truncated=True).truncated


def test_query_is_user_scoped_and_excludes_orphaned_and_old_messages(monkeypatch):
    # SQLAlchemy/aiosqlite are existing WebUI dependencies, test-only here.
    sa = pytest.importorskip('sqlalchemy')
    pytest.importorskip('aiosqlite')
    from open_webui.kakam.memory.activity import get_activity
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import declarative_base

    base = declarative_base()

    class Chat(base):
        __tablename__ = 'chat'
        id = sa.Column(sa.String, primary_key=True)
        user_id = sa.Column(sa.String)

    class Message(base):
        __tablename__ = 'chat_message'
        id = sa.Column(sa.String, primary_key=True)
        chat_id = sa.Column(sa.String)
        user_id = sa.Column(sa.String)
        role = sa.Column(sa.String)
        meta = sa.Column(sa.JSON)
        created_at = sa.Column(sa.BigInteger)

    async def scenario():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        try:
            async with engine.begin() as connection:
                await connection.run_sync(base.metadata.create_all)
            session = async_sessionmaker(engine)

            @asynccontextmanager
            async def context():
                async with session() as db:
                    yield db

            monkeypatch.setitem(
                sys.modules, 'open_webui.internal.db', types.SimpleNamespace(get_async_db_context=context)
            )
            monkeypatch.setitem(sys.modules, 'open_webui.models.chats', types.SimpleNamespace(Chat=Chat))
            monkeypatch.setitem(
                sys.modules, 'open_webui.models.chat_messages', types.SimpleNamespace(ChatMessage=Message)
            )
            now = int(dt.datetime.now(dt.timezone.utc).timestamp())

            def message(id, chat, owner='alice', **kwargs):
                return Message(
                    id=id,
                    chat_id=chat,
                    user_id=owner,
                    role=kwargs.get('role', 'assistant'),
                    meta=kwargs.get('meta', report()),
                    created_at=kwargs.get('created_at', now),
                )

            async with session() as db:
                db.add_all(
                    [
                        Chat(id='a', user_id='alice'),
                        Chat(id='b', user_id='bob'),
                        message('valid', 'a'),
                        message('bob', 'b', 'bob'),
                        message('forged-user', 'b'),
                        message('forged-chat', 'a', 'bob'),
                        message('deleted-chat', 'missing'),
                        message('legacy', 'a', meta={}),
                        message('user-msg', 'a', role='user'),
                        message('old', 'a', created_at=now - 40 * 86400),
                    ]
                )
                await db.commit()
            result = await get_activity('alice', 30)
            assert result.requests == 1 and result.total_characters == 100
            assert (await get_activity('bob', 30)).requests == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())
