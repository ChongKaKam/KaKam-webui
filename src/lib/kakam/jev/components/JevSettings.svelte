<script lang="ts">
	import { onMount } from 'svelte';
	import { getJevConfig, saveJevConfig, testJevConnection } from '../api';
	import { notifyJevConfigChanged } from '../service';
	import type { ConnectionStatus, ConnectionView } from '../types';
	import JevIcon from './JevIcon.svelte';
	let saved: ConnectionView | null = null;
	let baseUrl = 'https://api.typesafe.ai/v1';
	let apiKey = '';
	let clearKey = false;
	let busy = '';
	let error = '';
	let notice = '';
	let test: ConnectionStatus | null = null;
	const draft = () => ({
		base_url: baseUrl,
		...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
		clear_api_key: clearKey
	});
	function edited() {
		test = null;
		error = '';
		notice = '';
	}
	async function load() {
		busy = 'load';
		error = '';
		try {
			saved = await getJevConfig();
			baseUrl = saved.base_url;
		} catch (cause) {
			error = (cause as Error).message;
		} finally {
			busy = '';
		}
	}
	async function action(kind: 'save' | 'test') {
		busy = kind;
		error = '';
		notice = '';
		try {
			if (kind === 'test') test = await testJevConnection(draft());
			else {
				saved = await saveJevConfig(draft());
				baseUrl = saved.base_url;
				apiKey = '';
				clearKey = false;
				notice = '配置已保存';
				notifyJevConfigChanged();
			}
		} catch (cause) {
			error = (cause as Error).message;
			test = null;
		} finally {
			busy = '';
		}
	}
	onMount(load);
</script>

<section class="jev-settings" aria-label="Jev 模型管理">
	<div class="heading">
		<span class="icon"><JevIcon className="size-6" /></span>
		<div>
			<h2>Jev 模型管理</h2>
			<p>连接 TypeSafe 的决策模型，用于 defer to。</p>
		</div>
	</div>
	<form on:submit|preventDefault={() => action('save')}>
		<label for="jev-base-url">Base URL</label>
		<input
			id="jev-base-url"
			type="url"
			bind:value={baseUrl}
			on:input={edited}
			disabled={!!busy}
			required
			placeholder="https://api.typesafe.ai/v1"
		/>
		<p class="hint">默认使用官方 API，也支持兼容的服务地址。</p>
		<label for="jev-api-key"
			>API Key {#if saved?.has_api_key}<span class="saved">已配置</span>{/if}</label
		>
		<input
			id="jev-api-key"
			type="password"
			bind:value={apiKey}
			on:input={() => {
				clearKey = false;
				edited();
			}}
			disabled={!!busy}
			autocomplete="new-password"
			spellcheck="false"
			placeholder={saved?.has_api_key ? '留空保留已保存的密钥' : '输入 TypeSafe API Key'}
		/>
		<p class="hint">密钥保存在服务端，此页面不会回显已保存的密钥。</p>
		{#if saved?.has_api_key}<label class="clear"
				><input
					type="checkbox"
					bind:checked={clearKey}
					disabled={!!busy}
					on:change={() => {
						if (clearKey) apiKey = '';
						edited();
					}}
				/>清除已保存的密钥</label
			>{/if}
		<div class="model">
			<span>决策模型</span><strong>jev-latest</strong><span class="tag">Choice · Score · Noul</span>
		</div>
		<div class="actions">
			<button
				class="secondary"
				type="button"
				disabled={!!busy || clearKey || (!apiKey.trim() && !saved?.has_api_key)}
				on:click={() => action('test')}>{busy === 'test' ? '正在测试…' : '测试连接'}</button
			><button class="primary" type="submit" disabled={!!busy || !baseUrl.trim()}
				>{busy === 'save' ? '保存中…' : '保存配置'}</button
			>
		</div>
		<p class="hint">测试会执行一次简短的 Jev 判断。测试成功后，点击保存使配置生效。</p>
	</form>
	{#if test}<div class="success" role="status">
			<span class="dot"></span>连接成功 <span>{test.model} · {test.latency_ms} ms</span>
		</div>{/if}
	{#if notice}<p class="notice" role="status">{notice}</p>{/if}
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if !saved && !busy}<button class="secondary" on:click={load}>重新加载</button>{/if}
	<a class="docs" href="https://docs.typesafe.ai/api" target="_blank" rel="noreferrer"
		>TypeSafe API 文档 ↗</a
	>
</section>

<style>
	.jev-settings {
		max-width: 46rem;
		padding: 0.25rem 0.25rem 2rem;
		color: var(--kakam-text);
	}
	.heading {
		display: flex;
		gap: 0.9rem;
		align-items: center;
		margin-bottom: 2rem;
	}
	.icon {
		background: var(--kakam-surface);
		padding: 0.7rem;
		border-radius: 1rem;
	}
	h2 {
		font-size: 1.15rem;
		font-weight: 600;
	}
	p {
		margin-top: 0.4rem;
		color: var(--kakam-muted);
		font-size: 0.85rem;
		line-height: 1.6;
	}
	form {
		border: 1px solid var(--kakam-border);
		padding: 1.35rem;
		border-radius: 1.1rem;
	}
	label {
		display: block;
		font-size: 0.85rem;
		font-weight: 500;
		margin-bottom: 0.6rem;
	}
	input[type='url'],
	input[type='password'] {
		width: 100%;
		padding: 0.75rem 0.9rem;
		border: 1px solid var(--kakam-border);
		border-radius: 0.7rem;
		background: transparent;
		outline-offset: 3px;
		font-size: 0.9rem;
	}
	.hint {
		font-size: 0.76rem;
		margin: 0.5rem 0 1.3rem;
	}
	.hint:last-child {
		margin-bottom: 0;
	}
	.saved {
		font-size: 0.68rem;
		color: #059669;
		margin-left: 0.5rem;
	}
	.clear {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.78rem;
		color: var(--kakam-muted);
	}
	.model {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.7rem;
		padding: 1rem 0;
		font-size: 0.8rem;
		border-top: 1px solid var(--kakam-border);
	}
	.tag {
		color: var(--kakam-muted);
		font-size: 0.7rem;
	}
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.6rem;
		margin-top: 0.65rem;
	}
	button {
		font-size: 0.8rem;
		padding: 0.6rem 1rem;
		border-radius: 0.7rem;
		font-weight: 500;
	}
	button:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
	.primary {
		background: var(--kakam-text);
		color: var(--kakam-surface);
	}
	.secondary {
		border: 1px solid var(--kakam-border);
	}
	.success {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: center;
		padding: 1rem 0;
		font-size: 0.85rem;
	}
	.success span:last-child {
		color: var(--kakam-muted);
		font-size: 0.75rem;
	}
	.dot {
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 100%;
		background: #10b981;
	}
	.notice {
		color: #059669;
	}
	.error {
		color: #dc6464;
	}
	.docs {
		display: inline-block;
		margin-top: 1.6rem;
		font-size: 0.76rem;
		color: var(--kakam-muted);
		text-decoration: underline;
		text-underline-offset: 3px;
	}
</style>
