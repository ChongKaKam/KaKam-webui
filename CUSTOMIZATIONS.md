# Upstream integration points

## Resource-aware Docker deployment

`Dockerfile`: replace the commented Node heap option with build-only
`NODE_MAX_OLD_SPACE_SIZE` (default 6144MB). The custom `compose.kakam.yaml` passes
`KAKAM_BUILD_NODE_HEAP_MB`; `deploy.sh` checks resources, builds serially, backs up
databases/configuration, and waits for container health. See `deploy/README.md`.

## Administrator Memory provider configuration

| Upstream file | Reason / delegated behavior |
| --- | --- |
| `backend/open_webui/main.py` | Register the admin-only Memory configuration BFF router. |
| `src/lib/components/chat/SettingsModal.svelte` | Add the admin AI / Memory service entry and mount `src/lib/kakam/memory/admin/components/MemoryAdminSettings.svelte`. |
| `src/lib/components/admin/Settings/Interface.svelte` | Wrap native compaction controls with the custom `CompactionOwner` component: display Manager ownership and a settings link when KaKam is enabled, otherwise preserve the original controls and saved values. Ownership is read from the authenticated BFF, independently of Memory service availability. |

Provider settings, validation, encrypted persistence and live configuration snapshots belong to the independent
Memory service; the BFF only authenticates admins and signs internal requests. `cryptography` is added to the
independent service (same version as upstream) for authenticated AES-GCM encryption. See
`services/memory/ADMIN_CONFIG.md` for deployment, key handling, API protocols and embedding migration limits.

## Memory Manager v1 / default policy v2

All new domain behavior remains in `services/memory/kakam_memory/`; BFF adaptations
in `backend/open_webui/kakam/memory/`; UI in `src/lib/kakam/memory/` and the existing
`src/lib/kakam/handoff/`. No new production dependencies.

| Upstream file | Reason / delegated behavior |
| --- | --- |
| `backend/open_webui/main.py` | Mount the authenticated Manager BFF router alongside existing Memory endpoints. |
| `backend/open_webui/utils/middleware.py` | Delegate context compaction to the KaKam adapter; use native compaction only when KaKam is disabled. Original messages remain unchanged in storage. |
| `backend/open_webui/utils/tools.py` | Register bounded KaKam recall/proposal tools; no model approval or direct SQL tool. Native Memory tools remain suppressed. |

Completed-turn hooks now save usage only, never implicitly persist knowledge.
The service migration cancels legacy unapproved jobs. Model-proposed records need
an authenticated user's separate confirmation. See `services/memory/MANAGER.md`
for contracts, deployment, limitations, and migration/rollback precautions.

## KaKam Memory default v1

Custom implementation: `services/memory/`, `backend/open_webui/kakam/memory/`,
`src/lib/kakam/memory/`. Independent PostgreSQL/pgvector service; no native Memory
data migration and no dependencies on Open WebUI tables from the service.

| Upstream file | Reason / behavior delegated to custom modules |
| --- | --- |
| `backend/open_webui/main.py` | Register `/api/custom/memory`; expose Personalization when custom Memory is enabled. |
| `backend/open_webui/utils/middleware.py` | Recall before inference; emit composition; deliver completed user turn; suppress native recall/review during cutover. |
| `backend/open_webui/utils/tools.py` | Suppress native Memory tools when custom Memory is active, avoiding dual writes. |
| `src/lib/components/chat/Settings/Personalization.svelte` | Mount custom settings, using native management only when custom service is disabled. |
| `src/lib/components/chat/Chat.svelte` | Consume `kakam:memory` metadata and mount colored prompt matrix for the selected response. |
| `src/lib/stores/index.ts` | Add typed, persisted `kakamMemory` user preferences. |
| `src/lib/components/layout/Sidebar/UserMenu.svelte` | Mount the explicit Memory Policy entry in the avatar menu, delegating navigation and permission visibility to the custom module. |
| `src/lib/components/chat/SettingsModal.svelte` | Register a dedicated Memory Policy tab and mount its activity/management panel. Reuse the existing settings persistence callback. |
| `.dockerignore` | Keep the independent service's local virtual environment and test cache out of the WebUI image build context. |

Rollback: `KAKAM_MEMORY_ENABLED=false` and restart WebUI. Native data is untouched;
new KaKam records remain in their own database and are not copied to native Memory.
See `services/memory/README.md` for the scope and deployment of this first slice.

### Memory Policy activity UI

The custom adapter exposes `GET /api/custom/memory/activity?days=7..180` and
reads only the signed-in user's existing `chat_message.meta.kakamMemory` counts.
It joins the owning chat to prevent foreign/orphaned records appearing in reports.
No new upstream tables or migrations; no access to long-term memory text for analytics.
The UI mirrors the Usage/Token activity layout (summary, calendar squares, filters)
without modifying the native `Usage.svelte`. Color intensity represents character
share, not billable tokens. Original Personalization and per-chat composition remain.

