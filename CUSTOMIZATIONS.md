# Upstream integration points

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
