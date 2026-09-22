# Chat Effort

All models offer `none`, `low`, `medium`, `high`, and `extra high`; the default
is `high` when no per-model selection is saved. Capability metadata and probe
results do not disable choices, including for unknown reseller aliases. Existing
per-model selections persist in the chat's `kakam_effort` params. Compare mode
and @model overrides resolve each request independently.

The capsule opens a fixed-size two-step model/effort menu on desktop and phone.
Going back does not commit a selection; choosing an effort commits the model and
effort together. The capsule summarizes the first model and additional model count.

`none` means **omit effort**, not send the literal string `none`. It removes stale
`reasoning_effort` and `reasoning.effort` from global/custom parameters and, through
the BFF override, saved cloud-model defaults. The provider can still apply its own
default thinking behavior. This is the compatibility fallback for providers that
reject effort parameters. Other reasoning fields such as `summary` are preserved.

`extra high` maps to `max` if explicitly advertised by model/provider metadata,
otherwise `xhigh`. Metadata is advisory and only helps with this wire encoding.
Native provider-specific thinking APIs are not automatically translated.

The BFF consumes `_kakam_reasoning_effort` after saved cloud-model defaults and
strips the private marker. Direct/function paths consume it before dispatch.
OpenAI Responses uses `reasoning.effort`. Legacy UI markers with value `none` are
also treated as omission. Requests without a marker retain native default handling;
this does not change non-UI API clients or native Ollama protocol conversion.

Chat errors retain their original content and mount `EffortErrorHint.svelte`,
which suggests choosing `none` and retrying if the provider rejects the selected
effort. The hint does not diagnose all failures as effort-related, change the user's
selection, or automatically retry an inference request.

Validation: `npx vitest run src/lib/kakam/chat src/lib/kakam/providers src/lib/kakam/handoff`
and `backend/open_webui/kakam/chat/test_effort.py` (including native Responses conversion).