### Context drawer

The existing `Chat.svelte` mount now delegates to a compact Context button and a
responsive drawer in `src/lib/kakam/memory/components/`; no further upstream edits.
Prompt previews use the existing pre-inference hook and a project-owned, bounded
15-minute in-process cache. Only a random preview ID joins the persisted counts.
The custom BFF authenticates each preview read and rechecks chat ownership;
System text is restricted to administrators. No raw preview text in socket events
or chat metadata, no new database tables, no upstream Drawer/Modal modifications.

## KaKam Cloud UI

Presentation policy: `src/lib/kakam/shared/cloud-ui.ts`. Cloud mode hides local
inference management (Ollama, llama.cpp and LM Studio download/unload controls)
while retaining ordinary model selection, pinning, cloud connections, model
configuration import/export, and all backend APIs. No saved configuration or
parameter values are deleted or migrated. This is UI policy, not authorization.

| Upstream file | Reason / behavior delegated to custom modules |
| --- | --- |
| `src/lib/components/layout/Sidebar.svelte` | Mount `memory/components/MemorySidebarItem.svelte` in expanded and compact navigation. Reuse Memory Policy permissions and settings navigation; close the mobile sidebar after opening settings. Existing avatar menu entry remains. |
| `src/lib/components/admin/Settings/Connections.svelte` | Gate Ollama controls and add/manage mounts using Cloud UI policy. Skip hidden Ollama config reads and writes; cloud settings loading does not depend on Ollama config. |
| `src/lib/components/admin/Settings/Models.svelte` | Gate the local inference Manage button and modal mount, preserving normal model configuration and import/export. |
| `src/lib/components/chat/ModelSelector/Selector.svelte` | Gate local management discovery, download targets and queued-download rows. Preserve cloud connection guidance and model selection. |
| `src/lib/components/chat/ModelSelector/ModelItem.svelte` | Gate local model unload action. |
| `src/lib/components/chat/ModelSelector/ModelItemMenu.svelte` | Gate local model deletion action; keep edit, pinning and links. |
| `src/lib/components/chat/Settings/Advanced/AdvancedParams.svelte` | Gate local inference controls centrally for every caller; retain shared sampling, reasoning, streaming and custom parameters. |

Hidden parameter controls: `mirostat`, `mirostat_eta`, `mirostat_tau`,
`repeat_last_n`, `tfs_z`, `repeat_penalty`, `use_mmap`, `use_mlock`, Ollama
`think`/`format`, `num_keep`, `num_ctx`, `num_batch`, `num_thread`, `num_gpu`,
and `keep_alive`. Existing values remain untouched. `top_k`, `top_p`, `min_p`,
temperature and the custom parameter editor remain available for compatible
providers.

UI rollback: set the three Cloud UI policy fields to `true` and rebuild the
frontend. This does not change server-side provider enablement. About, document
embedding configuration and Ollama Cloud web search are outside this UI slice.

## KaKam chat and settings refinement

Mobile action stability and settings typography: `MessageInput.svelte` adds the
`kakam-composer-primary-action` hook to voice/send/stop buttons. The scoped theme
keeps their touch targets identical and icons centered across input states.
`common/InterfaceSettings.svelte`, `chat/Settings/UserSettingRow.svelte`,
`chat/Settings/UserSettingField.svelte`, `admin/Settings/AdminSettingRow.svelte`,
and `admin/Settings/AdminSettingField.svelte` add semantic label/description
hooks only; typography remains in `src/lib/kakam/shared/theme.css`. No settings
values, defaults, permissions or event handlers are changed.

Presentation and capability logic live in `src/lib/kakam/shared/theme.css`,
`src/lib/kakam/chat/`, and `src/lib/kakam/settings/`. Memory activity continues
using the existing project-owned panel and API. No new production dependencies.

