<script lang="ts">
	import type { Composition } from '../types';
	import ContextDrawer from './ContextDrawer.svelte';
	export let report: Composition | null = null;
	let open = false;
	let identity = '';
	$: nextIdentity = report ? `${report.message_id}:${report.detail_id ?? ''}` : '';
	$: if (nextIdentity !== identity) {
		identity = nextIdentity;
		open = false;
	}
</script>

{#if report}
	<div class="mx-auto flex w-full max-w-3xl justify-end px-4 py-1">
		<button
			type="button"
			class="flex items-center gap-2 rounded-lg px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white"
			aria-haspopup="dialog"
			aria-expanded={open}
			on:click={() => (open = !open)}
		>
			<span aria-hidden="true">◫</span>
			<span>Context · 查看详情</span>
			{#if report.status === 'unavailable'}<span class="text-amber-600 dark:text-amber-400"
					>记忆已降级</span
				>{/if}
		</button>
	</div>
	{#if open}<ContextDrawer {report} on:close={() => (open = false)} />{/if}
{/if}
