# Cloud image connection and model tests

The Images settings mounts a project-owned test panel for OpenAI-compatible and
Gemini generation/editing configuration. Local engines retain native verification.

- **测试连接并读取模型**: sends the unsaved Base URL/key to the administrator-only
  BFF, reads the provider's `/models`, and checks whether the configured model ID
  is present. All returned models are shown without guessing image support from names.
  Selecting a result fills the existing model input; saving still uses the native form.
- **验证生成（可能计费）**: available only for generation. Explicitly requests one
  test image with the configured model/size/additional parameters and protocol.
  OpenAI response-format selection follows the native configured regex. The prompt,
  model and count are forced for this test; streaming is disabled. Gemini uses its
  configured `predict` or `generateContent` method, matching the native generator.
  No automatic generation follows opening the settings or reading models.
- Editing configuration supports connection/model-list discovery only, not an
  image edit test. Models visibility does not prove edit/generation permissions.

`POST /api/custom/images/probe` requires the existing Open WebUI admin dependency.
Request: `engine: openai|gemini`, `action: models|generate`, `base_url`, `api_key`,
optional `api_version`, `model`, `size`, `params`, `method: predict|generateContent`.
Response for discovery: `models: [{id,name}]`, `complete`, and
`model_status: available|not_listed|unknown`. Generation returns `generated: true`
only when an HTTP image URL or recognizable base64 image signature is present.
This verifies the response shape, not image quality or downstream URL accessibility.

The BFF sends credentials server-side, never follows redirects, and does not echo
provider bodies or log secrets. Responses are bounded to 32 MiB. Gemini discovery
has a ten-page/5,000-model cap; incomplete lists cannot establish that a model is
unavailable. Server deadlines are 25s for discovery and 120s for generation; client
deadlines are 30s/130s. Configuration changes and component destruction cancel the
client request and discard stale results. Cancellation cannot retract a request
already accepted by the provider; retries can incur another charge.

The BFF does not write configuration, images, chats, or a model cache. Tests use
injected provider responses; no production credentials or billable services are
needed. A final real-provider check remains dependent on the administrator's URL,
key, model access and quota.
