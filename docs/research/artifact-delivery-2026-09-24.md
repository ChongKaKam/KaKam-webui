# KaKam WebUI 产物交付、会话归属与生命周期研究

日期：2026-09-24。范围：本地 Open WebUI 0.11.3 分支，HEAD `937196beb`，及当日官方文档。

这是现状研究和实施建议，不是已经实施的架构决策。没有修改运行时代码、线上配置、用户笔记或文件，也没有启用清理任务。工作区原有 usage 等未提交修改保持原样。

## 结论

1. 当前没有覆盖所有产物的统一存储、统一列表或统一过期策略。Artifacts、Notes、原生 Files、浏览器 Python 文件、Jupyter 文件和 Open Terminal 文件是不同路径。
2. 普通聊天不会自动得到服务器上的专用输出目录。要实现“每个聊天都有产物入口”，不必给每个聊天启动终端或容器；逻辑上按 `chat_id` 建立产物列表即可。
3. 现有 HTML/SVG Artifacts 主要是消息内容的前端投影。刷新后可以从仍然保存的消息重新提取，但没有独立产物记录、稳定产物 ID 或专门的过期时间。
4. Markdown 回复不会自动保存成笔记。调用 `write_note` 才创建笔记。此工具把内容写入 `note.data.content.md`；成功只表示笔记写入成功，不表示网页已经生成、运行、托管或验证。
5. 当前普通文件和笔记模型没有专用 `expires_at` 字段；未在检查的原生模型、路由、迁移和后台启动任务中发现统一产物 TTL/垃圾回收机制。
6. 删除聊天不会沿当前代码路径删除通用文件表中的记录及文件本体。关联表的级联删除只是解除关联；笔记也不会因为其创建来源聊天被删除而自动清理。
7. 推荐先补齐可靠下载和固定会话入口，再引入显式产物发布、独立版本与生命周期。不要把“所有输出存入 Notes”当作通用交付方案。

这里的“会话”指可持久化的聊天 `chat_id`。WebSocket `session_id`、Python execution ID、Jupyter kernel ID 和笔记 `note_id` 都不是同一个标识，不能直接替代它。

## 当前路径对照

| 路径 | 内容实际存放位置 | 与聊天的关系 | 下载方式 | 当前保留行为 |
| --- | --- | --- | --- | --- |
| 聊天 HTML/SVG Artifacts | 源码在消息中；预览内容在前端 store | 从当前聊天、当前消息分支提取 | 浏览器 Blob 下载 | 无独立 TTL；依赖消息仍然存在，临时聊天不保证重开可恢复 |
| 普通 Markdown 回复 | 聊天消息 | 随消息保存 | 当前缺少通用的单条回复 `.md` 文件下载入口；可复制 | 无独立产物 TTL，随消息 |
| Notes | `note` 表的 JSON 文档内容 | `write_note` 没有自动写入创建来源 `chat_id/message_id` | Notes 菜单导出 txt/md/pdf | 无统一 TTL；由笔记的删除流程管理 |
| 原生 Files／已接入的生成文件 | `file` 表 + 本地 uploads 或 S3/GCS/Azure | 可通过 `chat_file`、消息 files 或元数据关联 | 鉴权文件内容 API／附件入口 | 无通用产物 TTL；删除聊天不等于删文件 |
| Pyodide 文件 | 默认浏览器沙箱内存；可选 IndexedDB | 共享前端 worker；没有按 chat_id 建目录的默认保证 | 聊天侧栏 Files 中从虚拟文件系统下载 | 默认不持久化；开启持久化后仍是当前浏览器站点数据，无统一 TTL、不能跨设备恢复 |
| Jupyter 文件 | 外部 Jupyter 服务的文件系统 | 每次执行建立 kernel；无本地代码保证的 per-chat 输出目录 | 本地适配器主要返回 stdout/stderr/result；一般文件未自动变附件 | kernel 执行后销毁；磁盘文件生命周期取决于 Jupyter 部署 |
| Open Terminal 文件 | 外部终端工作区 | 普通连接共享工作区；编排器可选 per-chat | File Browser、display_file 卡片下载 | 取决于工作区存储及编排策略，不是 WebUI 通用产物 TTL |

### 1. Artifacts 是如何出现的

`Chat.svelte:getContents()` 通过 `createMessagesList(history, history.currentId)` 获取当前消息分支，再从可见输出中提取代码。`getCodeBlockContents()` 识别 HTML/CSS/JS 组合和 SVG。推理 details 被排除。

