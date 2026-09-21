# KaKam Memory Manager · default v2

这是独立 Memory Manager / Server 的第一版实现，不是完整 Agent 平台，也不是热安装插件。
自定义 UI 位于 `src/lib/kakam/memory/`，Open WebUI 适配层位于
`backend/open_webui/kakam/memory/`。本服务不导入 Open WebUI。

完整 Manager 契约、迁移和升级步骤见 [MANAGER.md](MANAGER.md)。该版本取消普通聊天自动写入。

## 当前行为

- Prompt：已有 System → 有界长期记忆块 → 当前分支 Session 消息 → 当前 Prompt。
  不替换管理员/用户原有 System，不打乱历史与工具调用。Session 直接复用 Open WebUI
  持久化聊天。KaKam 启用时由 Manager 独占压缩：摘要单独保存在 Memory DB，原始消息不变。
  需单独配置 MEMORY_CONTEXT_* 模型；未配置、失败或复杂非文本内容则保留原始上下文并显示状态。
- 长期记忆：默认最近 **30 天**，用户可选 **7 / 14 / 30 天**（包含今天，而非排除最近 7 天）。
  保存后 30 天过期；缩小窗口只改变召回，不删除数据。独立 PostgreSQL + pgvector 精确余弦检索，
  先过滤用户/状态/有效期/向量版本，再排序；优先 profile/preference/instruction，最多 12 条，
  内容预算 6000 UTF-8 字节（计入 JSON 转义，另有固定分隔块开销）。
- 保存方式：设置页主动保存，或 Context 中创建建议并确认。模型工具只能提出建议和召回，
  不能批准自己的写入。**普通聊天不再自动抽取/写入**；旧 TurnCompleted 接口兼容返回 queued=false。
  升级会停止旧的未审批抽取任务，worker 仅保留清理功能。临时/频道聊天不读写长期记忆。
- `default` 是当前唯一注册策略。点击用户头像 → **Memory Policy**，直接打开独立设置页；
  也可从设置侧栏进入。原「个性化」入口保留兼容。
- Context → Session Memory：按条目选择自动/优先使用/排除，开关自动召回及压缩，设置触发额度；
  查看摘要、待确认建议、编辑分类和标签、创建父子集合/多集合成员关系、查看最近 Manager 决策。
  列表与集合树是第一版知识视图，不声称提供完整知识图谱或自动实体推理。
  Hand-off 保留显式生成、流式输出、编辑和复制；连接正常时先由 Manager 整理可见快照，
  再通过现有 WebUI 模型调用生成，因此不会把 WebUI 模型密钥复制进 Memory 服务。
- Memory Policy 页参考「用量 → Token 活动」展示概览、按日方格、类别筛选与日期详情。
  紫=System、绿=长期记忆、蓝=Session、橙=当前 Prompt；全部模式按当天占比最高类别着色，
  单类别模式按该类别占比着色，颜色越深占比越高，灰色表示无统计或该类别占比为零。
  点击一天查看当天四类占比，点击“返回整个周期”恢复累计。默认查看 180 天活动，可选 7/30/90/180 天；
  这是**统计周期**，不改变策略的 7/14/30 天长期记忆窗口。
  占比按已保存请求的字符数加权计算，不是请求占比或计费 Token；旧对话、临时对话不补算。
  所有分支中已保存的响应快照均计入统计，用户删除聊天后对应快照不再计入。
- 聊天输入区仅保留「Context · 查看详情」按钮，默认收起；桌面右侧抽屉、手机全屏抽屉。
  支持关闭按钮、Esc、点击桌面遮罩，关闭后焦点回到入口。切换响应会关闭旧详情。
  抽屉内方格图显示选中响应的四类文本字符数量；紫=System，绿=长期记忆，蓝=Session，橙=当前 Prompt。
  点击图例突出该类别，悬停显示字符数。按响应保存到已有 `message.meta`，切换分支可查看对应统计。
  图中是推理前快照，不是输入框实时预览；后续工具循环不更新快照。
  不含图片、工具 schema、供应商侧包装；token 仅 UTF-8 字节估算，**不是计费 token**。
