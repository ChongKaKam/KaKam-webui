<script lang="ts">
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import Play from '$lib/components/icons/Play.svelte';
	import DocumentDuplicate from '$lib/components/icons/DocumentDuplicate.svelte';
	import ChevronUpDown from '$lib/components/icons/ChevronUpDown.svelte';
	export let language = '';
	export let collapsed = false;
	export let editing = false;
	export let editable = true;
	export let saveToChat = false;
	export let executing = false;
	export let runnable = false;
	export let previewable = false;
	export let copied = false;
	export let saved = false;
	export let onCollapse: () => void;
	export let onRun: () => void;
	export let onSave: () => void;
	export let onCopy: () => void;
	export let onPreview: () => void;
	function toggleEdit() {
		if (editing) onSave();
		else if (collapsed) onCollapse();
		editing = !editing;
	}
</script>

<span class="language" title={language}>{language || '代码'}</span>
<div class="actions" role="group" aria-label="代码操作">
	<button
		type="button"
		aria-label={collapsed ? '展开代码' : '折叠代码'}
		title={collapsed ? '展开代码' : '折叠代码'}
		aria-expanded={!collapsed}
		on:click={onCollapse}><ChevronUpDown className="size-4" /></button
	>
	{#if runnable || executing}
		<button
			type="button"
			aria-label={executing ? '运行中' : '运行代码'}
			title={executing ? '运行中' : '运行代码'}
			disabled={executing}
			on:click={onRun}
		>
			{#if executing}<span class="spinner" aria-hidden="true"></span>{:else}<Play />{/if}
		</button>
	{/if}
	{#if editable}
		<button
			type="button"
			class="edit-save"
			aria-label={editing ? (saveToChat ? '保存修改' : '完成编辑') : '编辑代码'}
			title={editing ? (saveToChat ? '保存修改' : '完成编辑') : '编辑代码'}
			aria-pressed={editing}
			on:click={toggleEdit}
		>
			{#if editing}
				<svg
					aria-hidden="true"
					width="18"
					height="18"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="1.5"
					stroke-linejoin="round"><path d="M5 3h12l4 4v14H3V3h2Z M7 3v6h10V3 M7 21v-8h10v8" /></svg
				>
			{:else if saved}<Check />{:else}<Pencil />{/if}
		</button>
	{/if}
	<button
		type="button"
		class="copy-code-button"
		aria-label={copied ? '已复制代码' : '复制代码'}
		title={copied ? '已复制代码' : '复制代码'}
		on:click={onCopy}
		>{#if copied}<Check />{:else}<DocumentDuplicate />{/if}</button
	>
	{#if previewable}<button type="button" aria-label="预览代码" title="预览代码" on:click={onPreview}
			><svg
				aria-hidden="true"
				width="18"
				height="18"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="1.5"
				><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" /><circle
					cx="12"
					cy="12"
					r="3"
				/></svg
			></button
		>{/if}
	<span class="sr-only" role="status"
		>{copied ? '已复制代码' : saved ? '修改已保存' : executing ? '正在运行代码' : ''}</span
	>
</div>

<style>
	.language {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.875rem;
	}
	.actions {
		display: flex;
		gap: 0.125rem;
		flex-shrink: 0;
		align-items: center;
	}
	button {
		display: grid;
		place-items: center;
		width: 2.25rem;
		min-height: 2.25rem;
		border-radius: 0.65rem;
	}
	button:focus-visible {
		outline: 2px solid currentColor;
		outline-offset: -2px;
	}
	button:disabled {
		opacity: 0.5;
		cursor: wait;
	}
	.spinner {
		width: 1rem;
		height: 1rem;
		border: 2px solid currentColor;
		border-right-color: transparent;
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	@media (pointer: coarse) {
		button {
			width: 2.75rem;
			min-height: 2.75rem;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.spinner {
			animation: none;
		}
	}
</style>
