# Remember it

The response toolbar's bookmark icon opens an editable preview of the selected
question and visible answer. Clicking the icon or cancelling never writes Memory;
only **保存到长期记忆** calls the existing authenticated manual-create API.
The icon inherits neighboring toolbar sizing, color, hover reveal and tooltip.
Ratings and Read Aloud controls are hidden by cloud presentation policy only.

Only a completed, non-error response with a user-message parent is eligible.
Read-only/shared views, pending/unauthenticated users, and users without Memory
permission do not show the action. Temporary/unsaved chats show a disabled action.
The preview does not concatenate sibling model replies or other history. It does
not include attachments, private System content or hidden reasoning. Responses API
visible text is supplied by the same renderer as the existing Copy action.

No automatic LLM summarization or extraction is performed. Long previews stay
intact and require the user to reduce the text to the existing 2,000-character
limit; no silent truncation. Confirmed content is stored as `episode` (a retained
conversation), not an independently verified fact or a durable instruction. The
record is retained indefinitely by default; recent-memory preference affects recall,
not storage lifetime. Retrieval budgets, permissions and sensitive-content checks
still apply. Saving does not force injection into every future chat or enable recall.

`POST /api/custom/memory` now optionally accepts:

```json
{
  "content": "user-confirmed edited text",
  "kind": "episode",
  "source": { "external_chat_id": "opaque-chat", "external_message_id": "opaque-answer" }
}
```

The BFF verifies authenticated ownership and the persisted assistant/user linkage,
forces source-backed writes to `episode`, and uses a service credential plus opaque
user identity. The internal `/v1/memories` accepts the same optional source contract
and forwards it to the repository's existing atomic `memory_source` insertion.
Existing clients without `source` retain their manual-create behavior. Source
tracking uses the existing schema, without Open WebUI foreign keys or domain
dependencies. Durable retention and its migration are described in
`services/memory/RETENTION.md`.

Source IDs are provenance, not a claim that the edited text exactly matches the
original answer. Exact duplicate/tombstone responses are displayed as **not added**,
not success. Multiple clicks are blocked while saving; retries are protected by the
existing per-owner content deduplication. Deleting a memory also clears its stored
source via the existing repository path.

Tests cover source ownership and lineage, permission/write modes, service failure,
secret/size rejection before embedding, tenant/user isolation, duplicate handling,
branch preview, hidden text and request shape. An opt-in PostgreSQL test covers
source persistence and deletion; run only against a disposable pgvector database.
