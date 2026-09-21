<script lang="ts">
	import { onMount } from 'svelte';
	import { getConfig } from '../api';
	import type { ConfigView, ProviderKind } from '../types';
	import ProviderSettings from './ProviderSettings.svelte';
	let config: ConfigView | null = null;
	let loading = false;
	let error = '';
	let notice = '';
	let loadRevision = 0;
	const kinds: ProviderKind[] = ['context', 'embedding'];
	let active: ProviderKind = 'context';
	async function load() {
		loading = true;
		error = '';
		try {
			config = await getConfig();
			loadRevision += 1;
			notice = '';
		} catch (e) {
			error = e instanceof Error ? e.message : '读取配置失败';
		} finally {
			loading = false;
		}
	}
	function saved(value: ConfigView) {
		config = value;
		notice = '配置已保存；后续 Memory 请求生效，进行中的请求继续使用原配置。';
	}
	onMount(load);
</script>

<!-- SettingsModal clips its fixed-height content; this page owns vertical scrolling. -->
<div
	role="region"
	aria-label="Memory 服务配置"
	tabindex="0"
	class="scrollbar-hover h-full min-h-0 w-full min-w-0 space-y-4 overflow-y-auto overscroll-contain pb-4 pr-1.5"
>
	<div class="flex items-center justify-between gap-3">
		<h2 class="text-lg font-semibold">Memory 服务</h2>
		<button type="button" class="text-xs underline" disabled={loading} on:click={load}
			>重新读取配置</button
		>
	</div>
	<p class="text-sm text-gray-500">
		管理员配置对当前租户的所有用户生效，记忆内容仍按用户隔离。此处与个人 Memory Policy 设置独立。
	</p>
	<nav aria-label="模型服务类型" class="grid grid-cols-2 gap-2">
		{#each kinds as kind}
			<button
				type="button"
				aria-pressed={active === kind}
				class="rounded-xl border p-3 text-left min-w-0 {active === kind
					? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30'
					: 'border-gray-200 dark:border-gray-800'}"
				on:click={() => (active = kind)}
			>
				<span class="block text-sm font-semibold"
					>{kind === 'context' ? 'Context' : 'Embedding'}</span
				>
				<span class="block text-xs text-gray-500"
					>{kind === 'context' ? '上下文压缩模型' : '记忆向量模型'}</span
				>
			</button>
		{/each}
	</nav>
	<p class="text-xs text-gray-500">
		没有独立自动抽取模型。用户主动要求记住时，由当前聊天模型调用记忆建议工具（需支持工具调用），用户确认后保存；手动录入不调用抽取模型。
	</p>
	{#if loading}<p role="status" class="text-sm">读取中…</p>{/if}
	{#if error}<p role="alert" class="text-sm text-red-500 break-words">{error}</p>{/if}
	{#if notice}<p role="status" class="text-sm text-green-600">{notice}</p>{/if}
	{#if config}
		{#if !config.write_enabled}
			<div class="rounded-lg bg-amber-50 dark:bg-amber-950/30 p-3 text-sm break-words">
				加密存储尚未启用。请在 Memory Server 部署环境中设置永久的 MEMORY_CONFIG_ENCRYPTION_KEY（64
				位十六进制），重启服务后再保存。请将此密钥与数据库备份一起安全保管，勿定期随机重置。现有环境变量配置仍可使用和测试。
			</div>
		{/if}
		{#each kinds as kind}
			<div hidden={active !== kind}>
				{#key `${kind}:${loadRevision}:${config.providers[kind].revision}`}
					<ProviderSettings
						{kind}
						value={config.providers[kind]}
						writable={config.write_enabled}
						onSaved={saved}
					/>
				{/key}
			</div>
		{/each}
	{/if}
	<p class="text-xs text-gray-500">
		数据库配置优先于环境变量。API Key
		加密保存，不在页面回显；修改服务地址时需明确替换或清除密钥。数据库凭据、服务间鉴权及加密主密钥仍由部署环境管理。聊天召回另受
		WebUI 的超时预算限制。
	</p>
</div>
