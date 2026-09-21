# Memory Manager v1（default policy v2）

## 运行边界

WebUI Chat → authenticated BFF → Memory Manager → repository/providers → PostgreSQL + pgvector。
Manager 和 Server 首版部署在同一个 memory-api 进程内，但不导入 `open_webui`。
Manager 的 registry/策略/存储/模型适配分别独立，WebUI 不实现领域决策。

- `policy.py`：registry、manifest、`run(task, tools) -> decision`。当前只有 default。
  召回只提供 owner-scoped search/read 能力；策略返回 ID，Manager 再验证权限、排除、有效性和预算。
  压缩策略提出触发与保留建议，Manager 强制执行用户开关、最小保留量、工具边界、输入输出限制。
  这是未来 Agent 策略的扩展点，不是已实现的自主 Agent 运行时。
- `manager.py`：应用编排和版本化 API；`manager_repository.py`：Session/建议/集合/审计持久化。
- `contracts.py`：结构化入参；WebUI `types.ts` 的 ManagerView 是视图协议，不暴露 owner/vector/密钥。
- 两个模型工具 `kakam_recall` / `kakam_propose_memory` 是应用内 skill 可调用的能力。
  没有自动安装个人 Codex skill；任何工具都不能提交“用户已批准”标记来绕过 UI 审批。

## API（浏览器不直连服务）

浏览器路径以 `/api/custom/memory/manager` 开头，由 BFF 检查登录、Memory 权限和聊天归属。
内部路径以 `/v1/manager` 开头，要求 service bearer key + `X-Memory-Tenant` / `X-Memory-User`。
租户来自部署配置、用户来自登录态，浏览器提交的同名 header 不会被转发。

| 内部接口 | 用途 |
| --- | --- |
| GET `/status`、POST `/probe` | 数据库/模型配置状态；实际 embedding 调用检查（不是正式模型质量评估） |
| GET / PUT `/sessions/{id}` | inspect_context / set_session_scope；视图含集合、记忆、摘要、建议、最近操作 |
| POST `/prepare-turn` | 同步 recall，返回受预算约束的选中记忆、遗漏优先项、cache_hit、operation_id |
| POST `/compact-context` | 校验源快照、计算安全边界、调用摘要模型、返回 cut/summary/state |
| POST `/sessions/{id}/proposals` | memory_action 的候选写入；没有长期记忆副作用 |
| POST `/proposals/{id}/decision` | UI 的独立确认/拒绝；行锁保证重复点击幂等 |
| PATCH `/memories/{id}` | 版本校验的正文/分类/标签编辑；重新 embedding，保留旧版本 |
| POST `/collections`、PUT `/memories/{id}/collection` | 父子集合与多对多成员关系 |
| POST `/sessions/{id}/handoff` | generate_handoff 的输入准备和审计；沿用 WebUI streaming 模型适配完成生成 |

旧 `/v1/memories` 手动 CRUD 保留。`/v1/events/turn-completed` 返回 queued=false，不再抽取。
complete_turn 目前只在 BFF 保存无正文的统计；没有为无副作用事件新增远程调用。
操作 `prepared` 表示 Manager 已选好候选，不代表 WebUI 已注入或模型最终使用；实际注入量看 Context 快照。

## 存储与安全

迁移 002 将旧 owner 映射成 `default:<opaque-user-id>`；所有查询使用完整 owner 命名空间。
租户名不允许冒号，opaque user id 可以包含冒号。生成列显式显示 tenant_id/external_user_id。
当前是应用层硬过滤 + 独立数据库角色，不声称已部署 PostgreSQL RLS。

记忆条目核心字段稳定；扩展包括 version/tags/metadata JSONB、memory_version、
memory_session、memory_proposal、memory_operation、memory_collection、memory_membership。
集合形成单父层级；记忆可进入多个集合，无 Open WebUI 表外键。API 不允许跨用户建立关系。
后续稳定字段通过有序 migration 增加，实验字段先放 metadata，不随意改变旧字段语义。

默认长期记忆创建后 30 天过期，召回窗口 7–30 天；优先记忆可越过召回时间窗口但不能越过有效期。
摘要只服务当前 Session；不会升级为长期知识。摘要和原始正文属于用户私有数据，不写入普通日志。
删除长期条目清除正文、向量、历史版本、来源与已应用建议；保留去重 tombstone 到条目原有效期。
不删除原聊天，亦不承诺从原聊天或用户再次确认的新文本中永远不可恢复该事实。
Session/操作记录最多保留 30 天，建议最多保留一天；worker 必须保持运行执行清理。