- 抽屉的四类原文按需通过 BFF 获取，以纯文本展示，不执行 HTML。System 原文仅管理员可见，
  普通用户只能看其数量。Session/当前 Prompt 按 role 分隔，长期记忆显示实际注入的有界文本块。
  原文仅保存在 WebUI 进程内：最多 128 份、每类 16000 字符、15 分钟，超额提前淘汰；
  定时清理不依赖后续请求。关闭页面释放前端详情状态，原文不写入聊天 metadata/广播事件。
  metadata 只新增随机详情 ID；读取时重新检查权限、用户和聊天归属，响应禁止浏览器缓存。
  旧记录只保留数量；重启、过期、多 worker 命中其他进程时可能没有详情，不用当前数据重建历史。

## Cache

1. Embedding：进程内 LRU 512 项 / 300 秒，按用户 + embedding 空间版本 + 文本摘要隔离。
2. 召回：进程内 LRU 256 项 / 60 秒，按租户/用户 + session + session revision + policy version + 窗口 + DB revision + embedding 版本 + query 摘要隔离。
3. 新增/遗忘事务递增用户 revision，各 API 实例下次读取立即失效；命中后仍复核有效期和时间窗口。
4. 稳定的输出次序减少无意义的 Prompt 前缀变动，但不承诺供应商 Prompt Cache 命中。
   设置的“复用召回缓存”只关闭第 2 层；图中的命中也只指第 2 层。

这是完全匹配缓存，不复用其他问题的 LLM 答案；不会为追求命中率返回跨用户或过时信息。
不同问题仍需检索，没有引入 Redis。

## 首次 Docker 部署

从 **KaKam-webui 仓库根目录**执行。此文件是独立 Compose，不要与原 `docker-compose.yaml` 叠加。
它新建命名卷，不会自动使用/迁移现有 WebUI 数据；已有部署请先备份并明确映射现有数据卷。

```sh
cp deploy/memory/.env.example .env.kakam
chmod 600 .env.kakam
```

用密码管理器分别生成并保存 5 个独立随机值，或分别运行 `openssl rand -hex 32`，
把输出填进 `.env.kakam`，不要把真实密钥提交到 Git、工单或聊天中：

| 变量 | 用途 |
| --- | --- |
| `POSTGRES_PASSWORD` | PostgreSQL 初始化管理员密码，仅 DB 容器持有 |
| `MEMORY_DB_PASSWORD` | 独立非超级用户 `kakam_memory` 的密码；此示例请使用 hex，避免连接 URL 转义问题 |
| `WEBUI_SECRET_KEY` | WebUI 签名/加密密钥，升级和重建时保持不变 |
| `MEMORY_SERVICE_KEY` | BFF 与 Memory API 之间的凭据；至少 32 字符 |
| `MEMORY_CONFIG_ENCRYPTION_KEY` | 管理界面配置加密主密钥，固定 64 位 hex；与数据库备份分开安全保存，不可随机重置 |

模型配置可先留空，启动后进入 **设置 → 管理员 → AI → Memory 服务** 配置。
也可在环境变量中填写 embedding 的 BASE_URL、API_KEY、MODEL、DIMENSION；维度必须与实际响应一致。
自动压缩使用独立的 MEMORY_CONTEXT_BASE_URL、MEMORY_CONTEXT_MODEL 和相应 API_KEY，
不自动复用 WebUI 聊天模型。模型接口应使用 HTTPS，或受信任的私网 endpoint。
详情及升级注意事项见 [管理员配置](ADMIN_CONFIG.md)。

```sh
docker compose --env-file .env.kakam -f compose.kakam.yaml config --quiet
docker compose --env-file .env.kakam -f compose.kakam.yaml up -d --build
docker compose --env-file .env.kakam -f compose.kakam.yaml ps
docker compose --env-file .env.kakam -f compose.kakam.yaml logs --tail=80 memory-api memory-worker
```

只绑定 `127.0.0.1:3000`，在服务器前加 HTTPS 反向代理；调试可用 SSH 端口转发。
Memory API 和 PostgreSQL **不发布宿主机端口**。
首个 WebUI 管理员创建后，在管理设置中配置聊天模型，再打开个性化设置验证 `default`。
首次镜像构建需要下载上游前端/后端依赖；不要用官方未修改镜像替代本项目构建。

### 「记忆服务不可用 · 已降级」排查

