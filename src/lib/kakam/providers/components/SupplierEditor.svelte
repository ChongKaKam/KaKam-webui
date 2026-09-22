<script lang="ts">
	import { onDestroy } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import { probeProvider } from '../api';
	import { connectionFingerprint, poolConnection } from '../service';
	import { reasoningSummary } from '../reasoning';
	import type { Connection } from '../types';
	export let connection: Connection;
	export let onSave: (connection: Connection) => Promise<void>;
	export let onClose: () => void;
	export let isNew = false;
	let show = true;
	let draft = structuredClone(connection);
	draft.config = {
		...draft.config,
		enable: draft.config.enable ?? true,
		api_type: draft.config.api_type ?? '',
		auth_type: draft.config.auth_type ?? 'bearer',
		provider: draft.config.provider ?? (draft.config.azure ? 'azure' : ''),
		headers: draft.config.headers ?? {}
	};
	let alias = draft.config.kakam_supplier?.alias ?? '';
	let discovered = draft.config.kakam_supplier?.models ?? [];
	let selected = [...(draft.config.model_ids ?? [])];
	let verified = draft.config.kakam_supplier && !isNew ? connectionFingerprint(draft) : '';
	let headers = JSON.stringify(draft.config.headers ?? {}, null, 2);
	let error = '';
	let status = '';
	let search = '';
	let probing = false;
	let saving = false;
	let request: AbortController | undefined;
	let alive = true;
	$: fingerprint = connectionFingerprint(draft);
	$: valid = verified === fingerprint;
	$: visible = discovered.filter((model) =>
		`${model.name} ${model.id}`.toLowerCase().includes(search.toLowerCase())
	);
	$: if (!show) onClose();
	function setHeaders() {
		try {
			const parsed = JSON.parse(headers);
			if (
				!parsed ||
				Array.isArray(parsed) ||
				typeof parsed !== 'object' ||
				Object.values(parsed).some((v) => typeof v !== 'string')
			)
				throw new Error();
			draft.config = { ...draft.config, headers: parsed };
			return true;
		} catch {
			error = '请求头需要是值为字符串的 JSON 对象。';
			return false;
		}
	}
	async function probe() {
		if (!setHeaders()) return;
		error = '';
		status = '';
		probing = true;
		verified = '';
		const snapshot = connectionFingerprint(draft);
		const controller = new AbortController();
		request = controller;
		const timeout = setTimeout(() => controller.abort(), 30000);
		try {
			const result = await probeProvider(localStorage.token, draft, controller.signal);
			if (!alive) return;
			if (snapshot !== connectionFingerprint(draft)) {
				error = '连接信息已变化，请重新探测。';
				return;
			}
			discovered = result;
			selected = selected.filter((id) => result.some((model) => model.id === id));
			verified = snapshot;
			status = `连接探测成功，发现 ${result.length} 个模型。请勾选需要入池的模型。`;
		} catch (cause) {
			if (alive)
				error = controller.signal.aborted
					? '探测超时，请检查服务后重试。'
					: cause instanceof Error
						? cause.message
						: '探测失败，请检查连接。';
		} finally {
			clearTimeout(timeout);
			if (alive) probing = false;
		}
	}
	async function save() {
		if (!setHeaders()) return;
		if (verified !== connectionFingerprint(draft)) {
			error = '请先使用当前连接信息探测 models。';
			return;
		}
		saving = true;
		error = '';
		try {
			await onSave(poolConnection(draft, alias, discovered, selected));
			show = false;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			saving = false;
		}
	}
	onDestroy(() => {
		alive = false;
		request?.abort();
	});
</script>

