<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { models, settings, config as backendConfig } from '$lib/stores';
	import { getBackendConfig } from '$lib/apis';
	import { getConnectionsConfig, setConnectionsConfig } from '$lib/apis/configs';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import SupplierEditor from './SupplierEditor.svelte';
	import { loadProviders, saveProviders, reloadModelPool } from '../api';
	import { connectionsFrom, connectionsTo, newConnection } from '../service';
	import type { Connection, ProviderConfig } from '../types';
	const dispatch = createEventDispatcher();
	let config: ProviderConfig | undefined;
	let connections: Connection[] = [];
	let directConfig: (Record<string, unknown> & { ENABLE_DIRECT_CONNECTIONS: boolean }) | null =
		null;
	let edit: { index: number; connection: Connection } | null = null;
	let deleting = -1;
	let showDelete = false;
	let busy = false;
	let error = '';
	let status = '';
	async function load() {
		try {
			config = await loadProviders(localStorage.token);
			connections = connectionsFrom(config);
			directConfig = await getConnectionsConfig(localStorage.token);
		} catch {
			error = '无法载入供应商配置，请检查管理员登录状态后重试。';
		}
	}
	async function persist(next: Connection[], enabled = config?.ENABLE_OPENAI_API ?? true) {
		if (!config || busy) return;
		busy = true;
		error = '';
		status = '';
		try {
			const updated = connectionsTo({ ...config, ENABLE_OPENAI_API: enabled }, next);
			await saveProviders(localStorage.token, updated);
			config = updated;
			connections = next;
			status = '供应商配置已保存。';
			try {
				models.set(
					await reloadModelPool(
						localStorage.token,
						$backendConfig?.features?.enable_direct_connections
							? ($settings?.directConnections ?? null)
							: null
					)
				);
			} catch {
				error = '配置已保存，但模型列表刷新失败，请刷新页面后重试。';
			}
			dispatch('save');
		} finally {
			busy = false;
		}
	}
	async function saveEdit(connection: Connection) {
		if (!edit) return;
		const next = [...connections];
		if (edit.index < 0) next.push(connection);
		else next[edit.index] = connection;
		await persist(next);
	}
	async function toggle(index: number) {
		try {
			await persist(
				connections.map((c, i) =>
					i === index ? { ...c, config: { ...c.config, enable: !(c.config.enable ?? true) } } : c
				)
			);
		} catch (cause) {
			error = String(cause);
		}
	}
	onMount(load);
</script>

<div class="supplier-settings">
	<h2>模型供应管理</h2>
	{#if config}
		<section>
			<div class="row">
				<h3>供应商（OpenAI 接口）</h3>
				<label class="check"
					><input
						type="checkbox"
						checked={config.ENABLE_OPENAI_API}
						disabled={busy}
						on:change={async (event) => {
							try {
								await persist(connections, event.currentTarget.checked);
							} catch (cause) {
								error = String(cause);
							}
						}}
					/>启用</label
				>
			</div>
			<p class="note">验证连接后选择模型白名单，再到“模型管理”配置启用状态与访问权限。</p>
			{#each connections as connection, index}
				<article>
					<div class="row">
						<div class="identity">
							<strong>{connection.config.kakam_supplier?.alias || `供应商 ${index + 1}`}</strong>
							<p>{connection.url}</p>
							<small
								>{connection.config.kakam_supplier
									? `白名单 ${connection.config.model_ids?.length ?? 0} 个模型`
									: '已有连接 · 编辑后可探测并设置白名单'}</small
							>
						</div>
						<label class="check"
							><input
								type="checkbox"
								checked={connection.config.enable ?? true}
								disabled={busy}
								on:change={() => toggle(index)}
							/>启用</label
						>
					</div>
					<div class="actions">
						<button type="button" disabled={busy} on:click={() => (edit = { index, connection })}
							>配置</button
						><button
							type="button"
							disabled={busy}
							on:click={() => {
								deleting = index;
								showDelete = true;
							}}>移除</button
						>
					</div>
				</article>
			{/each}
			<button
				type="button"
				class="action"
				disabled={busy}
				on:click={() => (edit = { index: -1, connection: newConnection() })}>＋ 添加供应商</button
			>
		</section>
		{#if directConfig}<section>
				<h3>用户连接</h3>
				<label class="check"
					><input
						type="checkbox"
						checked={directConfig.ENABLE_DIRECT_CONNECTIONS}
						on:change={async (event) => {
							const next = {
								...directConfig,
								ENABLE_DIRECT_CONNECTIONS: event.currentTarget.checked
							};
							try {
								await setConnectionsConfig(localStorage.token, next);
								directConfig = next;
								backendConfig.set(await getBackendConfig());
							} catch {
								error = '用户连接设置保存失败。';
							}
						}}
					/>允许用户使用自己的直连配置</label
				>
			</section>{/if}
	{:else}<p>正在载入供应商配置…</p>{/if}
	{#if status}<p role="status">{status}</p>{/if}
	{#if error}<p role="alert" class="error">{error}</p>
		{#if !config}<button type="button" on:click={load}>重试</button>{/if}{/if}
</div>
{#if edit}<SupplierEditor
		connection={edit.connection}
		isNew={edit.index < 0}
		onSave={saveEdit}
		onClose={() => (edit = null)}
	/>{/if}
<ConfirmDialog
	bind:show={showDelete}
	title="移除供应商"
	message="该供应商的模型将退出模型池。历史聊天和现有模型权限记录会保留。"
	on:confirm={async () => {
		try {
			await persist(connections.filter((_, index) => index !== deleting));
		} catch (cause) {
			error = String(cause);
		}
	}}
/>

<style>
	.supplier-settings {
		height: 100%;
		overflow-y: auto;
		padding-right: 0.25rem;
		font-size: 0.875rem;
	}
	h2 {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 1.5rem;
	}
	h3 {
		font-weight: 600;
	}
	section {
		margin-bottom: 1.5rem;
	}
	section + section {
		border-top: 1px solid #8884;
		padding-top: 1.25rem;
	}
	.row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}
	article {
		border: 1px solid #8884;
		border-radius: 0.9rem;
		padding: 1rem;
		margin: 0.75rem 0;
	}
	.identity {
		min-width: 0;
	}
	.identity p {
		overflow-wrap: anywhere;
		margin: 0.25rem 0;
		color: var(--kakam-muted, #888);
	}
	small,
	.note {
		color: var(--kakam-muted, #888);
		line-height: 1.6;
	}
	.note {
		margin: 0.75rem 0;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 1rem;
		margin-top: 0.75rem;
	}
	.action {
		border: 1px solid #8884;
		padding: 0.65rem 1rem;
		border-radius: 0.65rem;
	}
	button:disabled {
		opacity: 0.45;
	}
	.error {
		color: #c2410c;
		margin: 0.75rem 0;
	}
	:global(.dark) .error {
		color: #fdba74;
	}
</style>
