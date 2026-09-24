<script lang="ts">
	import { page } from '$app/stores';
	import { mobile, showSidebar, user } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import JevIcon from './JevIcon.svelte';
	export let compact = false;
</script>

{#if $user?.role === 'admin' || $user?.role === 'user'}
	<Tooltip
		content={compact ? 'defer to' : ''}
		placement="right"
		className={compact ? 'flex' : 'px-1 flex text-gray-700 dark:text-gray-300'}
	>
		<a
			href="/defer-to"
			aria-label="defer to"
			aria-current={$page.url.pathname === '/defer-to' ? 'page' : undefined}
			on:click={() => {
				if ($mobile) showSidebar.set(false);
			}}
			class={compact
				? 'group flex size-8 items-center justify-center rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900'
				: 'group flex grow items-center gap-2 rounded-xl px-2 py-1.5 transition hover:bg-gray-100 dark:hover:bg-gray-900'}
			class:active={$page.url.pathname === '/defer-to'}
		>
			<JevIcon />
			{#if !compact}<span class="translate-y-[0.5px] text-[0.8125rem] leading-5">defer to</span
				>{/if}
		</a>
	</Tooltip>
{/if}

<style>
	.active {
		background: var(--kakam-surface, #f3f3f3);
	}
</style>
