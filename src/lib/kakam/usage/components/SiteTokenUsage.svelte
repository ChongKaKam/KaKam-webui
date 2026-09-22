<script lang="ts">
	import { onMount } from 'svelte';
	import { user } from '$lib/stores';
	import { getSiteUsage } from '../api';
	import type { SiteUsage } from '../types';

	let data: SiteUsage | null = null;
	let loading = false;
	let error = '';
	let principal = '';
	let controller: AbortController | undefined;
	$: allowed = $user?.role === 'admin';

	async function load() {
		controller?.abort();
		if (!allowed || !principal) return;
		const request = new AbortController();
		controller = request;
		loading = true;
		error = '';
		const timeout = setTimeout(() => request.abort(), 8000);
		try {
			const result = await getSiteUsage(localStorage.token, request.signal);
			if (controller !== request || request.signal.aborted) return;
			data = result;
		} catch {
			if (controller !== request) return;
			data = null;
			error = '暂时无法获取用量';
		} finally {
			clearTimeout(timeout);
			if (controller === request) loading = false;
		}
	}

	onMount(() => {
		const unsubscribe = user.subscribe((current) => {
			const next = current?.role === 'admin' ? current.id : '';
			if (principal === next) return;
			controller?.abort();
			controller = undefined;
			data = null;
			error = '';
			principal = next;
			// The subscription supplies identity before Svelte's reactive flush.
			allowed = !!next;
			if (next) void load();
		});
		return () => {
			unsubscribe();
			const pending = controller;
			controller = undefined;
			pending?.abort();
		};
	});
</script>

{#if allowed}
	<section
		aria-label="本站 Token 使用情况"
		aria-busy={loading}
		class="h-full overflow-y-auto space-y-6 pb-4"
	>
		<header class="flex items-start justify-between gap-4">
			<div>
				<h2 class="text-lg font-medium">本站 Token 使用情况</h2>
				<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
					所有用户 · 全部时间 · 已记录的聊天用量
				</p>
			</div>
			<button
				type="button"
				class="shrink-0 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm disabled:opacity-40"
				on:click={load}
				disabled={loading}>{loading ? '加载中…' : '刷新'}</button
			>
		</header>
		{#if error}
			<div role="status" class="rounded-xl bg-gray-50 dark:bg-gray-900 p-6 text-sm">
				{error}<button type="button" class="ml-3 underline underline-offset-4" on:click={load}
					>重试</button
				>
			</div>
		{:else if data}
			<div class="rounded-2xl bg-gray-50 dark:bg-gray-900 p-5 sm:p-6">
				<p class="text-sm text-gray-500 dark:text-gray-400">累计总量</p>
				<p class="mt-2 break-all text-3xl sm:text-4xl font-medium tabular-nums tracking-tight">
					{data.total_tokens.toLocaleString()}
				</p>
				<p class="mt-1 text-xs text-gray-500">tokens</p>
				<div class="mt-6 grid grid-cols-2 gap-4 border-t border-gray-200 dark:border-gray-800 pt-4">
					<div>
						<p class="text-sm text-gray-500 dark:text-gray-400">输入 tokens</p>
						<p class="mt-1 break-all text-xl tabular-nums">{data.input_tokens.toLocaleString()}</p>
					</div>
					<div>
						<p class="text-sm text-gray-500 dark:text-gray-400">输出 tokens</p>
						<p class="mt-1 break-all text-xl tabular-nums">{data.output_tokens.toLocaleString()}</p>
					</div>
				</div>
			</div>
			<p class="text-sm text-gray-500 dark:text-gray-400">
				已记录 {data.recorded_users.toLocaleString()} 位用户、{data.recorded_messages.toLocaleString()}
				条回复的用量。
			</p>
			{#if data.recorded_messages === 0}<p class="text-sm text-gray-500" role="status">
					暂无已记录的 token 用量。
				</p>{/if}
		{:else}
			<p role="status" class="py-10 text-center text-sm text-gray-500">正在加载用量…</p>
		{/if}
		<p class="text-xs leading-relaxed text-gray-500 dark:text-gray-400">
			统计口径：累计输入 + 输出 tokens。未返回 usage
			的请求、未保存的临时聊天及未记入聊天记录的辅助调用可能不在其中；删除聊天记录可能影响历史总量。此数据不等同于供应商账单。
		</p>
	</section>
{/if}
