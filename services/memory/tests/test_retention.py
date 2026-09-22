"""Durable storage and recent-preferred recall, against disposable PostgreSQL."""

import datetime as dt
import json
import math
from pathlib import Path

import pytest
from kakam_memory.contracts import Edit
from kakam_memory.manager_repository import ManagerRepository
from test_api import headers
from test_manager import client_for

pytest_plugins = ['test_postgres']


def test_durable_crud_cleanup_and_relations(repo):
    mid = repo.add('default:alice', 'Remember this answer', 'episode', [1, 0, 0], 'v1')['id']
    with repo.connect() as db:
        db.execute("UPDATE memory_item SET created_at=now()-interval '365 days', updated_at=created_at")
    repo.cleanup()
    assert repo.list('default:alice')[0]['expires_at'] is None
    assert repo.get('default:alice', mid)['expires_at'] is None
    manager = ManagerRepository(repo)
    manager.configure('default:alice', 'chat', 'default', {mid: 'prefer'}, {})
    assert manager.session('default:alice', 'chat')['selections'] == {mid: 'prefer'}
    assert (
        manager.edit('default:alice', mid, Edit(content='Edited memory', version=1), [1, 0, 0], 'v1')['expires_at']
        is None
    )
    collection = manager.create_collection('default:alice', 'Archive', None)
    manager.membership('default:alice', mid, collection['id'], True)
    assert len(manager.relations('default:alice')) == 1
    assert repo.delete('default:alice', mid)
    repo.cleanup()
    assert not repo.add('default:alice', 'Edited memory', 'fact', [1, 0, 0], 'v1')['created']
    assert manager.session('default:alice', 'chat')['selections'] == {}


@pytest.mark.parametrize('repo', [False], indirect=True)
def test_upgrade_only_removes_legacy_default_deadlines(repo):
    migrations = Path(__file__).parents[1] / 'migrations'
    with repo.connect() as db:
        for path in sorted(migrations.glob('00[1-3]_*.sql')):
            db.execute(path.read_text())
            db.execute(
                'INSERT INTO memory_schema_version(version) VALUES (%s) ON CONFLICT DO NOTHING', (int(path.name[:3]),)
            )
    for content in ('legacy', 'deleted', 'superseded', 'explicit'):
        repo.add('default:alice', content, 'fact', [1, 0, 0], 'v1', source=('chat', content))
    with repo.connect() as db:
        db.execute(
            """UPDATE memory_item SET created_at=now()-interval '60 days',
                updated_at=now()-interval '60 days', expires_at=now()-interval '30 days'"""
        )
        db.execute("UPDATE memory_item SET status=content WHERE content IN ('deleted','superseded')")
        db.execute("UPDATE memory_item SET expires_at=created_at+interval '90 days' WHERE content='explicit'")
        before = db.execute(
            'SELECT id,content,status,embedding::text,dedupe_key,created_at,updated_at FROM memory_item ORDER BY id'
        ).fetchall()
    revision = repo.revision('default:alice')
    repo.migrate()
    repo.migrate()
    with repo.connect() as db:
        after = db.execute(
            'SELECT id,content,status,embedding::text,dedupe_key,created_at,updated_at FROM memory_item ORDER BY id'
        ).fetchall()
        assert before == after
        assert db.execute('SELECT count(*) AS n FROM memory_source').fetchone()['n'] == 4
        assert (
            db.execute("SELECT count(*) AS n FROM memory_event WHERE action='retention_default_removed'").fetchone()[
                'n'
            ]
            == 3
        )
    assert repo.revision('default:alice') == revision + 1
    rows = {r['content']: r for r in repo.list('default:alice')}
    assert set(rows) == {'legacy', 'explicit'}
    assert rows['legacy']['expires_at'] is None
    assert rows['explicit']['expires_at'] is not None
    repo.cleanup()
    assert {r['content'] for r in repo.list('default:alice')} == set(rows)
    assert repo.add('default:alice', 'new', 'episode', [1, 0, 0], 'v1')['created']
    assert next(r for r in repo.list('default:alice') if r['content'] == 'new')['expires_at'] is None