HTML 内容由前端包装后进入 `artifactContents`，在 `Artifacts.svelte` 的 iframe 中显示。下载时调用 `new Blob(...)`、`URL.createObjectURL(...)`，不是把文件保存到 WebUI 服务器的某个会话目录。当前下载函数统一使用 `text/html` 和 `.html`，包括从此按钮下载 SVG 的情况。

自动打开受 `detectArtifacts`、代码块闭合、当前聊天存在和非手机端等条件影响。手动预览和聊天菜单“产物”仍是另外的入口。**手机不自动弹出，不代表不支持预览。**

当前“Version N of M”切换的是提取结果列表；多个独立 HTML 输出也会进入同一列表。它不是具有稳定 artifact_id、父版本关系、内容校验和的产物版本库。切换消息分支或编辑消息可能改变列表和序号。

官方也将 HTML/SVG 等可渲染内容与 Markdown 文档、一般代码片段区分；后者并不会自动成为网页 Artifacts。[官方 Artifacts 说明](https://docs.openwebui.com/features/chat-conversations/chat-features/code-execution/artifacts/)

### 2. 为什么“网站”落成了 Markdown 笔记

内置 `write_note(title, content)` 的内容契约就是 Markdown，实际写入 `data={'content': {'md': content}}`。返回值包含 success、id、title、created_at，没有独立产物文件或下载能力描述。

Notes 编辑器会把 Markdown 解析为富文本；导出菜单只有 txt、md、pdf。即使笔记正文装着 HTML 源码，笔记保存成功也不等于完成交互网页交付。若正文只有说明文档，改扩展名不能补出缺失的 HTML/CSS/JS。

Notes 有自己的笔记聊天／内部聊天机制，但这不等于 `write_note` 已自动给原始创建聊天登记产物归属。原生 Markdown 回复也没有“自动存为笔记”的通用转换。

对本次 LLVM 示例：已知模型给出了两个 Note ID，用户能看到 Markdown 文档；尚未读取线上笔记源码和实际工具执行结果。因此可确认交付渠道的局限，不能断言该笔记从未包含 HTML，或 HTML 曾被编辑器改写。

### 3. 原生文件已经具备哪些可复用能力

默认存储根为 `DATA_DIR/uploads`；当前上传代码采用 `<uuid>_<filename>`，不是 `<chat_id>/outputs/`。`file` 表有所有者、路径、文件名、元数据、创建和更新时间，但无专用过期字段。可配置对象存储适配器。

`chat_file` 有 `chat_id`、`message_id`、`file_id`。同一个物理文件可能存在多个用途／引用，清理时不能只看某个聊天是否删除。当前聊天删除流程删除 chat/message；数据库级联可删除 chat_file 关联，但不会反向删除 file 或 Storage 中的对象。

文件下载 API `/api/v1/files/{id}/content?attachment=true` 已提供鉴权和 Content-Disposition。生成图像等路径会使用原生文件存储；插件也可以通过 `files` 事件把文件信息写到消息中。**事件里有 URL 只表示登记引用，不代表 WebUI 已把远端 URL 的字节归档到本地。**

现有 MCP 处理对图像/部分音频有专门适配；通用非图像 binary resource 在检查到的处理分支中可能只成为文字说明，而不会自动变为可下载附件。因此不能假设所有供应商/MCP 返回的文件已经打通。

### 4. 代码执行不等于持久化产物仓库

Pyodide 的 `ENABLE_PYODIDE_FILE_PERSISTENCE` 源码默认值是 false：走隔离沙箱，虚拟文件在当前运行环境内。开启后才使用挂载到 `/mnt` 的 IDBFS。前端使用共享 `pyodideWorker`，文件浏览器默认 `/mnt/uploads`，没有用 user_id/chat_id 划分持久化目录的默认逻辑。

这意味着“Python 执行结果可见”与“文件能在另一台设备下载”是两项能力。不能把浏览器 IndexedDB 当作服务器产物保存机制；超时导致 worker 终止也不同于有明确提示的文件过期。

Jupyter 适配器每次创建 kernel，并在退出时删除 kernel；返回结构主要是 stdout/stderr/result，图像有特殊提取路径。没有通用的“执行完成后收集所有新文件并登记下载附件”步骤。关闭 kernel 不意味着删除 Jupyter 磁盘上的文件。

### 5. 什么时候才真正有 per-chat 工作区

`utils/terminals.py:terminal_context_id()` 只有在管理员连接被识别为编排器、聊天配置选择 `context_id=chat_id`、且聊天是已保存聊天时，才生成 `chat:<chat_id>`。普通 Open Terminal 连接或默认共享配置返回空 context。

官方将其列为 Terminals 编排器能力，要求支持该功能的版本；普通终端、个人直连不自动获得相同的聊天隔离能力。默认 Shared；per-chat 还会增加同时运行的工作区数量。[官方 Terminal Contexts](https://docs.openwebui.com/features/open-terminal/terminals/orchestration/contexts/)

`display_file` 可以生成带 terminal_selector、session_id、path、name、mime_type 的结构化结果。前端随后向终端读取文件和下载；这通常是实时引用工作区路径，而非对当时版本作不可变归档。后来覆盖或删除同一路径会影响历史卡片的可用内容。

要分别理解：

- idle timeout：停止、回收空闲工作区运行实例。
- persistent storage：可让文件跨实例回收和重建保留。
- scheduled reset：按策略清理持久化文件。

因此不能把“空闲 30 分钟停止”理解为“文件 30 分钟过期”。官方把工作区配置和生命周期重置分开管理。[Policies](https://docs.openwebui.com/features/open-terminal/terminals/orchestration/policies/)、[Scheduled Resets](https://docs.openwebui.com/features/open-terminal/terminals/orchestration/scheduled-resets/)

## 目前的“清理”不应被误解为什么

| 代码／设置 | 真正作用 | 不代表 |
| --- | --- | --- |
| `STORAGE_LOCAL_CACHE=false` | 云文件处理后删除本地缓存副本 | 云端产物到期删除 |
| `ENABLE_KNOWLEDGE_FILE_RETENTION` | 影响知识库移除／删除等路径是否保留关联文件 | 所有聊天附件的定时过期策略 |
| session pool / task cleanup | 清理连接、运行任务等状态 | 清理聊天输出文件 |
| context compaction retention | 控制送入模型的上下文保留比例 | 删除原始聊天或产物 |
| `URL.revokeObjectURL` | 释放浏览器对象 URL | 删除数据库源内容，或令整个产物过期 |
| 删除聊天 | 删除聊天和消息、解除部分数据库关联 | 自动删除笔记、通用附件本体、外部终端目录 |

外部对象存储生命周期、服务器 cron、Jupyter 和 Terminals 策略可能额外删除文件，但不能从本地仓库判断线上是否存在这些配置。

## 建议：统一交付契约，分阶段建设

### 第一阶段：补齐用户可见的交付入口

不引入新的持久化文件库，优先复用已有消息、Notes 和 Files：

1. 每个聊天固定提供“产物”入口，手机也可见；没有内容时显示空状态，避免入口仅在识别成功后才出现。
2. 消息中的 HTML/SVG 提供预览与正确扩展名下载；普通代码块提供按语言下载。完整回复另提供“导出为 Markdown”，不要把每条说明自动列为正式产物。
3. 为明确的文档/网页交付展示卡片：文件名、格式、来源、预览、下载。把“来自消息，随聊天保存”和“仅存在于终端工作区”等状态显示清楚。
4. 对成功的 Notes 工具结果提供笔记链接和 `.md` 下载。只有实际检查到完整 HTML 时才提供“提取 HTML”操作；不按标题或模型口头描述判断文件类型，不自动覆盖旧笔记。
5. 将原生文件和终端引用纳入会话列表，保留来源信息。工作区文件与正式归档文件在可用性上要有区别。
6. 列表应有稳定来源键（例如 message_id + code block index + 内容摘要），保存分支来源；明确“当前分支”与“整个会话”视图，避免把不同网站混作同一网站的版本。

这一阶段解决“找不到、不能下载”的主要体验问题，但不能宣称已有独立版本库、跨设备浏览器文件同步或统一文件 TTL。历史消息继续作为其产物来源；需要精确保留当时内容的产物要进入第二阶段。

### 第二阶段：显式发布文件，建立可管理的产物记录

增加专用工具，例如 `publish_artifact`，用于“交付 HTML/Markdown/CSV/JSON/SVG 等文件”。工具接收内容或受控来源引用；user_id、chat_id、message_id 从已鉴权请求上下文取得，不能由模型任意指定。

成功条件是：内容校验通过、字节和元数据已经持久化、可通过有权限的下载路径取回。返回结构应包括 artifact_id、version_id、filename、mime_type、size、checksum、download_url、preview 支持情况和 expires_at；前端根据这个结构生成下载卡片，不依赖模型自己编造 Markdown 链接。

文件状态至少区分生成中、可下载、失败、已过期、已删除。保存成功不等于网页交互已经测试通过；需要分别展示保存/预览/运行检查结果。失败或只有一个沙箱路径时不能显示“交付完成”。

建议元数据包括：

```text
artifact_id / version_id
owner / tenant / external_chat_id / external_message_id
filename / media_type / byte_size / checksum
source_kind / source_reference
storage_key / status / created_at / expires_at
retention_policy / explicitly_saved_to_library
```

应有逻辑上的会话产物列表，但不要求给模型任意文件系统写权限，也不要求每个会话一台容器。纯 HTML/Markdown 交付可以直接保存字符串；真正需要执行 Python、构建 React 或生成 Office 文件时，才使用执行环境，然后把选定结果发布成产物快照。

如果实现独立持久化、版本、配额和清理，这些核心逻辑应放在项目独立模块／服务 `services/artifacts/`；Open WebUI BFF 只负责身份映射、来源授权和接口适配。核心不得导入 `open_webui.*`，也不与其表建立外键。

存储选择应保持清楚：第一阶段不复制原生文件；第二阶段原生文件可继续以受控引用显示，正式发布的产物才保存可管理的快照。快照使用独立对象前缀或独立目录及所有权元数据，复用既有存储基础设施；不要维护两份都能被任意修改的“同一源文件”，不要把产物混进 Memory 数据库。

可选 API 契约：

```text
GET    /api/custom/chats/{chat_id}/artifacts
POST   /api/custom/artifacts
GET    /api/custom/artifacts/{artifact_id}/versions
GET    /api/custom/artifacts/{artifact_id}/download
POST   /api/custom/artifacts/{artifact_id}/save-to-library
DELETE /api/custom/artifacts/{artifact_id}
```

接口对外返回明确 schema；存储路径不直接暴露成任意读取能力。HTML 预览使用隔离 iframe，下载返回 attachment，不能为了预览将生成脚本置于 WebUI 登录态同源页面执行。保留当前隔离边界，无需通过关闭安全设置解决交付体验。

### 第三阶段：让过期和删除成为可解释的产品行为

下面是建议默认策略，尚未实施，不能视为线上现状：

| 类别 | 建议保留规则 |
| --- | --- |
| 普通聊天的正式产物 | 默认随聊天保留，不静默 7/30 天删除；可由管理员设置明确配额和期限 |
| 用户明确加入资料库的产物 | 独立于原聊天保留；删除聊天时提示是否也删除这些保存项 |
| 执行环境的中间文件 | 可采用如 24 小时的可配置清理期限；与已发布产物分开 |
| 临时聊天 | 第一阶段仅本地下载，不暗中持久化；以后若支持服务端临时文件，需明确显示短期保留期限和保存动作 |
| 明确删除的正式产物 | 立即取消正常访问；如产品采用回收站，可保留如 7 天恢复期后清理字节，界面必须说明 |
| 原有 Notes、知识库及历史附件 | 不追溯套用新规则，不批量猜测归属，不自动清理 |

文件保留期与下载链接有效期应分开：短时签名链接到期可以重新签发，不表示产物被删除。下载鉴权应始终以当前用户权限为准；已过期的记录保留最小状态供 UI 解释，无权用户不能借此探测其他人的文件。

清理任务应支持预演、幂等重试、并发领取、删除失败重试、引用检查、下载/删除并发处理，以及清理报告。只处理归本系统明确拥有且已到期的对象；不扫描整个 uploads 目录按修改时间删除。记录容量、队列积压和错误，不记录正文。

## 最小集成面与验证要求

第一阶段主要新增 `src/lib/kakam/artifacts/`（types/api/store/service/components），按需新增 `backend/open_webui/kakam/artifacts/` 适配层。完整持久化阶段再增加 `services/artifacts/`，避免把服务端生命周期规则堆进组件或 BFF。

候选上游改动限于：聊天导航/控制面板挂载、CodeBlock/ResponseMessage 动作挂载、结构化工具结果渲染挂载、main.py 注册路由、utils/tools.py 注册项目工具。优先复用现有事件与文件 API，不为此大改中间件。真正实施时逐项记录到 `CUSTOMIZATIONS.md`。

验收至少覆盖：

- HTML 可交互预览，下载字节和保存内容一致；SVG/Markdown 的 MIME 与扩展名正确。
- 手机显示可发现的下载入口，刷新、切换分支、多产物和多模型输出不串记录。
- 只描述“已生成”、不完整代码块、失败的工具调用不成为可下载产物。
- Notes 中纯说明、纯 HTML、带围栏的 HTML、混合说明能被区分；旧笔记内容不被自动改写。
- 用户/租户/聊天隔离、路径与来源鉴权；不任意读取模型提供的服务器路径或外部地址。
- 重试和断流不重复发布；版本不可变；覆盖终端源文件不改变已发布快照。
- 临时聊天、过期、主动删除、多引用、清理失败、服务重启、对象缺失的行为清晰。
- 备份覆盖产物元数据和字节；能核对数量与 checksum，并有明确恢复路径。

## 本次核验和限制

执行了 9 个实际代码提取函数样例：HTML、Markdown、只有 Note ID、只有 sandbox 链接、未闭合 HTML、两个独立 HTML、HTML+CSS+JS、SVG、推理中的 HTML，全部符合上述描述。

执行了 7 个实际 terminal context helper 样例：普通终端、编排器默认共享、显式 per-chat、临时聊天、缺少 chat_id、关闭聊天 context、per-automation，全部通过。测试隔离了导入，没有启动数据库、浏览器执行环境或终端容器。

这不是线上端到端验证，也没有验证所有文件类型。当前 Compose 只声明 WebUI 和 Memory 相关服务，没有声明 Jupyter/Terminal；管理员仍可能配置仓库外的外部服务。尚需线上只读确认的项目：部署提交、用户启用的工具、Pyodide 持久化开关、Storage provider/外部生命周期、终端连接类型/版本/context、具体 LLVM 笔记内容及 write_note 结果。检查这些项目不需要输出任何密钥。

## 源码证据索引

路径相对仓库根，行号是本次 HEAD 附近的定位参考。

| 证据 | 位置 |
| --- | --- |
| 消息提取、当前分支、产物前端组装 | [Chat.svelte](../../src/lib/components/chat/Chat.svelte)，`getContents`，约 1932 行 |
| 代码块识别 | [utils/index.ts](../../src/lib/utils/index.ts)，`getCodeBlockContents`，约 2202 行 |
| 手机自动打开条件 | [ContentRenderer.svelte](../../src/lib/components/chat/Messages/ContentRenderer.svelte)，约 135 行 |
| Blob 下载及文件后缀 | [Artifacts.svelte](../../src/lib/components/chat/Artifacts.svelte)，约 82 行 |
| Notes 工具契约 | [builtin.py](../../backend/open_webui/tools/builtin.py)，`write_note`，约 1284 行 |
| Notes 保存结构、缺少过期字段 | [models/notes.py](../../backend/open_webui/models/notes.py)，`Note` |
| Notes 编辑、导出 | [NoteEditor.svelte](../../src/lib/components/notes/NoteEditor.svelte)，约 172、774 行；[NoteMenu.svelte](../../src/lib/components/notes/Notes/NoteMenu.svelte) |
| 原生文件结构、聊天关联 | [models/files.py](../../backend/open_webui/models/files.py)，`File`；[models/chats.py](../../backend/open_webui/models/chats.py)，`ChatFile`，约 217 行 |
| 聊天删除不删除文件本体 | [routers/chats.py](../../backend/open_webui/routers/chats.py)，约 1568 行；[models/chats.py](../../backend/open_webui/models/chats.py)，约 2481 行 |
| 文件名、内容下载及显式删除 | [routers/files.py](../../backend/open_webui/routers/files.py)，约 355、782、1001 行 |
| 存储适配与 uploads | [storage/provider.py](../../backend/open_webui/storage/provider.py)，约 58 行；[config.py](../../backend/open_webui/config.py)，约 149、173 行 |
| 文件/嵌入事件持久化 | [socket/main.py](../../backend/open_webui/socket/main.py)，约 1057 行 |
| MCP 与终端文件结果适配 | [utils/middleware.py](../../backend/open_webui/utils/middleware.py)，约 260、1124 行 |
| Pyodide 默认开关与工厂 | [env.py](../../backend/open_webui/env.py)，约 1190 行；[createPyodideWorker.ts](../../src/lib/pyodide/createPyodideWorker.ts) |
| 浏览器持久化与文件下载 | [pyodide.worker.ts](../../src/lib/workers/pyodide.worker.ts)，约 46 行；[PyodideFileNav.svelte](../../src/lib/components/chat/PyodideFileNav.svelte) |
| 共享 Python worker 和执行返回 | [routes/+layout.svelte](../../src/routes/+layout.svelte)，约 287 行；[builtin.py](../../backend/open_webui/tools/builtin.py)，`execute_code` |
| Jupyter kernel 生命周期 | [code_interpreter.py](../../backend/open_webui/utils/code_interpreter.py)，约 25、60、102 行 |
| 终端的 per-chat 条件 | [utils/terminals.py](../../backend/open_webui/utils/terminals.py)，约 32、57 行 |
| 终端文件按路径下载 | [terminal/index.ts](../../src/lib/apis/terminal/index.ts)，约 276 行；[TerminalOutputFile.svelte](../../src/lib/components/chat/Messages/TerminalOutputFile.svelte) |