这表示**那次请求**的召回捕获了异常，不是“没有长期记忆”，也不是用户开关没开。
`compose.kakam.yaml` 已设置 `KAKAM_MEMORY_ENABLED=true` 并共享 `MEMORY_SERVICE_KEY`。
诊断以日志为准；历史快照不会随服务恢复改变，需要发新消息验证。

```sh
docker compose --env-file .env.kakam -f compose.kakam.yaml ps
docker compose --env-file .env.kakam -f compose.kakam.yaml logs --since=10m --tail=100 open-webui memory-api memory-worker
docker compose --env-file .env.kakam -f compose.kakam.yaml exec -T open-webui python -c "import urllib.request; print(urllib.request.urlopen('http://memory-api:8081/health', timeout=5).status)"
```

分享诊断时只截取 `KaKam recall skipped (...)`、错误类型和 HTTP 状态码，先去掉私人内容；
不要分享完整日志、`.env.kakam` 或 `docker compose config` 的密钥输出。

| 日志/现象 | 下一步 |
| --- | --- |
| `ConnectError`、健康检查失败、容器反复重启 | 检查 memory-api / memory-db 状态、数据库初始化与容器网络；不要删卷 |
| `RuntimeError` | 检查 WebUI 服务密钥是否缺失；不要重新生成已有数据库/签名密钥 |
| `HTTPStatusError` | 结合 memory-api 日志区分内部鉴权失败、embedding 供应商错误、模型/向量维度错误 |
| `TimeoutError` / `ReadTimeout` / `ConnectTimeout` | 检查网络及 embedding 耗时；默认召回总时限 1500ms，必要时临时设 5000ms 对照验证，会增加聊天等待时间 |

`/health` 仅验证数据库，不验证 embedding；即使没有已保存记忆，首次召回仍可能调用 embedding。
必须单独设置 `MEMORY_EMBEDDING_BASE_URL`（含 `/v1`）、`MEMORY_EMBEDDING_API_KEY`、
`MEMORY_EMBEDDING_MODEL`、`MEMORY_EMBEDDING_DIMENSION`；聊天模型的 Key 不会自动复用。
不要把聊天模型名直接作为 embedding 模型；维度须与实际返回一致，已有向量更换模型需规划回填。
确认/修正 env 后沿用原文件、项目名、数据卷执行原 `up -d --build` 命令（不能仅 restart 来更新 env）。
在头像 → Memory Policy 打开用户记忆开关，用“测试真实服务连接”和手动保存测试读写；
模型的“请记住”建议需在 Context → Session Memory 中刷新并确认。
目前未获得远端错误日志，不能把这些可能原因当作已定位的根因。

### 保存、备份和密码变更

- `.env.kakam` 被仓库 `.env.*` 规则忽略；仍需 `chmod 600`，并在密码管理器/加密备份中另存一份。
  不要执行会打印全部密钥的 `docker compose config` 并把输出分享出去，校验用 `config --quiet`。
- `kakam_memory-data` 保存长期记忆和队列；`kakam_webui-data` 保存 WebUI 用户、设置、聊天。
  定期做 PostgreSQL 逻辑备份和 WebUI 数据一致性备份，备份本身包含私人内容，需要加密和限制访问。
- 升级使用同一 Compose 项目名和同一份 env；**不要执行 `down -v`**，它会删除数据卷。
- PostgreSQL 初始化变量只在空数据卷生效。现有库改密码必须同时修改实际数据库角色密码与 env，
  不能只改 `POSTGRES_PASSWORD` / `MEMORY_DB_PASSWORD` 后重启，更不能删卷“修复”。
- 轮换服务凭据需同步更新 API、worker、WebUI；不要为日常重启重新生成 `WEBUI_SECRET_KEY`。

## 服务接口与安全边界

浏览器仅访问 `/api/custom/memory`（GET/POST）、`/{id}`（DELETE）及 `/policies`（GET）。
另有 `GET /api/custom/memory/context/{snapshot_id}`，返回当前用户自有聊天的短时文本预览；
无权限返回 403，匿名返回 401，失效/非本人/已删除聊天返回 404，System 原文按管理员身份裁剪。
另有 `GET /api/custom/memory/activity?days=30`（7..180），从 WebUI 自己的消息 metadata
读取当前用户的数量快照并按 UTC 天聚合。只返回数量，不返回记忆/聊天原文。
查询最多取最近 5000 条带 metadata 的候选响应；超过时 UI 明确提示部分统计，不冒充全量。
权限在后端重查，浏览器不能指定 owner；Memory 服务宕机时仍可查看已保存统计。
BFF 验证登录、`features.memories` 权限；身份来自已认证用户，不接受浏览器传入 owner。
内部 API 使用 `Authorization: Bearer <service key>` 与 `X-Memory-User: <opaque user id>`。
服务密钥持有者是可信身份签发方，所以绝不能向浏览器公开密钥或把 API 直接暴露公网。
内部身份包含 `X-Memory-Tenant` 命名空间，默认 default；升级既有数据不要擅自更换该值。

