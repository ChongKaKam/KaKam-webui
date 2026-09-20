<script lang="ts">
	import { tick } from 'svelte';
	import { user, showSettings, mobile, showSidebar } from '$lib/stores';
	import DatabaseSettings from '$lib/components/icons/DatabaseSettings.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { canAccessMemoryPolicy, memoryPolicyTab } from '../navigation';

	export let compact = false;

	async function openPolicy(event: MouseEvent) {
		event.stopPropagation();
		showSettings.set(memoryPolicyTab.id);
		if ($mobile) {
			await tick();
			showSidebar.set(false);
		}
	}
</script>

{#if canAccessMemoryPolicy($user)}
	<Tooltip
		content={compact ? 'Memory' : ''}
		placement="right"
		className={compact ? 'flex' : 'px-1 flex text-gray-700 dark:text-gray-300'}
	>
		<button
			type="button"
			aria-label="Memory"
			on:click={openPolicy}
			class={compact
				? 'group flex size-8 cursor-pointer items-center justify-center'
				: 'group flex grow items-center gap-2 rounded-xl px-2 py-1.5 text-left transition hover:bg-gray-100 dark:hover:bg-gray-900'}
		>
			<span
				class={compact
					? 'flex size-[calc(30px*var(--app-text-scale,1))] items-center justify-center rounded-lg transition group-hover:bg-gray-100 dark:group-hover:bg-gray-900'
					: 'flex size-4 shrink-0 items-center justify-center'}
			>
				<DatabaseSettings className="size-4" />
			</span>
			{#if !compact}<span class="translate-y-[0.5px] text-[0.8125rem] leading-5">Memory</span>{/if}
		</button>
	</Tooltip>
{/if}