| Upstream file | Reason / behavior delegated to custom modules |
| --- | --- |
| `src/routes/+layout.svelte` | Load the scoped KaKam presentation stylesheet after upstream styles. |
| `src/app.html` | Allow pinch zoom while preserving `viewport-fit=cover` for iPhone safe areas. |
| `src/lib/components/chat/Chat.svelte` | Add the chat style scope, bind existing per-chat params to both composer mounts, and delegate per-model Effort serialization to `chat/effort.ts`. |
| `src/lib/components/chat/MessageInput.svelte` | Mount `chat/components/EffortSelector.svelte` between the model selector and send actions. Add toolbar style hooks for responsive layout. |
| `src/lib/components/chat/Messages/CodeBlock.svelte` | Add four presentation hooks for code typography, contrast, spacing and toolbar; preserve highlighting, copying, collapse, execution and editing. |
| `src/lib/components/chat/SettingsModal.svelte` | Add style scopes, group/breadcrumb hierarchy, mobile search and `settings/components/MobileSettingsNav.svelte`; feed it the existing permission-filtered tabs. |
| `backend/open_webui/routers/openai.py` | Apply the private UI Effort override after saved model defaults, and map Chat Completions effort to Responses format through `kakam/chat/effort.py`. |
| `backend/open_webui/utils/chat.py` | Consume the private UI override before direct-connection or function dispatch so custom fields never reach those consumers. |

The composer is authoritative for Effort on UI chat requests. Unknown models
show `none` and omit the provider parameter, even when old global/model defaults
set it. Supported models default to `high`; only explicitly supported levels
are selectable. `extra high` serializes as `xhigh`. Per-model selections persist
with existing chat params. Metadata can override conservative built-in detection;
see `src/lib/kakam/chat/README.md`. Requests without the private override retain
upstream default handling. Responses requests use `reasoning.effort`.

The stylesheet keeps the user's UI scale/font preference, adds readable chat/code
spacing, larger settings targets, mobile wrapping, and safe-area padding. Safe-area
behavior still requires a physical iPhone check; desktop viewport testing cannot
simulate the notch or software keyboard fully.

## Cascading model menu and Shiki code styles

Project implementation: `src/lib/kakam/chat/components/CascadeModelSelector.svelte`,
`chat/model-menu.ts`, and `src/lib/kakam/code/`. Shiki 4 is already a production
dependency and is used by upstream file/notebook previews; no dependency changes.

| Upstream file | Reason / behavior delegated to custom modules |
| --- | --- |
| `src/lib/components/chat/MessageInput.svelte` | Enable the cascading selector and bind chat params; model selection clears the transient @model override. Remove the separate Effort dropdown. |
| `src/lib/components/chat/ModelSelector.svelte` | Add an opt-in custom selector mount; reuse existing pin/default persistence, available model store and multiple-model permissions. Other callers keep the native selector. |
| `src/lib/components/common/Dropdown.svelte` | Reposition on width changes as well as height changes, keeping the second menu panel inside the viewport. Existing visual-viewport handling covers the mobile keyboard. |
| `src/lib/components/chat/Messages/CodeBlock.svelte` | Mount custom Shiki presentation and an edit/done toggle. Default to highlighted reading; the existing CodeEditor, copy/save/run, collapse and diagram paths remain. |
| `src/lib/components/common/InterfaceSettings.svelte` | Mount `code/components/CodeStyleSettings.svelte` using existing current settings and persistence callbacks, for both personal and admin-default interface settings. |
| `src/lib/stores/index.ts` | Type the persisted `kakamCodeTheme` preference, with invalid or missing values resolved to GitHub by the custom module. |

The capsule combines model name and current effort. The desktop menu has adjacent
model/effort panels; below 640px it becomes a single panel with a back action.
Search includes names, IDs and descriptions; hidden models stay hidden, pinned
models sort first. Comparison mode keeps per-model effort selections and supports
removal without clearing the other models. Arrow keys navigate, Right opens effort,
Left returns to models, and Escape closes the active level. Selection still uses
the existing conservative capability and request serialization policy.

Code styles: GitHub, VS Code, Catppuccin and Minimal, each paired for light/dark.
Rendering reuses Shiki's lazy singleton and locally bundled languages/themes;
no CDN or external highlighting requests. Streaming updates are coalesced for
100ms with escaped plain text visible while loading. Unknown languages, load
failures and code beyond 40,000 characters or 1,000 lines stay readable as plain
text. An in-memory cache is bounded to 24 results / one million source+HTML
characters. Raw code is never treated as HTML; only Shiki's escaped serialization
is mounted. This preference affects chat display, not the editing surface or
upstream file/notebook previews.

The project-owned stylesheet removes composer border/outline highlighting and
widens the model capsule; buttons retain visible keyboard focus styling. The
previous standalone Effort component and Highlight.js color overrides were
removed after their callers switched to the new modules.

## Context hand-off and compact code controls

| Upstream file | Reason / behavior delegated to custom modules |
| --- | --- |
| `src/lib/components/chat/Chat.svelte` | Pass current history and per-chat params through the existing PromptComposition mount to the project-owned hand-off panel. No new persistence or chat mutation. |
| `src/lib/components/chat/Messages/CodeBlock.svelte` | Replace the text toolbar with `code/components/CodeToolbar.svelte`. Reuse existing collapse, run, preview, copy and save callbacks; a single edit/save icon changes mode and Ctrl/Cmd-S returns to highlighted reading. |

