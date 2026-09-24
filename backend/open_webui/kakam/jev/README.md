# Jev / defer to

Jev 使用 TypeSafe 的结构化决策接口，不注册成 OpenAI 聊天模型。前端位于
`src/lib/kakam/jev/`，WebUI 适配器位于本目录。`client.py`、`schemas.py`、
`prompts.py`、`workflow.py` 不依赖 Open WebUI 内部模块；WebUI 身份、配置和
LLM 调度分别通过 `router.py`、`config.py`、`llm.py` 适配。

## 使用

1. 管理员进入设置 → AI → **Jev 模型管理**，填写 API Key 和 Base URL。
   默认 `https://api.typesafe.ai/v1`；也接受官方根地址或完整 `/v1/systemone`
   地址，并规范为 Base URL。
2. **测试连接**对当前表单执行一次很小的 Noul 判断，可能计入供应商用量。
   测试不保存配置；点击 **保存配置** 后对所有 WebUI 实例的后续请求生效。
3. 点击侧边栏 **defer to**，选择现有的服务端 LLM 作为润色模型，输入问题。
   润色模型沿用原生模型访问权限。浏览器直连、Arena、Function/Pipe 模型不列入
   此选择器；本功能不执行原生聊天的附件、搜索、Memory、工具或后台任务。
4. 流程依次展示 LLM 处理中、Jev 判断中、LLM 整理结果、Done。
   上下文不足时先澄清。可以继续提问、停止，或开始新对话。

会话只保留在当前页面实例，不写入原生聊天历史或 localStorage；刷新或离开页面
会结束本次会话。后续如需持久历史，应通过独立、带用户隔离的存储契约扩展。

## 结果与 skill

官方 MIT skill 固定在 `skills/typesafe-ai/SKILL.md`，保留原文和许可证：

- 上游：<https://github.com/typesafe-ai/skills>
- 版本：`65a39f393687675ce170e6094757de20370365b9`
- 文档核对日期：2026-09-24
- API：<https://docs.typesafe.ai/api>
- Skill：<https://docs.typesafe.ai/agent-skill>
- Score 语义：<https://docs.typesafe.ai/primitives/score>

每次输入编排都加载该 skill，加上 `prompts.py` 中集中维护的运行时 JSON 契约。
不在运行中联网安装 skill，也不自动修改用户 Workspace 中的其他 skills。
润色模型将用户输入和相关上下文完整转为英文，保留选项、数字、否定、条件与
不确定性，再生成 state/questions 和用户语言的显示标签。官方目前说明英文是
主要训练语言、准确性最好，而非完全不接受中文。

所有请求经 Pydantic 校验；格式错误只修正一次，仍失败则不调用 Jev。
无上下文、缺少必要选项或纯开放生成任务会先请求澄清。

- **Choice**：展示 Jev 选中的选项及完整概率分布。
- **Score**：按真实的 `0..N-1` 量表展示概率加权位置、每级描述及分布，不当作百分制。
- **Noul**：展示 P(yes) 和其补概率；0.5 表示无法偏向是或否，不是“中等强度”。

卡片数值始终直接来自 Jev 的类型化响应，不接受润色模型改写。Jev 不提供推理
过程；第二次 LLM 调用只进行结果表述，不能声称是 Jev 的推理解释。润色失败时
保留卡片并提示降级。界面可展开检查实际提交的英文内容。

## 配置和内部复用

配置存储为现有 WebUI Config 中的一行 `kakam.jev.connection`，URL 和 key 原子
更新。遵循现有 Config 持久化开关，不新增表、迁移或生产依赖。未保存配置时可用：

```text
KAKAM_JEV_BASE_URL=https://api.typesafe.ai/v1
KAKAM_JEV_API_KEY=<server-side secret>
```

