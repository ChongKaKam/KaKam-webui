<script lang="ts">
	import { createEventDispatcher, tick } from 'svelte';
	import { user, showSettings, mobile, showSidebar } from '$lib/stores';
	import DatabaseSettings from '$lib/components/icons/DatabaseSettings.svelte';
	import { canAccessMemoryPolicy, memoryPolicyTab } from '../navigation';
	const dispatch = createEventDispatcher();

	async function openPolicy() {
		dispatch('navigate');
		showSettings.set(memoryPolicyTab.id);
		if ($mobile) {
			await tick();
			showSidebar.set(false);
		}
	}
</script>

{#if canAccessMemoryPolicy($user)}
	<button
		type="button"
		on:click={openPolicy}
		class="flex h-[1.6875rem] items-center gap-2 rounded-xl px-2 text-[0.8125rem] w-full hover:bg-gray-100 dark:hover:bg-gray-900 transition cursor-pointer select-none text-left"
	>
		<DatabaseSettings className="size-3.5" />
		<span class="truncate">Memory Policy</span>
	</button>
{/if}