| 内部接口 | 用途 |
| --- | --- |
| `GET /health` | 数据库可用性，不表示 embedding/抽取供应商可用 |
| `GET /v1/policies` | 返回 default 注册信息 |
| `GET/POST /v1/memories` | 列表（最多 200 条）/手动创建 |
| `DELETE /v1/memories/{id}` | 用户隔离的遗忘 |
| `POST /v1/recall` | `{query, policy:"default", days:7..30, cache:true}` |
| `POST /v1/events/turn-completed` | 兼容旧客户端，不再入队；请使用明确保存动作 |

Recall 总超时默认 1500ms；失败继续聊天，并在图中显示降级。手动保存允许最多 30s。
Worker 保留数据库清理，旧自动抽取任务停止写入。
删除清空原文和向量，保留摘要墓碑至原到期时间，阻止尚未完成的任务重新插入完全相同的内容。
常见密钥形式被拦截，但正则不是全面 DLP；不要主动发送敏感凭证，embedding/摘要供应商会收到相应用户文本。
召回文本以转义 JSON 放入明确“不可信数据”分隔块；这减少指令混淆，不是模型级注入安全保证。

### 第一版边界

这是目标架构的增量切片：已增加手动编辑、Session 摘要、Session 操作查询和集合视图。
暂未实现语义去重/冲突自动 supersede、独立全局 pin、原生 Memory 迁移、向量换代回填及生产指标面板。
本版只做精确文本去重，不会自动覆盖矛盾事实；可在设置页遗忘旧事实，当前输入优先。
旧模型/endpoint/维度的向量不会与新空间混算；更换后需要另行回填，不能把“没有召回”当数据迁移成功。
手动保存和确认有明确失败提示；普通聊天无需持久化抽取 outbox，因为它不再写入长期记忆。

开启 KaKam 时禁用原生自动召回、后台 review、模型 Memory 工具并替换设置页；原生历史数据不变。
原生 HTTP Memory API 仍保留兼容性，不应由旧客户端继续调用；原生数据不会进入 KaKam。
暂停新写入：`KAKAM_MEMORY_WRITE_MODE=off`；召回独立支持 `off|shadow|on`。
WRITE_MODE=shadow 与 off 均禁止首版管理动作落库；shadow recall 只查询不注入。
回滚设置 `KAKAM_MEMORY_ENABLED=false` 并重启 WebUI，切回原生，独立数据仍保留。
迁移 002 后不能直接将 Memory 服务二进制降级为旧版；完整回滚需恢复升级前数据库备份。

## 验证

```sh
python3.11 -m venv services/memory/.venv
services/memory/.venv/bin/pip install -r services/memory/requirements.txt pytest
# 可选：运行 WebUI adapter 的 SQLite 查询集成测试（复用上游依赖）
services/memory/.venv/bin/pip install 'sqlalchemy[asyncio]==2.0.50' aiosqlite==0.22.1
services/memory/.venv/bin/pytest -q services/memory/tests
npx vitest run src/lib/kakam/memory
npm run check
npm run build
```

PostgreSQL 集成测试仅在设置 `KAKAM_TEST_DATABASE_URL` 时运行：须为**专用可丢弃测试库**，
账号有创建 schema/extension 权限；测试创建随机 schema 后只删除该 schema，勿指向生产库。
API/adapter 单测使用 fake provider/repository，不会调用真实模型或用户数据库。

上线冒烟：用户 A 保存偏好 → 新聊天询问 → 图中看到长期记忆；相同 Prompt 再试检查 cache；
用户 B 不可见 A 的记忆；遗忘后新请求不再召回；切换窗口、临时聊天、Memory 服务停止时仍可正常聊天；
刷新后对应响应的方格图仍在。现有聊天记录里的旧文本不会因遗忘长期记忆而消失。

