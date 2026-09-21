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
