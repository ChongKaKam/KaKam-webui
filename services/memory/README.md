# KaKam Memory · default v1

这是独立 Memory 服务的第一条可运行纵向切片，不是完整 Agent 平台，也不是热安装插件。
自定义 UI 位于 `src/lib/kakam/memory/`，Open WebUI 适配层位于
`backend/open_webui/kakam/memory/`。本服务不导入 Open WebUI。

## 当前行为

- Prompt：已有 System → 有界长期记忆块 → 当前分支 Session 消息 → 当前 Prompt。
  不替换管理员/用户原有 System，不打乱历史与工具调用。Session 直接复用 Open WebUI
  持久化分支及其现有上下文压缩；不是另建一份聊天数据库，也没有新增 Session 总结 LLM。
- 长期记忆：默认最近 **30 天**，用户可选 **7 / 14 / 30 天**（包含今天，而非排除最近 7 天）。
  保存后 30 天过期；缩小窗口只改变召回，不删除数据。独立 PostgreSQL + pgvector 精确余弦检索，
  先过滤用户/状态/有效期/向量版本，再排序；优先 profile/preference/instruction，最多 12 条，
  内容预算 6000 UTF-8 字节（计入 JSON 转义，另有固定分隔块开销）。
- 保存方式：设置页手动添加/遗忘；完成普通聊天后异步处理用户输入。
  未配置抽取模型时，仅识别“请记住：…”或“remember …”；配置后可提取有原文依据的长期事实。
  不从助手回答推断用户事实，临时/频道聊天不读写长期记忆。
- `default` 是当前唯一注册策略。点击用户头像 → **Memory Policy**，直接打开独立设置页；
  也可从设置侧栏进入。原「个性化」入口保留兼容。
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
2. 召回：进程内 LRU 256 项 / 60 秒，按用户 + policy + 窗口 + DB revision + embedding 版本 + query 摘要隔离。
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

用密码管理器分别生成并保存 4 个独立随机值，或分别运行 `openssl rand -hex 32`，
把输出填进 `.env.kakam`，不要把真实密钥提交到 Git、工单或聊天中：

| 变量 | 用途 |
| --- | --- |
| `POSTGRES_PASSWORD` | PostgreSQL 初始化管理员密码，仅 DB 容器持有 |
| `MEMORY_DB_PASSWORD` | 独立非超级用户 `kakam_memory` 的密码；此示例请使用 hex，避免连接 URL 转义问题 |
| `WEBUI_SECRET_KEY` | WebUI 签名/加密密钥，升级和重建时保持不变 |
| `MEMORY_SERVICE_KEY` | BFF 与 Memory API 之间的凭据；至少 32 字符 |

另填写 embedding 的 BASE_URL（包括 `/v1`）、API_KEY、MODEL、DIMENSION；维度必须与实际响应一致。
这与聊天模型是独立配置，不自动复用管理员存储在 WebUI 内的 API Key。
抽取模型的三项配置可先留空。模型接口应使用 HTTPS，或受信任的私网 endpoint。

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
本版是单 WebUI 实例身份域；未来多租户接入需增加明确 tenant namespace。

| 内部接口 | 用途 |
| --- | --- |
| `GET /health` | 数据库可用性，不表示 embedding/抽取供应商可用 |
| `GET /v1/policies` | 返回 default 注册信息 |
| `GET/POST /v1/memories` | 列表（最多 200 条）/手动创建 |
| `DELETE /v1/memories/{id}` | 用户隔离的遗忘 |
| `POST /v1/recall` | `{query, policy:"default", days:7..30, cache:true}` |
| `POST /v1/events/turn-completed` | `{chat_id,message_id,evidence}`，幂等入队 |

Recall 总超时默认 1500ms；失败继续聊天，并在图中显示降级。手动保存允许最多 30s。
Worker 任务持久化在 PostgreSQL，SKIP LOCKED、10 分钟租约、最多 5 次处理；完成/失败后清除输入证据。
删除清空原文和向量，保留摘要墓碑至原到期时间，阻止尚未完成的任务重新插入完全相同的内容。
常见密钥形式被拦截，但正则不是全面 DLP；不要主动发送敏感凭证，抽取供应商会收到用户文本。
召回文本以转义 JSON 放入明确“不可信数据”分隔块；这减少指令混淆，不是模型级注入安全保证。

### 第一版边界

这是 AGENTS.md 目标架构的增量切片：暂未实现语义去重/冲突自动 supersede、手动编辑/pin、
独立 Session 摘要、原生 Memory 迁移、审计查询 UI、向量模型换代回填及生产指标面板。
本版只做精确文本去重，不会自动覆盖矛盾事实；可在设置页遗忘旧事实，当前输入优先。
旧模型/endpoint/维度的向量不会与新空间混算；更换后需要另行回填，不能把“没有召回”当数据迁移成功。
完成事件到达服务后可重试，但 **BFF → Memory API 入队失败目前只有日志，没有跨服务持久 outbox**，
因此服务故障期间的自动记忆可能丢失；手动添加有明确失败提示。

开启 KaKam 时禁用原生自动召回、后台 review、模型 Memory 工具并替换设置页；原生历史数据不变。
原生 HTTP Memory API 仍保留兼容性，不应由旧客户端继续调用；原生数据不会进入 KaKam。
暂停新写入：`KAKAM_MEMORY_WRITE_MODE=off`；召回独立支持 `off|shadow|on`。
shadow 写入使用独立用户 namespace，不影响正式召回；shadow recall 只查询不注入。
回滚设置 `KAKAM_MEMORY_ENABLED=false` 并重启 WebUI，切回原生，独立数据仍保留。

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

### 本次本地验证（2026-09-19）

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

依赖仅复用现有栈的 FastAPI/Uvicorn、HTTPX 和 Psycopg（独立服务需单独安装）；pgvector 使用数据库扩展，
无需额外 Python vector SDK。参考：[pgvector](https://github.com/pgvector/pgvector) 和
[Compose 环境变量](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)。
