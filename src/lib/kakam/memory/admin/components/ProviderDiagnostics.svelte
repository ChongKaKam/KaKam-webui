<script lang="ts">
	import type { ProbeResult } from '../types';
	export let busy: string;
	export let error: string;
	export let result: ProbeResult | null;
	export let onTest: () => void;
	export let onDiscover: () => void;
</script>

<div class="mb-4 space-y-2">
	<div class="flex flex-wrap gap-2">
		<button
			type="button"
			disabled={!!busy}
			class="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-2 text-xs disabled:opacity-50"
			on:click={onDiscover}
		>
			{busy === 'discover' ? '探测中…' : '检测连接 / 获取模型'}
		</button>
		<button
			type="button"
			disabled={!!busy}
			class="rounded-lg border border-gray-300 dark:border-gray-700 px-3 py-2 text-xs disabled:opacity-50"
			on:click={onTest}
		>
			{busy === 'test' ? '测试中…' : '测试模型调用'}
		</button>
	</div>
	<p class="text-xs text-gray-500">
		填好 Base URL
		和密钥后可获取列表，无需先填模型。选定模型后再测试实际调用；两种检查都不会保存配置。
	</p>
	{#if error}<p role="alert" class="text-sm text-red-600 dark:text-red-400 break-words">
			{error}
		</p>{/if}
	{#if result}
		<p
			role="status"
			class="text-sm break-words"
			class:text-green-600={result.ok}
			class:text-red-500={!result.ok}
		>
			{result.message} · {result.elapsed_ms} ms{result.http_status
				? ` · HTTP ${result.http_status}`
				: ''}
		</p>
	{/if}
</div>
