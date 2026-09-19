"""Dedicated database, short-lived transactions; never hold one during LLM calls."""

import uuid
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .domain import fingerprint


def vector_literal(vector):
    return '[' + ','.join(str(float(value)) for value in vector) + ']'


class Repository:
    def __init__(self, url):
        self.url = url

    def connect(self):
        return psycopg.connect(
            self.url, row_factory=dict_row, connect_timeout=5, options='-c statement_timeout=10000 -c lock_timeout=3000'
        )

    def migrate(self):
        sql = (Path(__file__).parent.parent / 'migrations/001_initial.sql').read_text()
        with self.connect() as db:
            db.execute('SELECT pg_advisory_xact_lock(7218411)')
            db.execute(sql)

    def revision(self, owner):
        with self.connect() as db:
            row = db.execute('SELECT revision FROM memory_revision WHERE owner=%s', (owner,)).fetchone()
            return row['revision'] if row else 0

    @staticmethod
    def bump(db, owner):
        db.execute(
            'INSERT INTO memory_revision(owner, revision) VALUES (%s,1) ON CONFLICT(owner) DO UPDATE SET revision=memory_revision.revision+1',
            (owner,),
        )

    def list(self, owner):
        with self.connect() as db:
            return db.execute(
                "SELECT id,kind,content,pinned,created_at,expires_at FROM memory_item WHERE owner=%s AND status='active' AND expires_at>now() ORDER BY updated_at DESC LIMIT 200",
                (owner,),
            ).fetchall()

    def recall(self, owner, days, vector, version):
        with self.connect() as db:
            # Scope BEFORE exact distance sorting. No approximate global index.
            return db.execute(
                """WITH scoped AS MATERIALIZED (
                SELECT * FROM memory_item WHERE owner=%s AND status='active'
                AND updated_at >= now() - make_interval(days => %s)
                AND expires_at>now() AND embedding_version=%s)
                SELECT id,kind,content,pinned,expires_at,updated_at,
                1-(embedding <=> %s::vector) AS similarity FROM scoped
                WHERE (pinned OR kind IN ('profile','preference','instruction') OR 1-(embedding <=> %s::vector) >= 0.3)
                ORDER BY pinned DESC, (kind IN ('profile','preference','instruction')) DESC,
                embedding <=> %s::vector, id LIMIT 30""",
                (owner, days, version, vector_literal(vector), vector_literal(vector), vector_literal(vector)),
            ).fetchall()

    def add(self, owner, content, kind, vector, version, source=None):
        with self.connect() as db:
            # A deletion tombstone prevents old jobs from recreating forgotten facts.
            row = db.execute(
                """INSERT INTO memory_item(id,owner,kind,content,dedupe_key,embedding,embedding_version)
                VALUES (%s,%s,%s,%s,%s,%s::vector,%s)
                ON CONFLICT(owner,dedupe_key) DO NOTHING RETURNING id""",
                (uuid.uuid4(), owner, kind, content, fingerprint(content.casefold()), vector_literal(vector), version),
            ).fetchone()
            if row:
                if source:
                    db.execute(
                        'INSERT INTO memory_source VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', (row['id'], *source)
                    )
                db.execute(
                    "INSERT INTO memory_event(owner,memory_id,action) VALUES (%s,%s,'created')", (owner, row['id'])
                )
                self.bump(db, owner)
            return {'created': bool(row)}

    def delete(self, owner, memory_id):
        with self.connect() as db:
            row = db.execute(
                """UPDATE memory_item SET status='deleted',content='',
                embedding=array_fill(0::real, ARRAY[vector_dims(embedding)])::vector,
                updated_at=now() WHERE owner=%s AND id=%s AND status='active' RETURNING id""",
                (owner, memory_id),
            ).fetchone()
            if row:
                db.execute('DELETE FROM memory_source WHERE memory_id=%s', (memory_id,))
                db.execute(
                    "INSERT INTO memory_event(owner,memory_id,action) VALUES (%s,%s,'deleted')", (owner, memory_id)
                )
                self.bump(db, owner)
            return bool(row)

    def enqueue(self, owner, chat_id, message_id, evidence):
        with self.connect() as db:
            row = db.execute(
                """INSERT INTO memory_job(id,owner,event_key,chat_id,message_id,evidence)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(owner,event_key) DO NOTHING RETURNING id""",
                (uuid.uuid4(), owner, fingerprint(f'{chat_id}:{message_id}:default:1'), chat_id, message_id, evidence),
            ).fetchone()
            return bool(row)

    def claim(self):
        with self.connect() as db:
            # Lease recovery after worker crashes. A lease is longer than provider timeout.
            return db.execute("""UPDATE memory_job SET status='processing',attempts=attempts+1,
                available_at=now()+interval '10 minutes' WHERE id=(SELECT id FROM memory_job
                WHERE status IN ('pending','processing') AND available_at<=now() AND attempts<5
                ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *""").fetchone()

    def finish(self, job, success):
        with self.connect() as db:
            state = 'done' if success else ('failed' if job['attempts'] >= 5 else 'pending')
            db.execute(
                """UPDATE memory_job SET status=%s,evidence=CASE WHEN %s THEN '' ELSE evidence END,
                available_at=now()+interval '30 seconds' WHERE id=%s""",
                (state, state in {'done', 'failed'}, job['id']),
            )

    def cleanup(self):
        with self.connect() as db:
            db.execute(
                "UPDATE memory_job SET status='failed',evidence='' WHERE status='processing' AND attempts>=5 AND available_at<=now()"
            )
            db.execute('DELETE FROM memory_item WHERE expires_at < now()')
            db.execute("DELETE FROM memory_job WHERE created_at<now()-interval '30 days'")
            db.execute("DELETE FROM memory_event WHERE created_at<now()-interval '30 days'")
