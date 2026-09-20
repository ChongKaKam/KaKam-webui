# Chat Effort

The composer shows `none`, `low`, `medium`, `high`, `extra high`. Unsupported
choices are disabled, not silently sent. A supported model defaults to `high`;
if metadata excludes high, the strongest declared level is used. Unknown models
offer only `none` and omit the parameter. Switching models restores that
model's selection from the existing per-chat params (`kakam_effort`). The capsule opens a cascading model/effort menu. Compare mode configures each
model in its own submenu; each request retains that model's valid default or
saved selection. The capsule summarizes the first model and the additional model
count. On phones, a back action returns from effort to the model list.

Detection is conservative: exact API IDs/base IDs and dated snapshots of
`gpt-6-astra`, `gpt-5.5`, `gpt-5.2`, and `gpt-5` are recognized. Display names,
unknown aliases, DeepSeek, Claude and MiniMax names alone do not establish support
for the OpenAI-compatible `reasoning_effort` parameter. Native provider thinking
APIs are not automatically translated.

Use a model's existing JSON import/update support to declare capability in
`meta.reasoning_effort` (exposed to the frontend as `model.info.meta`):

```json
{
  "meta": {
    "reasoning_effort": ["none", "low", "medium", "high", "xhigh"]
  }
}
```

Declare only levels accepted by that connection. `false` disables support;
`true` declares low/medium/high; an explicit array is preferred. An empty array
also disables support. `meta.capabilities.reasoning_effort` is accepted as a
fallback. Explicit metadata takes priority over built-in recognition. Ollama and
arena models do not expose this control. Do not advertise `none` when the model
requires reasoning (for example GPT-6 Astra).

The UI's `extra high` maps to API `xhigh`. The BFF consumes
`_kakam_reasoning_effort` after saved model defaults, removes stale effort from
unsupported requests, and strips the private marker. Direct and function paths
consume it before dispatch. OpenAI Responses connections use `reasoning.effort`.
Calls without the marker retain existing default behavior. The composer overrides
older Advanced Params Effort values for UI chat requests without deleting saved
settings. Other sampling/custom parameters remain unchanged.

Capability references checked 2026-09-20:

- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/models/gpt-5.5
- https://developers.openai.com/api/docs/models/gpt-5.2
- https://developers.openai.com/api/docs/models/gpt-5
- https://developers.openai.com/api/docs/guides/reasoning

Validation:

```sh
npx vitest run src/lib/kakam
python3 -m unittest discover -s backend/open_webui/kakam -p test_effort.py -v
```
