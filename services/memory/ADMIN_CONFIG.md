# 管理员 Memory 服务配置

入口：设置 → 管理员 → AI → **Memory 服务**。这不是个人 Memory Policy 页面。
配置在当前租户内共享，记忆内容仍按租户及用户隔离，管理员配置页不提供读取他人记忆的权限。

## 可配置内容

- Context：启用、Base URL、API Key、模型、Chat Completions / Responses 协议、1–60 秒超时。
- Embedding：启用、Base URL、API Key、模型、维度、1–60 秒超时；使用 `/embeddings`。
- 两组配置独立保存，展示“环境变量 / 数据库配置”来源，可测试未保存草稿或恢复环境变量。
- 不再提供自动抽取模型配置及抽取调用。长期记忆仍需用户手动保存或确认模型建议。

页面顶部通过 Context / Embedding 按钮切换两种模型，切换保留未保存草稿。
“检测连接 / 获取模型”使用当前草稿地址和密钥调用供应商 `GET /models`，无需先选择模型。
它不执行推理、不写数据库、不自动选择模型，列表不代表摘要或 embedding 能力。
选择后需点击“测试模型调用”验证实际用途（该测试可能有模型调用费用），再保存配置。
不支持列表接口（404/405）时仍可手动填写模型 ID；其他失败显示脱敏状态码或网络提示。
发现请求最多 20 秒，响应最多 1 MiB，只返回最多 500 个合法、去重的模型 ID；不跟随重定向，
不发送聊天或记忆内容，不回传供应商附加字段，分页/数量截断会在 UI 提示。
接口契约参照 [OpenAI Models API](https://developers.openai.com/api/reference/ruby/resources/models)。

新增 BFF `GET /api/custom/memory/admin/config/ownership` 返回是否由 Manager 接管（仅管理员）。
列表探测经 `POST /api/custom/memory/admin/config/{context|embedding}/models` 转发到
内部 `POST /v1/admin/config/{context|embedding}/models`，沿用管理员鉴权、签名及禁止缓存。
启用 KaKam 时，原“管理员 → 界面 → 上下文压缩”区域标注接管并隐藏原生控件；禁用后恢复原控件。
服务离线不会把接管状态错误地切回原生压缩，状态查询失败时显示重试，不修改原配置。

“记忆建议”不是隐藏的自动抽取任务：用户明确要求记住时，由当前聊天模型调用
`kakam_propose_memory`（需要模型支持且使用工具调用），仍需用户确认；手动录入直接校验保存。

Base URL 是 **Memory Server 调用模型供应商**的地址，例如 `https://provider.example/v1`，
不是 WebUI 地址，也不是 Memory Server 的服务地址；不要填写完整 `/chat/completions` 或 `/responses`。
Chat Completions 发送 `messages`、`max_completion_tokens`；Responses 发送 `instructions`、`input`、
`max_output_tokens`，读取 `output` 中的 assistant `output_text`，不读取隐藏 reasoning。
两者都发送 `store:false`、非流式请求；截断、拒绝或无有效文本不会覆盖 Session 摘要。
Embedding 发送 `encoding_format:float` 和 `dimensions`，严格校验返回维度及有限非零向量。
供应商必须支持相应协议和参数；连接测试会验证响应。参考 [OpenAI 协议迁移说明](https://developers.openai.com/api/docs/guides/migrate-to-responses)。

## 安全保存与首次升级

1. 备份当前数据库和 `.env.kakam`，不要覆盖已有密码、WEBUI_SECRET_KEY 或服务鉴权密钥。
2. 在部署端运行一次 `openssl rand -hex 32`，将结果填入 `.env.kakam` 的
   `MEMORY_CONFIG_ENCRYPTION_KEY=`。把同一值保存到密码管理器，保持 `.env.kakam` 权限 `600`。
   不要将实际值提交 Git、发送聊天或记入日志。此密钥丢失后无法解密数据库覆盖配置。
3. 更新代码后运行：

   ```sh
   docker compose --env-file .env.kakam -f compose.kakam.yaml config --quiet
   docker compose --env-file .env.kakam -f compose.kakam.yaml up -d --build
   docker compose --env-file .env.kakam -f compose.kakam.yaml ps
   ```

4. 管理员进入 Memory 服务，分别配置并测试 Context 和 Embedding，保存后重新读取确认来源为数据库。
   测试只发送合成文本、不保存配置，但会产生少量模型调用费用。
5. 在普通用户聊天中测试记忆保存、召回、压缩和故障降级。生产供应商仍需部署后验证。

迁移 `003_provider_config.sql` 增加独立配置表及不含密钥的审计表，不修改或删除记忆。
数据库中的整个配置 payload 使用 AES-256-GCM 加密，以租户和配置类型作为认证附加数据。
DB 和加密密钥必须配套备份恢复；所有 Memory API 实例应使用相同主密钥。缺少主密钥时，
原有环境配置仍正常工作，页面只读且可测试；已有加密覆盖但主密钥丢失或错误时明确报错，
不会静默换供应商。暂不提供在线主密钥轮换。

## 生效与密钥语义

数据库整组覆盖环境变量。每个请求开始读取配置快照，保存后新请求使用新配置；正在进行的请求
沿用旧配置。无需重建容器。配置版本参与缓存键；多进程从同一数据库读取，不依赖单进程热变量。
恢复环境变量清除该组覆盖（不删除记忆），恢复服务**启动时**读取的环境配置。
修改 `.env.kakam` 本身仍需重新创建对应容器。部署级 DB 凭据、服务鉴权及加密主密钥不允许在线修改。

API Key 只返回是否已配置，明文不会回传。页面明确选择“保留 / 替换 / 清除”，空输入不代表删除。
保存后密码输入框清空，不存入 localStorage；修改供应商 origin 时必须显式替换或清除原密钥，
避免误向新供应商发送保留密钥。用户应只配置可信供应商：请求从服务器发起，能访问服务器可达网络；
不要将管理员权限授予不可信人员。仅内部网络开放 Memory API，公网仅通过 HTTPS WebUI BFF。

WebUI 使用 `get_admin_user` 鉴权；BFF 对内部管理请求的方法、路径、身份、时间和内容摘要签名。
普通用户的服务调用不能直接访问管理接口。服务返回校验错误和供应商测试错误时不回显输入或响应原文。
测试显示 401/403、404、429、网络/TLS、超时及格式/维度错误；成功仅表示合成请求在该时刻成功。

## 向量换代与边界

更换 embedding 地址、模型或维度会创建不同向量空间。有有效记忆时，服务器要求显式确认影响，
包括恢复环境变量的操作。旧记忆不会删除，也不会与新空间混算，但不会被新空间语义召回。
本版**没有自动批量回填**：可恢复旧配置，或用户逐条编辑并保存生成新向量；跨用户批量迁移应另行实现。
Session 中显式“优先使用”的条目仍可按 ID 加入上下文，它不是向量检索。

模型启用开关只控制相应模型调用，不会删除数据。禁用 embedding 后普通语义召回/新向量写入不可用，
但仍可浏览、删除记录，显式按 ID 选择的记忆不依赖向量。禁用 Context 不再生成新摘要，已有摘要仍可复用。
浏览器召回还受 WebUI `KAKAM_MEMORY_TIMEOUT_MS` 预算限制，不等于这里的供应商超时。
恢复旧服务版本前，应恢复对应旧版本数据库备份；不要让旧 worker 在已升级库上重新执行抽取。

## 本次验证（2026-09-21）

- Memory 后端 62 项测试通过，包含独立 PostgreSQL、签名管理请求的真实 HTTP 链路、模型列表大小限制与错误脱敏。
- Memory / handoff 前端 35 项测试通过，生产构建通过；全仓库类型检查仍有既有错误，本次涉及的自定义管理组件与 Interface 未报告错误。
- 本地模拟服务下验证了手机与桌面布局、空模型名探测、模型选择、切换配置保留草稿、供应商不支持列表，以及启用/关闭 KaKam 的接管展示。
- 上述验证未调用生产模型供应商；部署后需分别执行“检测连接 / 获取模型”和“测试模型调用”。
