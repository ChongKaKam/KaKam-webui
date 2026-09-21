<script lang="ts">
	import { onMount } from 'svelte';
	import { showSettings } from '$lib/stores';
	import { getOwnership } from '../api';
	let managed: boolean | null = null;
	let error = false;
	async function load() {
		error = false;
		try {
			managed = (await getOwnership()).manager_enabled;
		} catch {
			error = true;
		}
	}
	onMount(load);
</script>

{#if managed === true}
	<div
		class="rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/20 p-3 space-y-2"
	>
		<div class="flex flex-wrap items-center gap-2 text-sm font-medium">
			<span>上下文压缩</span><span class="text-xs text-blue-700 dark:text-blue-300"
				>已由 Memory Manager 接管</span
			>
		</div>
		<p class="text-xs text-gray-600 dark:text-gray-400">
			Open WebUI 原生压缩设置当前不生效，原配置仍保留。压缩模型在 Memory
			服务配置；自动压缩开关与额度在聊天 Context → Session Memory
			中设置。接管状态不代表模型已配置或服务可用。
		</p>
		<button
			type="button"
			class="text-xs text-blue-700 dark:text-blue-300 underline"
			on:click={() => showSettings.set('admin:memory')}>前往 Memory 服务设置</button
		>
	</div>
{:else if managed === false}
	<slot />
{:else}
	<div class="text-xs text-gray-500" role="status">
		{error ? '暂时无法确认上下文压缩的接管状态。' : '正在确认上下文压缩的接管状态…'}
		{#if error}<button type="button" class="underline ml-2" on:click={load}>重试</button>{/if}
	</div>
{/if}