The model picker now uses one fixed-width, fixed-height viewport for both steps
on desktop and mobile, opened by click/keyboard rather than hover. Back does not
commit a model change; choosing an effort commits model and effort together.
The popup scrolls when available vertical space is limited. Light code surfaces
use a shared pale-gray background while dark themes keep their Shiki colors.
Context matrix labels and captions are larger.

Hand-off implementation lives in `src/lib/kakam/handoff/` and is mounted by the
existing project-owned Context drawer. It defaults to the selected response's
model, lets the user choose another available model, and uses the existing
authenticated `/api/chat/completions` dispatcher, including model access checks and
per-model effort policy. Requests do not carry parent/chat IDs, so they do not
create a chat or trigger KaKam Memory recall/extraction. No new backend endpoint,
dependency or database schema. Direct models use the active socket session.

Input follows only the selected response's parent chain, including that response;
it never merges sibling replies. It includes available, unrestricted long-term
Memory preview text, never System preview text, image payloads or attachment
files. Known hidden reasoning blocks are omitted. The initial objective and recent
messages are bounded, with explicit notices for missing/truncated context. Expired
Memory snapshots do not prevent conversation-only generation. The prompt treats
source records as data and asks the model to distinguish verified work from plans.
Opening Hand-off only reveals the panel; Generate explicitly starts the request.
The user-provided editorial prompt lives in `handoff/prompt.ts`. SSE chat/Responses
output is displayed incrementally (JSON responses remain supported), with elapsed
time and connection/reasoning/output status; reasoning content is not displayed.
Generation is cancellable, with a three-minute inactivity timeout and ten-minute
overall limit. Retry failures before new output preserve the previous text;
interrupted streams retain partial output with an incomplete warning. Results are
editable and remain only in the
open drawer until copied or exported as Markdown; closing the drawer aborts the
client request. UI validation uses mock responses rather than production chats.

## Supplier management and model allowlists

Custom implementation: `src/lib/kakam/providers/` and
`backend/open_webui/kakam/providers/`. Reuses the admin-only `/openai/verify`
models probe, native connection configuration persistence/cache invalidation,
and native model activation and access grants. No new dependencies or tables.

| Upstream file | Reason / delegated behavior |
| --- | --- |
| `src/lib/components/admin/Settings/Connections.svelte` | Mount project-owned SupplierSettings in Cloud UI mode; skip the legacy loader in that mode. The native Ollama-compatible settings remain available under the existing policy. The cloud UI omits the base-model cache switch; underlying caching remains supported. |
| `src/lib/components/chat/SettingsModal.svelte` | Rename the admin AI entries to 模型供应管理 and 模型管理. |
| `src/lib/components/admin/Settings/Models.svelte` | Rename the heading, mount an empty 模型路由 section above the list, and show supplier aliases alongside model names. Existing editor, activation, public/private and user/group grants are unchanged. |
| `src/lib/components/chat/ModelSelector.svelte` | Delegate model labels to the supplier-aware helper for both cascading and native selectors. IDs and selection behavior remain unchanged. |
| `backend/open_webui/routers/openai.py` | Validate supplier inventories before saving and supply only selected cached models. Keep original display names while applying native provider ID prefixes. Existing authentication, config storage, cache invalidation and request routing remain authoritative. |
| `backend/open_webui/utils/models.py` | Carry safe supplier provenance into presets derived from a supplier model. |

New suppliers receive immutable UUID-based ID prefixes, independently of their
editable aliases. The native dispatcher strips only the selected connection's
prefix before calling its upstream. Safe `kakam_provider` metadata contains only
supplier ID, alias and original model ID, never URL, credentials or headers.
Custom Effort recognition uses that original ID; explicit capability metadata
still wins. Hand-off model choices show the supplier label as well.

An editor requires successful model discovery before new credentials or a legacy
connection can be saved into the pool. Transport edits invalidate the probe;
failed/aborted probes cannot authorize a save. A saved, unchanged connection can
reuse its selected-model snapshot for alias and allowlist edits. Empty managed
allowlists load zero models, rather than triggering native auto-discovery.
Existing connection IDs and model/access records are not automatically migrated
or removed. Legacy connections adopt the explicit allowlist when edited and
saved; changing a legacy prefix is an explicit advanced operation with an ID and
permission warning. New unconfigured models follow native admin-only visibility
until the administrator grants access in Model Management. Removing a supplier
or a model from its allowlist does not erase its history or saved access settings.

Validation covers duplicate provider model IDs, prefix dispatch, empty pools,
snapshot consistency, safe metadata, and the native per-model access filter.
UI probes use a local mock server; no production supplier configuration is changed.
