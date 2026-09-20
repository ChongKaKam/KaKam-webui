<script lang="ts">
	import CodeHighlight from './CodeHighlight.svelte';
	import { codeThemes, normalizeCodeTheme, type CodeTheme } from '../themes';
	export let value: unknown = 'github';
	export let save: (value: { kakamCodeTheme: CodeTheme }) => unknown;
	$: selected = normalizeCodeTheme(value);
	let error = '';
	async function change(event: Event) {
		const choice = normalizeCodeTheme((event.currentTarget as HTMLSelectElement).value);
		selected = choice;
		error = '';
		try {
			await save({ kakamCodeTheme: choice });
		} catch {
			error = '保存失败，请重试。';
		}
	}
</script>

<section class="code-style" aria-label="代码块样式">
	<div class="heading">
		<div>
			<h3>代码块样式</h3>
			<p>配色跟随明暗模式，应用于聊天中的代码块。</p>
		</div>
		<select aria-label="代码块样式" value={selected} on:change={change}>
			{#each Object.entries(codeThemes) as [id, item]}<option value={id}>{item.label}</option
				>{/each}
		</select>
	</div>
	<p class="description">{codeThemes[selected].description}</p>
	<div class="preview">
		<CodeHighlight
			theme={selected}
			language="typescript"
			code={'// KaKam Cloud\nconst greet = (name: string) => {\n  return `Hello, ${name}!`;\n};'}
		/>
	</div>
	{#if error}<p role="alert">{error}</p>{/if}
</section>

<style>
	.code-style {
		margin-block: 1.25rem;
	}
	.heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}
	h3 {
		font-size: 0.875rem;
		font-weight: 600;
		margin: 0 0 0.25rem;
	}
	p {
		font-size: 0.75rem;
		color: var(--kakam-muted);
	}
	select {
		min-height: 2.75rem;
		border: 1px solid var(--kakam-border);
		border-radius: 0.75rem;
		background: transparent;
		padding: 0.5rem 0.75rem;
		font-size: 1rem;
	}
	.description {
		margin-block: 0.75rem;
	}
	.preview {
		overflow: hidden;
		border: 1px solid var(--kakam-border);
		border-radius: 0.875rem;
	}
</style>
