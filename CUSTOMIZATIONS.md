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
| `.dockerignore` | Keep the independent service's local virtual environment and test cache out of the WebUI image build context. |

Rollback: `KAKAM_MEMORY_ENABLED=false` and restart WebUI. Native data is untouched;
new KaKam records remain in their own database and are not copied to native Memory.
See `services/memory/README.md` for the scope and deployment of this first slice.
