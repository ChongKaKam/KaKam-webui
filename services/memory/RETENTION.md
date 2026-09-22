# Durable Memory and recall policy v3

Memory storage and retrieval have separate lifetimes. New `memory_item` records
have `expires_at = NULL` (indefinite retention), including manual writes,
Remember it, and confirmed proposals. The API returns a nullable `expires_at`;
clients must display “长期保留” for null. Deletion, superseding and user/tenant
isolation still apply. An explicitly set non-null deadline remains authoritative.
Proposal, session, cache and operational-log TTLs are unchanged.

## Recent-preferred recall

`days` keeps its existing 7–30 range and default 30, but now describes the recent
ranking window, not retention or a hard age cutoff. Both `/v1/recall` and Manager
`prepare-turn` use the same repository selection:

- Hard filters: owner, active lifecycle, explicit expiry, compatible embedding
  version, and session exclusions.
- Pinned records and profile/preference/instruction records remain candidates
  regardless of age. Explicit session “prefer” selections also remain eligible.
- Other recent records require cosine similarity >= 0.3; older records require
  >= 0.7. These are initial heuristic thresholds, not measured quality guarantees.
- Rank pinned and stable kinds first, then similarity with a 0.1 bonus for records
  updated within `days`; break ties by ID. A strongly relevant old answer can rank
  above a weak recent answer. Read access does not refresh `updated_at`.
- Keep the existing 30-candidate SQL cap, deduplication and final context budget.
  Saving a memory does not guarantee injection on every turn.

Cache hits still recheck explicit expiry, but do not discard memories by age.
Record/session revisions invalidate cached selections after edits, exclusions or
deletions. Policy version is now `3` and participates in Manager cache keys.

## Upgrade and rollback

`004_durable_memory.sql` runs in the existing advisory-locked migration transaction.
It removes the NOT NULL constraint and default deadline. Existing rows whose
`expires_at` exactly equals `created_at + interval '30 days'` lose that legacy
implicit deadline, including expired rows that have not yet been purged. Other
explicit deadlines remain intact. Content, vectors, source IDs, timestamps,
versions and lifecycle states are preserved; deleted/superseded rows are never
made active. A metadata-only event is added for each converted row and each
changed owner's cache revision advances once. Re-running migration is a no-op.
Already purged records cannot be recovered by this migration.

Before production rollout, back up the independent Memory database and deploy
service and frontend together. Stop the old Memory worker before the migration
so it cannot purge legacy expired rows concurrently. The old service cannot
handle nullable expiry: do not roll back to its image against the migrated DB.
Prefer a forward fix or a compatibility release that retains nullable-expiry
support. A full database restore requires a coordinated outage and reconciliation
of writes since the backup; never invent new deadlines for durable records just
to satisfy the old schema. This change does not run a production migration or
alter deployments by itself.

## Verification

`tests/test_retention.py` runs only with `KAKAM_TEST_DATABASE_URL` pointing at a
disposable PostgreSQL/pgvector database. It covers durable CRUD, cleanup, relation
and session access, deletion precedence, migration preservation/idempotency,
recent weighting, old highly relevant recall, explicit deadlines, cache hits and
exclusions. `tests/fixtures/recall_v3.json` is a versioned deterministic selection
corpus (controlled embeddings), including irrelevant records, stable preferences,
old pinned records, conflicts, deleted records and other owners. Existing domain
and adapter tests cover explicit remember, secret rejection and prompt-injection
boundaries; this is not a live embedding-provider relevance benchmark.
