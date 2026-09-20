<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { settings } from '$lib/stores';
	import { highlight } from '../highlight';
	import { normalizeCodeTheme, type CodeTheme } from '../themes';
	export let code = '';
	export let language = '';
	export let theme: CodeTheme | undefined = undefined;
	let mounted = false;
	let html: string | null = null;
	let timer: ReturnType<typeof setTimeout>;
	let version = 0;
	$: selectedTheme = normalizeCodeTheme(theme ?? $settings?.kakamCodeTheme);
	$: if (mounted) schedule(code, language, selectedTheme);
	function schedule(source: string, lang: string, style: CodeTheme) {
		const request = ++version;
		clearTimeout(timer);
		html = null;
		// Coalesce streaming chunks. Plain text stays visible while highlighting catches up.
		timer = setTimeout(async () => {
			try {
				const result = await highlight(source, lang, style);
				if (request === version) html = result;
			} catch {
				if (request === version) html = null;
			}
		}, 100);
	}
	onMount(() => {
		mounted = true;
	});
	onDestroy(() => {
		version++;
		clearTimeout(timer);
	});
</script>

<div class="kakam-shiki" data-code-theme={selectedTheme}>
	{#if html}
		<!-- Shiki serializes escaped code with bundled grammars/themes; no user HTML or transformers. -->
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		{@html html}
	{:else}<pre><code>{code}</code></pre>{/if}
</div>

<style>
	.kakam-shiki {
		min-width: 0;
	}
	.kakam-shiki :global(pre) {
		margin: 0;
		padding: 1.25rem;
		overflow-x: auto;
		tab-size: 4;
		background: var(--kakam-surface);
		color: var(--kakam-text);
	}
	.kakam-shiki :global(pre code) {
		display: block;
		font-family: var(--kakam-mono);
		font-size: 0.875rem;
		line-height: 1.7;
		white-space: pre;
		overflow-wrap: normal;
		word-break: normal;
	}
	:global(.dark) .kakam-shiki :global(.shiki),
	:global(.dark) .kakam-shiki :global(.shiki span) {
		color: var(--shiki-dark) !important;
		background-color: var(--shiki-dark-bg) !important;
		font-style: var(--shiki-dark-font-style) !important;
		font-weight: var(--shiki-dark-font-weight) !important;
		text-decoration: var(--shiki-dark-text-decoration) !important;
	}
	@media (max-width: 767px) {
		.kakam-shiki :global(pre) {
			padding: 1rem;
		}
	}
</style>
