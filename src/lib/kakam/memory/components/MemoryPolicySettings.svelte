<script lang="ts">
	import MemoryActivity from './MemoryActivity.svelte';
	import MemorySettings from './MemorySettings.svelte';
	export let saveSettings: (value: Record<string, unknown>) => void | Promise<void>;
</script>

<div id="tab-memory-policy" class="flex h-full min-h-0 flex-col text-sm">
	<h2 class="mb-2 text-xl font-semibold text-gray-900 dark:text-white">Memory Policy</h2>
	<p class="mb-7 text-sm text-gray-500">记忆策略、Prompt 构成与长期记忆管理</p>
	<div class="scrollbar-hover min-h-0 flex-1 overflow-y-auto pr-1.5">
		<MemoryActivity />
		<div class="my-8 border-t border-gray-100 dark:border-gray-800"></div>
		<MemorySettings {saveSettings} />
	</div>
</div>