## 压缩与边界

默认触发额度 12000 UTF-8 字节上界估算，保留最近至少 8 条消息（按完整 user turn 切分）。
它不是精确 tokenizer，也不代表供应商 context window。管理员应按模型留出 System、工具与输出额度。
System/developer 不发送到摘要模型，不裁剪；当前 Prompt 不裁剪；跨边界未完成 tool call 不切割。
普通文本和仅含文本/推理的 OR 输出可处理（隐藏推理不发送）；图片和复杂 OR 工具输出暂时跳过。
源文本上限 160KB，摘要上限 6000 字符。源前缀哈希不匹配时不用旧摘要，避免编辑后串用。
未配置或超时等错误保留原请求并公开状态；大于模型硬窗口的请求仍可能被供应商拒绝，不会偷偷丢消息。
旧 checkpoint 能复用，但关闭自动压缩不会还原已压缩请求；改写源消息会使 checkpoint 失效。
尚不实现多标签页一致性、分支管理、复杂 Agent 计划循环或自动语义知识图谱。

当前分类由用户选 kind 和 tags，default 只做安全筛选/检索/预算/精确去重；高级语义去重、
冲突推理、自动实体抽取与归类留给后续策略，不声称已实现。

## 已有 Compose 部署升级

1. 备份当前 WebUI 与 Memory 数据卷/数据库以及安全保存的 `.env.kakam`；保留原密钥不变。
2. 保留 `KAKAM_MEMORY_TENANT=default`，否则旧用户记录会处在另一个命名空间。
3. 在 `.env.kakam` 添加实际配置（不要直接把占位符部署）：

```dotenv
KAKAM_MEMORY_SERVICE_URL=http://memory-api:8081
KAKAM_MEMORY_TENANT=default
MEMORY_CONTEXT_BASE_URL=https://your-model-endpoint.example/v1
MEMORY_CONTEXT_MODEL=your-chat-model
MEMORY_CONTEXT_API_KEY=your-provider-key
```

现有 MEMORY_EMBEDDING_* 仍必须有效。WebUI 管理页的聊天 API Key 不会自动传给 Memory。
独立远端 Memory Server 使用可达的私网/HTTPS 地址，配置匹配的 service key，切勿暴露数据库端口。

4. 在仓库根目录执行：

```sh
docker compose --env-file .env.kakam -f compose.kakam.yaml config --quiet
docker compose --env-file .env.kakam -f compose.kakam.yaml up -d --build
docker compose --env-file .env.kakam -f compose.kakam.yaml ps
```

启动时串行执行 migration；不要多个不同版本服务同时写同一数据库。旧 pending 抽取任务会停止，
保留已存 Memory，worker 后续只做清理。这是有意的写入授权规则变更。

5. 头像 → Memory Policy → 测试真实服务连接；手动保存测试记忆；新建已保存聊天，确认 Context
显示实际召回；在 Session Memory 排除后再发一轮，检查不再注入。用第二个用户验证不可见。
6. 让模型“请记住…”（模型必须支持工具调用）→ Context → 刷新 → 核对原文 → 确认保存。
7. 配置摘要模型后进行长文本会话，查看 compaction=compacted 和独立摘要；检查原聊天仍完整。

回滚聊天集成可设 `KAKAM_MEMORY_ENABLED=false`，会恢复原生路径。
数据库 002 不支持直接给旧服务二进制降级使用：owner 已改命名空间；完整回滚需恢复升级前备份。
不要仅切回旧 image 然后让旧 worker 写入迁移后的数据库。

## 验证

本地已执行独立 PostgreSQL/pgvector SQL 与 HTTP 集成测试，模型服务使用可控 HTTP fixture；
这不能替代真实远端供应商 smoke test。测试库必须是一次性数据库：

```sh
KAKAM_TEST_DATABASE_URL=postgresql://.../disposable_test_db services/memory/.venv/bin/pytest -q services/memory/tests
```

测试覆盖身份隔离、源证据、确认幂等、预算/排除、缓存失效、编辑版本、源快照失效、工具边界、
HTTP 传输和 API 重启后持久化。前端还有 Memory/Hand-off Vitest，以及 desktop/mobile 组件验收。