管理页只返回 `base_url`、`has_api_key`、`model`。空白 key 保留旧值；清除需显式
勾选；更换地址时必须重新提供 key，避免旧凭据意外发送到新服务。测试 key 不写入
代码、skill、示例配置、日志或前端状态。存储沿用原生配置的保护方式，未额外加密；
现有管理员全量配置导出仍具备读取这些服务器配置的权限。

未来可信后端调度器可以复用同一个工厂，每次读取最新配置，无需将密钥传给浏览器：

```python
from open_webui.kakam.jev.config import get_jev_client
from open_webui.kakam.jev.schemas import EvaluationRequest

client = await get_jev_client()
answer = await client.evaluate(
    EvaluationRequest(
        state='A customer explicitly asks for a refund.',
        questions={'refund': {'type': 'noul', 'instructions': 'Does the customer request a refund?'}},
    )
)
```

## BFF 契约

| 方法与路径（前缀 `/api/custom/jev`） | 权限                         | 用途                                                               |
| ------------------------------------ | ---------------------------- | ------------------------------------------------------------------ |
| `GET /config`                        | admin                        | 脱敏配置                                                           |
| `PUT /config`                        | admin                        | 保存 `base_url`、可选 `api_key` / `clear_api_key`                  |
| `POST /test`                         | admin                        | 使用当前表单执行小型真实判断，不保存                               |
| `GET /status`                        | verified user                | 使用 `GET /v1/models` 检查连通、鉴权和模型可用性；不回传地址或凭据 |
| `GET /prompt-models`                 | verified user                | 原生权限过滤后的服务端润色模型                                     |
| `POST /turn`                         | verified user + model access | `{model_id, messages}` → SSE                                       |
| `POST /evaluate`                     | verified user                | 直接进行类型化判断，供内部 API 客户端复用                          |

`/turn` 的 SSE data 是 `type` 区分的 JSON：`stage`、`result`、`summary`、
`clarification`、`warning`、`error`。只有明确收到 `stage=done` 才视为完成；
错误、断流、取消不会假报完成。`result` 含 `evaluation`、`display`、`response`，
在结果润色之前就发送。心跳间隔 10 秒，禁用代理缓冲；断连会取消正在等待的任务，
但已发送到供应商的请求可能已经被处理。

本应用限制每次最多 12 个问题、40 条历史消息、24,000 字符对话、96 KB 判断请求。
超限直接报错，不静默截断用户含义。Choice 支持 2–255 个选项，Score 为 2–10 级。
LLM 单次超时 90 秒，Jev 单次超时 35 秒，整个流程 240 秒；仅 429/529 进行最多
两次指数退避重试，不自动重试推理超时。禁止重定向，限制响应大小，供应商错误
只返回清理过的消息。前端每 60 秒在可见页面刷新连接状态。

## 验证

```sh
PYTHONPATH=backend python -m pytest backend/open_webui/kakam/jev/tests -q
npm run test:frontend -- --run src/lib/kakam/jev
ruff check backend/open_webui/kakam/jev
```

覆盖三个原语、概率边界、量表范围、ID 与标签对应、URL 规范化、权限、凭据更新、
不跟随重定向、超时/限流、修正次数、澄清、润色失败保留结果、流式 UTF-8 分片、
断流和取消。官方 API 的模型列表与三个原语已使用临时测试 key 验证。
浏览器交互验证使用真实组件和 BFF、模拟 LLM/供应商响应；不代表真实 LLM 的翻译
质量已完成线上评估。

本次验证环境为 Python 3.12 和 Node 22.14：73 项后端测试、14 项前端测试通过，
新增模块的 Ruff / ESLint 检查通过；Vite 生产构建通过。全量 `npm run check`
报告 7,772 个错误、203 个警告，与排除本次改动的源代码基线逐项比对一致。
`npm run build` 的现有 Pyodide 下载预处理因 PyPI 网络连接失败而受阻，随后使用
现有静态资源单独完成 `vite build`；未修改该预处理脚本或提交其生成文件。
