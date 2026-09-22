# Model suppliers

The Cloud UI mounts `SupplierSettings` through the existing Connections tab.
The editor probes `/openai/verify` using the current Base URL, API Key, auth and
protocol configuration. Successful model discovery unlocks whitelist selection
and save. Provider errors are presented without returning remote diagnostic bodies.
The 30-second request is aborted when the editor closes; credentials never go to
local/session storage or diagnostic logs from this module.

`OPENAI_API_CONFIGS[index].kakam_supplier` stores the stable supplier ID, editable
alias, and selected `{id, name}` model snapshot. `model_ids` mirrors that allowlist.
No selected models means no exposed models. Unmanaged legacy connections retain
native behavior until an administrator edits, probes and saves them. Their prefixes
are preserved to protect old chats, defaults and grants; new providers get unique
UUID prefixes. Native cache invalidation runs on save; the UI refreshes model data.

The adapter emits `kakam_provider: {id, alias, model_id}` alongside each model,
including the base-model cache. Native routing still uses `urlIdx` and `prefix_id`.
Presets inherit supplier metadata. Display aliases never replace routing IDs, and
Effort reads the original model ID. Each qualified ID uses its own native enabled
flag and model access grants (private/public/user/group). New models are visible
only to admins until those grants are configured.

This is a model catalog, not routing policy. `ModelRoutingSection` is intentionally
empty. Discovery verifies access to the provider's model-list endpoint, not that
every returned model can complete an inference request. Azure and other compatible
services must expose usable model/deployment IDs through their discovery endpoint.
No automatic migration of existing duplicate unprefixed connections is attempted;
the admin can set a distinct prefix explicitly after reviewing the displayed warning.

Tests: frontend service/API tests and `backend/open_webui/kakam/providers/test_inventory.py`.
The latter isolates the pure adapter and executes the native inventory/ACL functions
with stubbed external dependencies, without starting the application or a database.

## Automatic thinking-effort discovery

Every successful model probe now attaches a bounded `reasoning` capability to each
selected snapshot and exposes it inside `kakam_provider`. Re-probe and save an
existing connection to populate/refresh this information. No automatic production
migration and no extra inference requests are made. The editor distinguishes
supported, explicitly unsupported, and unknown results with their evidence source.

`reasoning.ts` reads explicit model-list `reasoning_effort` declarations at the
top level, in `capabilities`, or in `info.meta` (including its `capabilities`).
Declarations may be an array of wire levels, `false`, or an object containing
`values` / `supported: false`. A boolean `true`, generic reasoning support, or
`supported_parameters: ["reasoning_effort"]` without concrete levels cannot prove
which values work, so the result stays unknown. Unrecognized levels also stay
unknown. Missing capability fields never establish lack of support.

With no explicit declaration, a small catalog matches both an official HTTPS
endpoint and exact IDs. It covers the existing GPT rules and DeepSeek's documented
`deepseek-flash`, `deepseek-v4-flash`, `deepseek-v4-flash-vision-exp`, and
`deepseek-v4-pro` compatibility IDs. The DeepSeek rule was verified on 2026-09-21:
https://api-docs.deepseek.com/guides/thinking_mode/
Aliases such as `dpsk-4.1-flash` at resellers remain unknown unless metadata supplies
levels; provider names alone are not trusted capability evidence. These results
describe advertised support, not a measured change in inference behavior.

Capability results are advisory. Every model offers all five UI levels and defaults
to `high` unless a per-model selection is saved, including unknown and explicitly
unsupported results. Native administrator metadata takes priority only when choosing
the wire spelling of `extra high`: advertised `max`, otherwise `xhigh`. Missing
`medium` or negative capability metadata no longer disables a UI choice.

`none` omits the effort parameter and clears saved cloud-model effort defaults.
On a failed call, the chat error display suggests choosing `none` and retrying if
the provider rejects effort. It does not automatically retry or assert that effort
caused the error. The BFF still validates and preserves bounded capability snapshots;
malformed saved data falls back to unknown without breaking the model list or login.
