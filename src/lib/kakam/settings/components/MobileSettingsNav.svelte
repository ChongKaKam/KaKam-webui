<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as I18n } from 'i18next';
	const i18n = getContext<Writable<I18n>>('i18n');
	export let tabs: { id: string; title: string }[] = [];
	export let selectedTab: string;
</script>

<label class="kakam-mobile-settings-nav">
	<span>设置分类</span>
	<select aria-label="设置分类" bind:value={selectedTab}>
		{#each [false, true] as admin}
			{@const group = tabs.filter((tab) => tab.id.startsWith('admin:') === admin)}
			{#if group.length}
				<optgroup label={admin ? $i18n.t('Admin') : $i18n.t('Personal')}>
					{#each group as tab}<option value={tab.id}>{$i18n.t(tab.title)}</option>{/each}
				</optgroup>
			{/if}
		{/each}
	</select>
</label>

<style>
	label {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 0.75rem 0.75rem;
		font-size: 0.875rem;
	}
	span {
		flex-shrink: 0;
		opacity: 0.65;
	}
	select {
		flex: 1;
		min-width: 0;
		min-height: 2.75rem;
		border: 1px solid rgb(128 128 128 / 0.2);
		border-radius: 0.75rem;
		padding: 0.5rem 0.75rem;
		background: transparent;
		font-size: 1rem;
	}
	@media (min-width: 768px) {
		label {
			display: none;
		}
	}
</style>