<Modal bind:show size="lg">
	<form class="supplier-editor" on:submit|preventDefault={save}>
		<header>
			<h2>{isNew ? '添加供应商' : '编辑供应商'}</h2>
			<button type="button" aria-label="关闭供应商设置" on:click={() => (show = false)}>✕</button>
		</header>
		<fieldset disabled={saving || probing}>
			<label
				>供应商别名<input
					bind:value={alias}
					maxlength="80"
					required
					placeholder="例如：官方 OpenAI、团队中转"
				/></label
			>
			<label
				>Base URL<input
					bind:value={draft.url}
					type="url"
					required
					autocomplete="off"
					placeholder="https://api.openai.com/v1"
				/></label
			>
			<label
				>API Key<input
					bind:value={draft.key}
					type="password"
					autocomplete="new-password"
					placeholder="输入供应商密钥"
				/></label
			>
			<label
				>接口协议<select bind:value={draft.config.api_type}
					><option value="">Chat Completions</option><option value="responses">Responses API</option
					></select
				></label
			>
			<label class="check"
				><input type="checkbox" bind:checked={draft.config.enable} />启用供应商</label
			>
			<details>
				<summary>高级连接设置</summary>
				<label
					>认证方式<select bind:value={draft.config.auth_type}
						><option value="bearer">Bearer API Key</option><option value="none">无认证</option
						><option value="session">用户 Session</option><option value="system_oauth">OAuth</option
						><option value="microsoft_entra_id">Microsoft Entra ID</option><option value="azure_ad"
							>Azure AD</option
						></select
					></label
				>
				<label
					>兼容类型<select
						bind:value={draft.config.provider}
						on:change={() => (draft.config.azure = draft.config.provider === 'azure')}
						><option value="">OpenAI-compatible</option><option value="azure">Azure OpenAI</option
						><option value="litellm">LiteLLM</option><option value="llama.cpp">llama.cpp</option
						><option value="lmstudio">LM Studio</option></select
					></label
				>
				{#if draft.config.provider === 'azure' || draft.config.azure}<label
						>Azure API Version<input
							bind:value={draft.config.api_version}
							placeholder="2024-10-21"
						/></label
					>{/if}
				<label
					>附加请求头<textarea
						bind:value={headers}
						on:input={() => (verified = '')}
						rows="3"
						spellcheck="false"
					></textarea></label
				>
				<label
					>模型标识前缀<input
						bind:value={draft.config.prefix_id}
						readonly={!!connection.config.kakam_supplier}
					/></label
				>
				<p class="note">
					新供应商自动分配稳定前缀。同名模型因此可以独立管理。已有连接修改前缀会改变模型
					ID，需要重新配置权限和默认模型。
				</p>
			</details>
		</fieldset>
		<section aria-label="模型白名单">
			<div class="row">
				<h3>模型白名单</h3>
				<button
					type="button"
					class="action"
					on:click={probe}
					disabled={probing || saving || !draft.url}>{probing ? '正在探测…' : '探测 models'}</button
				>
			</div>
			<p class="note">
				先验证 Base URL 和 API Key，再选择入池模型。未勾选的模型不会载入；留空表示不载入任何模型。
			</p>
			<p class="note">
				所有模型均可选择思考强度，默认 high。以下能力信息仅供参考，不限制档位；调用失败时可改为 none 重试。探测不会发送付费聊天请求。
			</p>
			{#if status}<p role="status">{status}</p>{/if}
			{#if !valid}<p class="note">当前连接尚未验证，请先探测。</p>{/if}
			{#if discovered.length}
				<label
					>搜索模型<input bind:value={search} type="search" placeholder="名称或模型 ID" /></label
				>
				<div class="row">
					<span>已选择 {selected.length} / {discovered.length}</span>
					<div>
						<button
							type="button"
							disabled={!valid || probing || saving}
							on:click={() => (selected = [...new Set([...selected, ...visible.map((m) => m.id)])])}
							>全选搜索结果</button
						>
						·
						<button
							type="button"
							disabled={!valid || probing || saving}
							on:click={() => (selected = [])}>清空</button
						>
					</div>
				</div>
				<div class="model-list">
					<fieldset disabled={!valid || probing || saving}>
						{#each visible as model (model.id)}<label class="check model"
								><input type="checkbox" bind:group={selected} value={model.id} /><span
									>{model.name}{#if model.name !== model.id}<small>{model.id}</small>{/if}<small
										>{reasoningSummary(model.reasoning)}</small
									></span
								></label
							>{/each}
					</fieldset>
				</div>
			{/if}
		</section>
		{#if error}<p role="alert" class="error">{error}</p>{/if}
		<footer>
			<button type="button" on:click={() => (show = false)}>取消</button><button
				class="action"
				type="submit"
				disabled={saving || probing || !valid || !alias.trim()}
				>{saving ? '正在保存…' : '保存并载入模型'}</button
			>
		</footer>
	</form>
</Modal>

<style>
	.supplier-editor {
		padding: 1.5rem;
		font-size: 0.875rem;
		max-height: 85dvh;
		overflow-y: auto;
	}
	header,
	.row,
	footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}
	header {
		margin-bottom: 1rem;
	}
	h2 {
		font-size: 1.125rem;
		font-weight: 600;
	}
	h3 {
		font-weight: 600;
	}
	label {
		display: block;
		margin: 0.75rem 0;
	}
	input:not([type='checkbox']),
	select,
	textarea {
		display: block;
		width: 100%;
		border: 1px solid #8885;
		border-radius: 0.65rem;
		padding: 0.65rem;
		margin-top: 0.35rem;
		background: transparent;
		min-width: 0;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 0.65rem;
	}
	.model span {
		overflow-wrap: anywhere;
	}
	small {
		display: block;
		opacity: 0.65;
	}
	section {
		border-top: 1px solid #8884;
		margin-top: 1rem;
		padding-top: 1rem;
	}
	.note {
		color: var(--kakam-muted, #888);
		line-height: 1.6;
		margin: 0.65rem 0;
		font-size: 0.8125rem;
	}
	.model-list {
		max-height: 16rem;
		overflow-y: auto;
		margin-top: 0.5rem;
	}
	.model {
		padding: 0.4rem 0.25rem;
		margin: 0;
	}
	.action {
		background: rgb(128 128 128 / 0.15);
		border: 1px solid #8885;
		border-radius: 0.65rem;
		padding: 0.55rem 0.85rem;
	}
	footer {
		justify-content: flex-end;
		margin-top: 1rem;
	}
	button:disabled {
		opacity: 0.45;
	}
	.error {
		color: #c2410c;
		margin-top: 1rem;
	}
	:global(.dark) .error {
		color: #fdba74;
	}
	@media (max-width: 640px) {
		.supplier-editor {
			padding: 1rem;
		}
		input:not([type='checkbox']),
		select,
		textarea {
			font-size: 1rem;
		}
		.row {
			flex-wrap: wrap;
			gap: 0.5rem;
		}
	}
</style>
