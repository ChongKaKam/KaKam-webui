"""Manager state persists beside memories, never in Open WebUI-owned tables."""

import uuid

from psycopg.types.json import Jsonb


class ManagerRepository:
    def __init__(self, repository):
        self.repo = repository

    def session(self, owner, session_id):
        with self.repo.connect() as db:
            db.execute(
                'INSERT INTO memory_session(owner,session_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                (owner, session_id),
            )
            row = db.execute(
                'SELECT policy,selections,settings,checkpoint,revision FROM memory_session WHERE owner=%s AND session_id=%s',
                (owner, session_id),
            ).fetchone()
            if row['selections']:
                active = db.execute(
                    """SELECT id FROM memory_item
                    WHERE owner=%s AND id=ANY(%s::uuid[]) AND status='active'
                    AND (expires_at IS NULL OR expires_at>now())""",
                    (owner, list(row['selections'])),
                ).fetchall()
                ids = {str(item['id']) for item in active}
                row['selections'] = {key: value for key, value in row['selections'].items() if key in ids}
            return row

    def configure(self, owner, session_id, policy, selections, settings):
        self.session(owner, session_id)
        with self.repo.connect() as db:
            for memory_id in selections:
                if not db.execute(
                    """SELECT id FROM memory_item
                    WHERE owner=%s AND id=%s AND status='active'
                    AND (expires_at IS NULL OR expires_at>now())""",
                    (owner, memory_id),
                ).fetchone():
                    raise LookupError('Memory not found')
            db.execute(
                'UPDATE memory_session SET policy=%s,selections=%s,settings=%s,revision=revision+1,updated_at=now() WHERE owner=%s AND session_id=%s',
                (policy, Jsonb(selections), Jsonb(settings), owner, session_id),
            )
        return self.session(owner, session_id)

    def checkpoint(self, owner, session_id, checkpoint):
        self.session(owner, session_id)
        with self.repo.connect() as db:
            db.execute(
                'UPDATE memory_session SET checkpoint=%s,updated_at=now() WHERE owner=%s AND session_id=%s',
                (Jsonb(checkpoint), owner, session_id),
            )

    def operation(self, owner, session_id, operation, snapshot, state, facts, policy_version='default:3'):
        operation_id = uuid.uuid4()
        with self.repo.connect() as db:
            db.execute(
                'INSERT INTO memory_operation(id,owner,session_id,operation,snapshot_id,policy_version,state,facts) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                (operation_id, owner, session_id, operation, snapshot, policy_version, state, Jsonb(facts)),
            )
        return str(operation_id)

    def operations(self, owner, session_id):
        with self.repo.connect() as db:
            return db.execute(
                'SELECT id,operation,snapshot_id,policy_version,state,facts,created_at FROM memory_operation WHERE owner=%s AND session_id=%s ORDER BY created_at DESC LIMIT 20',
                (owner, session_id),
            ).fetchall()

    def propose(self, owner, session_id, content, kind, evidence, source_id):
        with self.repo.connect() as db:
            row = db.execute(
                'INSERT INTO memory_proposal(id,owner,session_id,content,kind,evidence,source_message_id) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(owner,session_id,source_message_id,content) DO UPDATE SET content=EXCLUDED.content RETURNING id,state',
                (uuid.uuid4(), owner, session_id, content, kind, evidence, source_id),
            ).fetchone()
            return row

    def proposals(self, owner, session_id):
        with self.repo.connect() as db:
            return db.execute(
                "SELECT id,content,kind,evidence,source_message_id,state FROM memory_proposal WHERE owner=%s AND session_id=%s AND state='pending' AND expires_at>now() ORDER BY created_at LIMIT 30",
                (owner, session_id),
            ).fetchall()

    def decide(self, owner, proposal_id, approve, vector=None, embedding_version=None):
        # The source proposal row lock serializes repeated confirmation clicks.
        with self.repo.connect() as db:
            row = db.execute(
                'SELECT * FROM memory_proposal WHERE owner=%s AND id=%s AND expires_at>now() FOR UPDATE',
                (owner, proposal_id),
            ).fetchone()
            if not row:
                raise LookupError('Proposal not found')
            if row['state'] != 'pending':
                return row['result'] or {'state': row['state']}
            if not approve:
                result = {'state': 'rejected'}
            else:
                from .domain import fingerprint
                from .repository import vector_literal

                memory_id = uuid.uuid4()
                created = db.execute(
                    'INSERT INTO memory_item(id,owner,kind,content,dedupe_key,embedding,embedding_version) VALUES (%s,%s,%s,%s,%s,%s::vector,%s) ON CONFLICT(owner,dedupe_key) DO NOTHING RETURNING id',
                    (
                        memory_id,
                        owner,
                        row['kind'],
                        row['content'],
                        fingerprint(row['content'].casefold()),
                        vector_literal(vector),
                        embedding_version,
                    ),
                ).fetchone()
                if created:
                    db.execute(
                        'INSERT INTO memory_source(memory_id,chat_id,message_id) VALUES (%s,%s,%s)',
                        (memory_id, row['session_id'], row['source_message_id']),
                    )
                    db.execute(
                        "INSERT INTO memory_event(owner,memory_id,action) VALUES (%s,%s,'created')", (owner, memory_id)
                    )
                    self.repo.bump(db, owner)
                result = {
                    'state': 'applied' if created else 'duplicate_or_forgotten',
                    'id': str(memory_id) if created else None,
                }
            db.execute(
                'UPDATE memory_proposal SET state=%s,result=%s,evidence=%s WHERE id=%s',
                (result['state'], Jsonb(result), '', proposal_id),
            )
            return result

    def proposal(self, owner, proposal_id):
        with self.repo.connect() as db:
            return db.execute(
                'SELECT content,state,result FROM memory_proposal WHERE owner=%s AND id=%s AND expires_at>now()',
                (owner, proposal_id),
            ).fetchone()

    def edit(self, owner, memory_id, body, vector, embedding_version):
        from .domain import fingerprint
        from .repository import vector_literal

        with self.repo.connect() as db:
            row = db.execute(
                """SELECT * FROM memory_item
                WHERE owner=%s AND id=%s AND status='active'
                AND (expires_at IS NULL OR expires_at>now()) FOR UPDATE""",
                (owner, memory_id),
            ).fetchone()
            if not row:
                raise LookupError('Memory not found')
            if row['version'] != body.version:
                raise ValueError('Version conflict; refresh before editing')
            duplicate = db.execute(
                'SELECT id FROM memory_item WHERE owner=%s AND dedupe_key=%s AND id<>%s',
                (owner, fingerprint(body.content.casefold()), memory_id),
            ).fetchone()
            if duplicate:
                raise ValueError('Duplicate or forgotten memory')
            db.execute(
                'INSERT INTO memory_version(memory_id,version,content,kind,tags) VALUES (%s,%s,%s,%s,%s)',
                (memory_id, row['version'], row['content'], row['kind'], Jsonb(row['tags'])),
            )
            db.execute(
                'UPDATE memory_item SET content=%s,kind=%s,tags=%s,embedding=%s::vector,embedding_version=%s,dedupe_key=%s,version=version+1,updated_at=now() WHERE owner=%s AND id=%s',
                (
                    body.content,
                    body.kind,
                    Jsonb(body.tags),
                    vector_literal(vector),
                    embedding_version,
                    fingerprint(body.content.casefold()),
                    owner,
                    memory_id,
                ),
            )
            db.execute("INSERT INTO memory_event(owner,memory_id,action) VALUES (%s,%s,'edited')", (owner, memory_id))
            self.repo.bump(db, owner)
        return self.repo.get(owner, memory_id)

    def collections(self, owner):
        with self.repo.connect() as db:
            return db.execute(
                'SELECT id,name,parent_id FROM memory_collection WHERE owner=%s ORDER BY name', (owner,)
            ).fetchall()

    def create_collection(self, owner, name, parent_id):
        with self.repo.connect() as db:
            if (
                parent_id
                and not db.execute(
                    'SELECT id FROM memory_collection WHERE id=%s AND owner=%s', (parent_id, owner)
                ).fetchone()
            ):
                raise LookupError('Collection not found')
            return db.execute(
                'INSERT INTO memory_collection(id,owner,name,parent_id) VALUES (%s,%s,%s,%s) ON CONFLICT(owner,name) DO UPDATE SET name=EXCLUDED.name RETURNING id,name,parent_id',
                (uuid.uuid4(), owner, name, parent_id),
            ).fetchone()

    def membership(self, owner, memory_id, collection_id, include):
        with self.repo.connect() as db:
            if (
                not db.execute(
                    "SELECT id FROM memory_item WHERE owner=%s AND id=%s AND status='active'", (owner, memory_id)
                ).fetchone()
                or not db.execute(
                    'SELECT id FROM memory_collection WHERE owner=%s AND id=%s', (owner, collection_id)
                ).fetchone()
            ):
                raise LookupError('Memory or collection not found')
            if include:
                db.execute(
                    'INSERT INTO memory_membership VALUES (%s,%s) ON CONFLICT DO NOTHING', (memory_id, collection_id)
                )
            else:
                db.execute(
                    'DELETE FROM memory_membership WHERE memory_id=%s AND collection_id=%s', (memory_id, collection_id)
                )

    def relations(self, owner):
        with self.repo.connect() as db:
            return db.execute(
                """SELECT r.memory_id,r.collection_id FROM memory_membership r
                JOIN memory_item m ON m.id=r.memory_id JOIN memory_collection c ON c.id=r.collection_id
                WHERE m.owner=%s AND c.owner=%s AND m.status='active'
                AND (m.expires_at IS NULL OR m.expires_at>now()) LIMIT 500""",
                (owner, owner),
            ).fetchall()