### Manager v1 本地验证（2026-09-21）

- Python 48 项通过，包含真实 PostgreSQL + pgvector、旧版数据迁移、确认写入、隔离、HTTP 连接和重启持久化。
- 前端 Memory / Hand-off 32 项测试通过，Vite 生产构建通过；Python 编译、基础 Ruff、Compose 配置校验通过。
- 组件验收覆盖 1280px 桌面侧栏、390px 手机全屏、无横向溢出、Session 排除、确认建议和集合视图。
- 全仓类型检查为 7777 个错误、202 个警告，本次 KaKam 模块无报错；全仓检查没有通过。
- HTTP embedding/摘要使用可控 fixture，UI 组件验收使用测试数据；未连接远端生产供应商，需部署后 smoke test。

### 管理员配置增量验证（2026-09-21）

- Python 53 项通过，包含 PostgreSQL 配置迁移、密文落库、主密钥错误、租户隔离、管理员鉴权、
  签名真实 HTTP 请求、修订冲突、保存/恢复、向量空间切换确认、热更新缓存失效及供应商错误脱敏。
- Context 两种协议、截断响应拒绝和 Embedding 测试使用 HTTP fixture，不访问生产密钥或真实聊天。
- Memory / Hand-off 前端 34 项通过、Vite 生产构建通过；基础 Ruff、Compose 与 diff 检查通过。
- 组件测试数据验收覆盖桌面 1280px / 手机 390px、测试草稿、保存来源切换、恢复前确认及无横向溢出。
- 全仓类型检查仍有 7777 个既有错误、202 个警告，本次自定义模块无错误；不能视为全仓检查通过。
- 本地验证不包含远端部署，实际供应商连接仍需部署后验收。

### 历史验证记录（2026-09-19）

- Python 29 项通过；PostgreSQL 2 项跳过（本机 Docker daemon 未启动，也未提供专用测试库）。
- 前端 Vitest 4 项通过，`npm run build` 通过，Python 编译与基础 Ruff 检查通过，Compose 配置校验通过。
- 浏览器使用组件测试数据确认了方格渲染/图例筛选、窗口与缓存设置回调、手动添加列表更新；
  不等同于真实模型 + PostgreSQL + WebUI 全链路验证，部署后需执行上述冒烟检查。
- `npm run check` 与未修改 HEAD 均为 7789 个类型错误，新增模块没有类型错误；不把全仓检查标记为通过。
- 本机原 Node 22 动态库损坏，前端验证使用可用 Node 24.19；交付 Dockerfile 仍使用上游规定的 Node 22。

Memory Policy 入口与活动页增量验证（同日）：

- Python 32 项通过（含 SQLite 查询的用户/聊天归属隔离），PostgreSQL 2 项仍因缺少专用库跳过。
- 前端 Vitest 12 项通过，Vite 生产构建通过；基础 Ruff 和 diff 空白检查通过。
- 浏览器组件验收使用模拟数据验证头像入口、四类占比、周期切换、日期选中和类别筛选；
  尚未执行真实登录用户与 PostgreSQL 的全链路验收。
- 全仓类型检查仍为 7789 个原有错误、202 个警告，自定义模块无报错。

Context 抽屉增量验证：

- Python 36 项通过、前端 Vitest 12 项通过；PostgreSQL 2 项仍跳过。
- 生产构建通过；全仓类型检查仍为原有 7789 个错误、202 个警告，本次模块无新增报错。
- 模拟数据组件验收覆盖桌面右侧/390px 手机全屏、按需读取、原文纯文本展示、旧记录兼容、
  关闭按钮/Esc/遮罩以及焦点恢复。不是远端真实模型 + 数据库全链路验收。
- 新增测试覆盖预览所有者隔离、聊天归属、System 权限、无缓存响应、容量/长度/过期清理、
  预览故障不阻塞聊天，且 socket 事件仍不含原文。

依赖复用现有栈的 FastAPI/Uvicorn、HTTPX 和 Psycopg；新增 cryptography（复用上游版本）实现 AES-GCM 配置加密。
独立服务需单独安装这些依赖；pgvector 使用数据库扩展，
无需额外 Python vector SDK。参考：[pgvector](https://github.com/pgvector/pgvector) 和
[Compose 环境变量](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)。
