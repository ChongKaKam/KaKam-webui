# Administrator site token usage

Settings → Admin → Data → 本站 Token 使用情况 shows all-time recorded totals for
all users: input tokens, output tokens, their sum, and the number of users and
assistant responses with usage records. The homepage has only its existing
branding footer below the composer, without suggested prompts or usage panels.

GET /api/custom/usage/site is protected by native get_admin_user. It calls native
ChatMessages.get_token_usage_by_user without date/group/user filters and sums
all rows (no top-N or pagination). No user identities or message content are
returned. The old personal /daily endpoint is removed. No new schema or dependency.

This is retained chat usage, not a billing ledger. Missing provider usage,
ephemeral chats and auxiliary calls not saved as chat messages are not fully
represented. Deleting records may change totals. Empty records show zero; errors
show retry. There is no shared response cache; unmount/account changes abort
requests and discard stale results. Client timeout is eight seconds, server six.

Validation: aggregation across users, empty data, admin-only endpoint wiring,
no scope overrides, timeout handling, authenticated client requests and malformed
response rejection. Route tests stub native auth/database boundaries; they are
not a full deployment integration test. Browser tests use synthetic local data.

```sh
npx vitest run src/lib/kakam/usage
services/memory/.venv/bin/pytest -q --confcutdir=backend/open_webui/kakam/usage/tests --rootdir=backend/open_webui/kakam/usage/tests backend/open_webui/kakam/usage/tests
```
