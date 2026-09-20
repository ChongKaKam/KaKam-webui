# Conversation hand-off

`service.ts` extracts the selected parent chain and constructs bounded source data;
`api.ts` calls the existing authenticated chat dispatcher; `HandoffPanel.svelte`
owns the ephemeral UI result and cancellation. The Context drawer passes history,
response ID, available Memory details, default model and effort params.

No chat or Memory writes: do not add `parent_id`, `chat_id`, chat tools, attachments,
or background task flags to these requests. Provider access remains enforced by
Open WebUI. The source includes at most the initial 4,000 characters, 20,000 recent
characters across 100 messages, and 4,000 characters of visible Memory. System
snapshots and hidden reasoning markup are excluded. The UI discloses omissions;
this is a bounded hand-off summary, not a full chat export.

Result text is not persisted. Closing the drawer discards it and aborts an ongoing
client fetch. Copy/export operate on the user-edited text. Opening the panel never
calls the model; Generate is the explicit action.
`prompt.ts` holds the full editorial instructions. `response.ts` consumes streaming
chat/Responses SSE, with a JSON fallback for compatible providers. It exposes only
answer text, never reasoning content. The UI shows connection/reasoning/output
progress and elapsed time. Requests stop after three minutes without activity or
ten minutes overall. In-stream errors, empty answers and premature EOF are surfaced.
A failed regeneration before new text keeps the previous result; interrupted
streaming keeps the partial new text with an explicit incomplete warning.
Server/provider cancellation follows existing HTTP behavior.