def test_recall_v3_evaluation_corpus(repo):
    cases = json.loads((Path(__file__).parent / 'fixtures/recall_v3.json').read_text())
    for case in cases:
        similarity = case['similarity']
        vector = [similarity, math.sqrt(1 - similarity**2), 0]
        result = repo.add(case.get('owner', 'default:alice'), case['content'], case['kind'], vector, 'v1')
        with repo.connect() as db:
            db.execute(
                """UPDATE memory_item SET updated_at=now()-make_interval(days => %s),
                pinned=%s, status=%s, expires_at=%s WHERE id=%s""",
                (
                    case['age'],
                    case.get('pinned', False),
                    case.get('status', 'active'),
                    dt.datetime.now(dt.UTC) - dt.timedelta(days=1) if case.get('expired') else None,
                    result['id'],
                ),
            )
    recalled = repo.recall('default:alice', 30, [1, 0, 0], 'v1')
    assert {r['content'] for r in recalled} == {c['content'] for c in cases if c['expected']}
    excluded = [r['id'] for r in recalled]
    assert repo.recall('default:alice', 30, [1, 0, 0], 'v1', excluded) == []


def test_recent_bonus_and_window_do_not_cut_off_strong_old_matches(repo):
    for content in ('recent', 'old'):
        repo.add('alice', content, 'episode', [0.8, 0.6, 0], 'v1')
    with repo.connect() as db:
        db.execute("UPDATE memory_item SET updated_at=now()-interval '90 days' WHERE content='old'")
    assert [r['content'] for r in repo.recall('alice', 30, [1, 0, 0], 'v1')] == ['recent', 'old']
    repo.add('alice', 'moderate', 'episode', [0.6, 0.8, 0], 'v1')
    with repo.connect() as db:
        db.execute("UPDATE memory_item SET updated_at=now()-interval '20 days' WHERE content='moderate'")
    assert 'moderate' in {r['content'] for r in repo.recall('alice', 30, [1, 0, 0], 'v1')}
    assert 'moderate' not in {r['content'] for r in repo.recall('alice', 7, [1, 0, 0], 'v1')}


def test_manager_old_recall_cache_expiry_and_exclusions(repo, monkeypatch):
    import kakam_memory.manager as module

    with client_for(repo) as client:
        mid = client.post('/v1/memories', headers=headers(), json={'content': 'old answer'}).json()['id']
        with repo.connect() as db:
            db.execute("UPDATE memory_item SET updated_at=now()-interval '365 days' WHERE id=%s", (mid,))
        body = {'session_id': 'chat', 'query': 'old answer'}
        for hit in (False, True):
            result = client.post('/v1/manager/prepare-turn', headers=headers(), json=body).json()
            assert result['cache_hit'] == hit
            assert result['memories'][0]['id'] == mid
            assert result['memories'][0]['expires_at'] is None
            assert result['policy_version'] == '3'
        assert not client.post('/v1/manager/prepare-turn', headers=headers('bob'), json=body).json()['memories']
        scope = client.get('/v1/manager/sessions/chat', headers=headers()).json()['session']
        scope['selections'] = {mid: 'exclude'}
        client.put('/v1/manager/sessions/chat', headers=headers(), json=scope)
        assert not client.post('/v1/manager/prepare-turn', headers=headers(), json=body).json()['memories']
        scope['selections'] = {}
        client.put('/v1/manager/sessions/chat', headers=headers(), json=scope)
        now = dt.datetime.now(dt.UTC)
        with repo.connect() as db:
            db.execute('UPDATE memory_item SET expires_at=%s WHERE id=%s', (now + dt.timedelta(minutes=1), mid))
        assert client.post('/v1/manager/prepare-turn', headers=headers(), json=body).json()['memories']

        class Later(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return now + dt.timedelta(minutes=2)

        monkeypatch.setattr(module, 'datetime', Later)
        result = client.post('/v1/manager/prepare-turn', headers=headers(), json=body).json()
        assert result['cache_hit'] and not result['memories']
