# 消息与文件管理中心

用户入口：侧栏 / 用户菜单「消息与文件」及设置 → Data →「消息与文件」。
会话菜单提供「查看对话产物」，固定地址 `/library?chat_id=<id>`。
原来的 `notes` 导航偏好键仍保留，指向新的 `/library` 页面；旧笔记编辑、
分享 URL、置顶笔记和原 `/notes` 工作区不变。长期记忆 Memory 不参与本模块。

## 已实现

- 首页是按对话组织的 Gallery：对话名称作为标题，侧边栏分组作为彩色标签，
  显示更新时间与归档标记。支持名称搜索、服务端分组筛选和分页；无分组显示「未分组」。
  管理员进入此中心也只能列出自己的数据，分组名称同样按本人权限读取。
- 点击卡片进入产物合集，不再显示聊天正文、消息分支、消息 ID 或聊天导出 / 删除入口。
  「生成产物」优先展示，上传的参考附件和无法确认来源的关联文件放在次级分区。
  普通聊天文本和用户输入的代码不会被当作产物；查看聊天使用「打开原对话」。
- 同一原生文件在文件表、消息附件和 Markdown 中的引用合并显示。保留原始代码和
  文件字节，支持产物名称搜索、预览、下载、空状态、加载失败重试和窄屏 / 深色样式。
  旧聊天 JSON 与新的 `chat_message` 均支持，恢复代码产物时读取各消息分支。
- 「全部文件」和「笔记」保留下载、按 30 / 90 / 365 天未修改筛选和明确确认的清理操作。
- 识别消息与笔记中的 HTML / SVG / Markdown / JSON / CSV 等代码块，按正确扩展名
  下载原始代码。HTML / SVG 在不具有站点同源权限的 iframe 中按需预览；外部资源受 CSP
  限制。这里不会把网站说明文字冒充为 HTML，也不会改写多文件项目的 CSS / JS 引用。
- 文件列表包含原生模型图像和用户上传附件；会话详情还展示消息 / 结构化输出中的
  文件引用。已存储的 HTML / SVG 文件可以预览；普通文本预览限 2 MiB。
- 本人文件原始字节统计、未知大小文件数、选择本页 / 单项、明确列出目标的删除确认。
  部分失败逐项报告，不会把失败当成成功，也不重试已成功删除的项。
- 原聊天代码工具栏增加下载按钮，下载当前显示 / 编辑的代码。
- 原生 function calling 新增 `publish_artifact(filename, content)` 工具：保存
  HTML、Markdown、SVG、CSV、JSON、文本和源码为原生 File，关联当前会话 / 消息，
  发出附件事件，并返回真实下载 URL。仅在模型文件能力、工具类别及用户上传权限允许时
  注入；执行时再次验证权限与会话所有权。每次发布创建独立文件，最大 2 MiB UTF-8。
  工具不接收模型指定的用户 ID、会话 ID 或服务器路径，不读取任意服务器文件。

## 存储与生命周期

这是一个**聚合管理层**，不复制已有内容，也没有新数据库或迁移：

| 内容 | 权威存储 | 获取方式 |
| --- | --- | --- |
| 会话 / 消息 | 原生 chat、chat_message（兼容旧 chat JSON） | 只用于归集产物；正文在原对话中查看 |
| 对话分组 | 原生 chat.folder_id + folder | 本人分组标签 / 筛选，不另建分类存储 |
| 上传附件、模型图像、发布产物 | 原生 file + Storage provider | 已鉴权的原生文件下载 API |
| 会话来源 | chat_file；补充读取 file.meta.data 的 chat_id / message_id | 本人会话链接 |
| 笔记 | 原生 note.data.content.md | 本中心下载，原编辑器继续编辑 |
| 消息或笔记中的代码块 | 原记录中的文本 | 下载时生成 Blob，不重复占用服务器文件空间 |

每个会话拥有固定的**逻辑入口**，没有新增物理输出目录。新发布文件的来源元数据与
文件一同持久保存；下载 URL 需要原生鉴权，不是公开分享链接。原生图片生成路径本来
就使用 File 存储，因此自动纳入。用户授权访问但不拥有的附件可从消息中的引用下载，
不会计入本人文件存储或批量删除列表。

默认**不自动过期**，沿用现有持久保存行为。时间筛选只是清理辅助，未引入 TTL
任务或后台删除。删除会话保留文件和笔记；删除文件调用上游清理 API，影响所有引用，
包括知识库、分享与其他会话。界面在删除前展示这些影响。没有回收站。
清理不会操作备份、向量索引以外的缓存或外部终端磁盘。

