<script lang="ts">
	import { discoverModels, resetProvider, saveProvider, testProvider } from '../api';
	import { discoverySource, payload, toForm } from '../service';
	import type { ConfigView, ModelsResult, ProbeResult, ProviderKind, ProviderView } from '../types';
	import ProviderDiagnostics from './ProviderDiagnostics.svelte';

	export let kind: ProviderKind;
	export let value: ProviderView;
	export let writable: boolean;
	export let onSaved: (result: ConfigView) => void;
	let form = toForm(value);
	let busy = '';
	let error = '';
	let result: ProbeResult | null = null;
	let confirmReset = false;
	let discovery: ModelsResult | null = null;
	let previousSource = '';
	$: source = discoverySource(form);
	$: if (source !== previousSource) {
		previousSource = source;
		discovery = null;
		result = null;
	}

	async function run(action: 'save' | 'test' | 'reset' | 'discover') {
		if (busy) return;
		busy = action;
		error = '';
		result = null;
		try {
			if (action === 'discover') {
				discovery = null;
				discovery = await discoverModels(kind, payload(form));
				result = discovery;
			} else if (action === 'test') result = await testProvider(kind, payload(form));
			else {
				const updated =
					action === 'save'
						? await saveProvider(kind, payload(form))
						: await resetProvider(kind, form.revision, form.acknowledge_reindex);
				form.api_key = '';
				onSaved(updated);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : '配置操作失败';
		} finally {
			busy = '';
		}
	}
</script>

<section class="rounded-2xl border border-gray-200 dark:border-gray-800 p-4 min-w-0">
	<div class="flex flex-wrap items-center justify-between gap-2 mb-1">
		<h3 class="font-semibold">
			{kind === 'context' ? 'Context · 上下文压缩' : 'Embedding · 记忆检索'}
		</h3>
		<span class="text-xs rounded-md bg-gray-100 dark:bg-gray-850 px-2 py-1">
			{value.source === 'database' ? '数据库配置' : '环境变量'} · v{value.revision}
		</span>
	</div>
	<p class="text-xs text-gray-500 mb-4">
		{kind === 'context'
			? '由 Memory Server 调用，用于生成 Session 摘要；不是聊天主模型。'
			: '用于保存记忆时生成向量，以及召回时的语义检索。'}
	</p>
	<ProviderDiagnostics
		{busy}
		{error}
		{result}
		onTest={() => run('test')}
		onDiscover={() => run('discover')}
	/>
	<form
		on:submit|preventDefault={() => run('save')}
		on:input={() => (result = null)}
		on:change={() => (result = null)}
		autocomplete="off"
	>
		<fieldset disabled={!!busy} class="space-y-3 min-w-0">
			<label class="flex items-center gap-2 text-sm">
				<input type="checkbox" bind:checked={form.enabled} /> 启用此服务
			</label>
			<label class="block text-sm"
				>Base URL
				<input
					class="field"
					type="url"
					bind:value={form.base_url}
					placeholder="https://provider.example/v1"
					required={form.enabled}
				/>
			</label>
			<p class="text-xs text-gray-500">
				填写 API 基础地址，不要附加 /responses、/chat/completions 或 /embeddings。测试与调用从
				Memory Server 发起。
			</p>
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
				<label class="block text-sm"
					>模型名称
					<input
						class="field"
						bind:value={form.model}
						required={form.enabled}
						maxlength="200"
						placeholder="供应商的模型 ID"
					/>
				</label>
				{#if discovery?.ok && discovery.models.length}
					<label class="block text-sm"
						>探测到的模型（{discovery.models.length}）
						<select class="field" bind:value={form.model}>
							<option value="">请选择模型</option>
							{#if form.model && !discovery.models.includes(form.model)}<option value={form.model}
									>{form.model}（手动填写）</option
								>{/if}
							{#each discovery.models as model}<option value={model}>{model}</option>{/each}
						</select>
						<span class="block mt-1 text-xs text-gray-500"
							>列表不区分模型能力，请选择适合{kind === 'context'
								? '文本摘要'
								: 'Embedding'}的模型并测试。{discovery.truncated
								? '仅显示部分模型；仍可手动填写其他模型 ID。'
								: ''}</span
						>
					</label>
				{/if}
				{#if kind === 'context'}
					<label class="block text-sm"
						>API 协议
						<select class="field" bind:value={form.protocol}>
							<option value="chat_completions">Chat Completions</option>
							<option value="responses">Responses</option>
						</select>
					</label>
				{:else}
					<label class="block text-sm"
						>向量维度
						<input
							class="field"
							type="number"
							min="1"
							max="16000"
							step="1"
							required
							bind:value={form.dimension}
						/>
					</label>
				{/if}
			</div>
			<label class="block text-sm"
				>请求超时（秒）
				<input
					class="field"
					type="number"
					min="1"
					max="60"
					step="1"
					required
					bind:value={form.timeout_seconds}
				/>
			</label>
			<label class="block text-sm"
				>API Key · {value.api_key_set ? '已配置（不回显）' : '未配置'}
				<select class="field" bind:value={form.api_key_action}>
					<option value="keep">保留现有密钥</option>
					<option value="replace">替换密钥</option>
					<option value="clear">清除密钥（无鉴权服务）</option>
				</select>
			</label>
			{#if form.api_key_action === 'replace'}
				<label class="block text-sm"
					>新的 API Key
					<input
						class="field"
						type="password"
						bind:value={form.api_key}
						autocomplete="new-password"
						required
						maxlength="8192"
						placeholder="输入新密钥，保存后不再回显"
					/>
				</label>
			{/if}
			{#if kind === 'embedding'}
				<div
					class="rounded-lg bg-amber-50 dark:bg-amber-950/30 p-3 text-xs text-amber-900 dark:text-amber-200 space-y-2"
				>
					<p>
						更换地址、模型或维度会改变向量空间。旧记忆仍保留，但不会参与新空间的语义检索。本版不自动重建向量；可恢复旧配置，或逐条编辑并保存记忆重新生成向量。
					</p>
					<label class="flex items-start gap-2"
						><input type="checkbox" bind:checked={form.acknowledge_reindex} />
						<span>我已理解旧记忆需重建向量，同意切换（恢复环境配置时也适用）</span>
					</label>
				</div>
			{/if}
			<div class="flex flex-wrap gap-2 pt-1">
				<button class="action primary" type="submit" disabled={!writable}
					>{busy === 'save' ? '保存中…' : '保存配置'}</button
				>
				<button
					class="action"
					type="button"
					disabled={!writable || value.source === 'environment'}
					on:click={() => (confirmReset = !confirmReset)}>恢复环境变量</button
				>
			</div>
			{#if confirmReset}
				<div class="rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-sm space-y-2">
					<p>
						确定删除此组数据库覆盖配置并立即恢复 Memory Server
						启动时读取的环境变量吗？不会删除记忆内容。
					</p>
					<button class="action" type="button" on:click={() => run('reset')}>确认恢复</button>
					<button class="action" type="button" on:click={() => (confirmReset = false)}>取消</button>
				</div>
			{/if}
		</fieldset>
	</form>
	<p class="mt-3 text-xs text-gray-500">
		测试不会保存配置，仅发送合成文本，可能产生少量模型调用费用。
	</p>
</section>

<style>
	.field {
		display: block;
		width: 100%;
		min-width: 0;
		margin-top: 0.375rem;
		border: 1px solid #8884;
		border-radius: 0.5rem;
		padding: 0.5rem 0.625rem;
		background: transparent;
		font-size: 0.875rem;
	}
	.action {
		border: 1px solid #8884;
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
		font-size: 0.75rem;
	}
	.primary {
		background: #2563eb;
		color: white;
		border-color: #2563eb;
	}
	button:disabled,
	fieldset:disabled {
		opacity: 0.5;
	}
	button:disabled {
		cursor: not-allowed;
	}
</style>
