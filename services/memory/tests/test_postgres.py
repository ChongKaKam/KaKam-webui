"""Opt-in integration suite. Point ONLY to a disposable pgvector test database."""

import os
from uuid import uuid4

import psycopg
import pytest
from kakam_memory.repository import Repository
from psycopg import sql
from psycopg.rows import dict_row


@pytest.fixture
def repo(request):
    url = os.getenv('KAKAM_TEST_DATABASE_URL')
    if not url:
        pytest.skip('KAKAM_TEST_DATABASE_URL not set; requires disposable PostgreSQL + pgvector')
    schema = 'test_memory_' + uuid4().hex
    with psycopg.connect(url) as db:
        db.execute('CREATE EXTENSION IF NOT EXISTS vector')
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    repository = Repository(url)
    repository.connect = lambda: psycopg.connect(url, row_factory=dict_row, options=f'-c search_path={schema},public')
    try:
        if getattr(request, 'param', True):
            repository.migrate()
            repository.migrate()
        yield repository
    finally:
        with psycopg.connect(url) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_sql_isolation_expiry_dimension_tombstone_and_revision(repo):
    assert repo.add('alice', '中文', 'preference', [1, 0, 0], 'v1')['created']
    assert not repo.add('alice', '中文', 'preference', [1, 0, 0], 'v1')['created']
    repo.add('bob', 'private', 'fact', [1, 0], 'v2')
    repo.add('alice', 'other model', 'fact', [1, 0], 'v2')
    rows = repo.recall('alice', 30, [1, 0, 0], 'v1')
    assert len(rows) == 1 and rows[0]['content'] == '中文'
    assert not repo.delete('bob', rows[0]['id'])
    revision = repo.revision('alice')
    assert repo.delete('alice', rows[0]['id'])
    assert repo.revision('alice') == revision + 1
    assert repo.recall('alice', 30, [1, 0, 0], 'v1') == []
    assert not repo.add('alice', '中文', 'fact', [1, 0, 0], 'v1')['created']
    repo.add('alice', 'expired', 'fact', [1, 0, 0], 'v1')
    with repo.connect() as db:
        db.execute("UPDATE memory_item SET expires_at=now()-interval '1 second' WHERE content='expired'")
    assert repo.recall('alice', 30, [1, 0, 0], 'v1') == []
    repo.cleanup()


def test_job_idempotency_lease_retry_and_evidence_erasure(repo):
    assert repo.enqueue('alice', 'chat', 'message', 'evidence')
    assert not repo.enqueue('alice', 'chat', 'message', 'different evidence')
    job = repo.claim()
    assert job['attempts'] == 1 and repo.claim() is None
    repo.finish(job, False)
    with repo.connect() as db:
        db.execute("UPDATE memory_job SET available_at=now()-interval '1 second'")
    retry = repo.claim()
    assert retry['id'] == job['id'] and retry['attempts'] == 2
    repo.finish(retry, True)
    with repo.connect() as db:
        assert db.execute('SELECT evidence FROM memory_job').fetchone()['evidence'] == ''