存储统计是元数据记录的原始文件字节，不是服务器磁盘占用，也不包含数据库、索引、
备份、云存储计费副本。旧文件大小缺失单独计数；未知来源不等于孤立文件。
旧笔记缺少会话来源，无法可靠自动回填。外部 URL、Open Terminal / Pyodide 的临时
资源保留引用并指引回原会话，不承诺这些引用永久可用。

## 边界与 API

前端：`src/lib/kakam/library/{api,types,store,service}.ts` 与 `components/`。
后端：`backend/open_webui/kakam/library/`，作为 native 数据的只读 BFF 与发布适配器。
领域级跨产品资产库、版本链、自动保留策略不在这个聚合模块中实现。

认证 API（均 `Cache-Control: private, no-store`）：

```
GET /api/custom/library/summary
GET /api/custom/library/entries?kind=chat|file|note&q=&offset=0&limit=30&before=<epoch>&chat_id=<id>&group_id=<id>&ungrouped=false
GET /api/custom/library/groups
GET /api/custom/library/chats/{id}
GET /api/custom/library/notes/{id}
```

列表 limit 上限 100，q 上限 200 字符；用户范围来自认证，不能由参数覆盖。
Notes 开关与权限沿用上游。下载和删除复用原生 `/api/v1/files|chats|notes` API，
保留现有权限、存储和索引清理行为。`group_id` / `ungrouped` 仅筛选对话，互斥；
筛选在服务端计数与分页前执行。分组列表仅包含本人有对话的本人分组，已删除或不属于
本人的分组引用按未分组显示，不泄露分组名称。Entry / ChatDetail 新增可空 `group` 字段，
原 API 字段保留兼容。Gallery 列表不读取消息正文或逐卡片请求完整聊天。

详情仍为单会话全量读取以恢复代码产物，浏览器按 36 项分批展示，文件按 30 项分页加载。
很大的单会话仍可能有读取内存压力。Gallery 包含没有产物的对话，详情会给出明确空状态；
不会为了预先统计产物而批量扫描所有聊天。上传和生成来源无法确认时显示为「关联文件」。
文本 / 图像预览只对已知不超过 2 MiB 的支持格式启用；HTML / SVG 始终隔离预览。

## 验证与部署

```
services/memory/.venv/bin/pytest -q --confcutdir=backend/open_webui/kakam/library/tests --rootdir=backend/open_webui/kakam/library/tests backend/open_webui/kakam/library/tests
npx vitest run src/lib/kakam/library
services/memory/.venv/bin/ruff check backend/open_webui/kakam/library
npx eslint src/lib/kakam/library 'src/routes/(app)/library/+page.svelte'
npm run check
npm run build
```

后端测试在独立 SQLite 内验证查询及用户隔离，用上游等价的最小 ORM 表替代启动整套
应用；HTTP 测试通过真实 FastAPI 路由和替代认证依赖验证范围与错误。发布测试替代
Storage / socket 边界。前端测试覆盖导出原文、扩展名、附件解析、请求竞争、部分清理
失败和下载 Blob 的文件名 / 生命周期。

本地真实 Svelte 组件以虚构 API 数据检查 Gallery、分组筛选、搜索空状态、产物预览、
上传附件分区和文件 / 笔记入口，以及 390px 手机宽度、设置宽度和深色模式；没有读取或清理线上数据。
后端测试覆盖分组过滤先于分页、跨用户 / 已删除分组隔离，前端测试覆盖产物去重、上传与
生成来源区分、普通聊天排除、部分加载失败及取消后的请求隔离。内置浏览器的下载事件捕获未成功，
下载函数通过 Blob / 文件名测试验证；仍需在部署后的 Safari / Chrome 验证实际落盘。
2026-09-25 Gallery 改版验证：12 项后端测试、20 项前端测试通过；模块 ESLint / Ruff
通过，Vite 生产构建完成。全仓类型检查仍有 7,769 条既有错误、203 条警告，
本模块无类型错误或警告。未部署到线上，仍需用真实账号数据做上线验收。

部署需要同时重建 WebUI 前端和后端；本地修改不会直接改变 chat.kakamlab.com。
无需数据迁移，也未添加生产依赖。回退代码即可恢复原导航与工具；新发布的文件
仍是普通原生 File，不会因回退丢失。
