<script lang="ts">
	import { tick } from 'svelte';
	import { pinnedModels } from '$lib/stores';
	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import {
		effortLevels,
		selectedEffort,
		selectEffort,
		supportedEfforts,
		type ChatParams,
		type Effort
	} from '../effort';
	import { chooseModel, effortDescriptions, menuItems, type ModelMenuItem } from '../model-menu';
	export let items: ModelMenuItem[] = [];
	export let values: string[] = [];
	export let params: ChatParams = {};
	export let disabled = false;
	export let compareEnabled = false;
	export let multipleEnabled = false;
	export let showSetDefault = false;
	export let activeModelId: string | undefined = undefined;
	export let onModelSelect: () => void = () => {};
	export let onSetDefault: () => Promise<void> | void = () => {};
	export let pinModelHandler: (id: string) => void = () => {};
	let show = false;
	let search = '';
	let activeId = '';
	let panel: HTMLDivElement;
	let trigger: HTMLButtonElement;
	let dropdown: Dropdown;
	$: visible = menuItems(items, search, $pinnedModels);
	$: effectiveValues = activeModelId ? [activeModelId] : values;
	$: current = items.find((item) => item.value === (activeModelId ?? values[0]));
	$: active = visible.find((item) => item.value === activeId);
	$: allowed = supportedEfforts(active?.model);
	$: currentEffort = selectedEffort(current?.model, params);
	$: if (!show) {
		activeId = '';
		search = '';
	}
	$: if (disabled && show) show = false;
	export async function open() {
		if (!disabled && !show) {
			trigger?.click();
			await tick();
			panel?.focus();
		}
	}
	async function reveal(item: ModelMenuItem, focus = false) {
		activeId = item.value;
		await tick();
		if (focus) panel?.querySelector<HTMLButtonElement>('[data-effort]:not(:disabled)')?.focus();
	}
	function selectModel(item: ModelMenuItem) {
		values = chooseModel(values, item.value, compareEnabled);
		onModelSelect();
	}
	async function selectLevel(item: ModelMenuItem, effort: Effort) {
		selectModel(item);
		params = selectEffort(params, item.model, effort);
		dropdown?.close();
		await tick();
		trigger?.focus();
	}
	async function back() {
		const previous = activeId;
		activeId = '';
		await tick();
		panel
			?.querySelector<HTMLButtonElement>(
				`[data-model-index="${visible.findIndex((item) => item.value === previous)}"]`
			)
			?.focus();
	}
	function navigate(event: KeyboardEvent) {
		const target = event.target as HTMLElement;
		if (event.key === 'ArrowLeft' || (event.key === 'Escape' && active)) {
			event.preventDefault();
			event.stopPropagation();
			void back();
			return;
		}
		const modelIndex = target.dataset.modelIndex;
		if (event.key === 'ArrowRight' && modelIndex !== undefined) {
			event.preventDefault();
			void reveal(visible[Number(modelIndex)], true);
			return;
		}
		if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
		if (target instanceof HTMLInputElement && event.key !== 'ArrowDown') return;
		const inEffort = target.hasAttribute('data-effort');
		const selector = inEffort ? '[data-effort]:not(:disabled)' : '[data-model-index]';
		const buttons = [...panel.querySelectorAll<HTMLButtonElement>(selector)];
		if (!buttons.length) return;
		event.preventDefault();
		const index = buttons.indexOf(target as HTMLButtonElement);
		const next =
			event.key === 'Home'
				? 0
				: event.key === 'End'
					? buttons.length - 1
					: (index + (event.key === 'ArrowUp' ? -1 : 1) + buttons.length) % buttons.length;
		buttons[next]?.focus();
	}
</script>

<Dropdown
	bind:this={dropdown}
	bind:show
	side="top"
	align="end"
	visualViewportAware={true}
	contentClass="kakam-cascade-popup"
	maxHeight="min(32rem, calc(100dvh - 2rem))"
>
	<button
		bind:this={trigger}
		id="model-selector-model-button"
		type="button"
		class="model-pill"
		{disabled}
		aria-label="选择模型与思考强度"
		aria-haspopup="menu"
		aria-expanded={show}
	>
		<span class="model-name"
			>{current?.label || '选择模型'}{!activeModelId && values.length > 1
				? ` +${values.length - 1}`
				: ''}</span
		>
		<span class="pill-effort">{currentEffort}</span><span aria-hidden="true">⌄</span>
	</button>
	<div
		slot="content"
		class="cascade"
		bind:this={panel}
		role="menu"
		tabindex="-1"
		aria-label="模型与思考强度"
		on:keydown={navigate}
	>
		<div class="models-panel" class:hidden={!!active}>
			<div class="menu-heading">选择模型</div>
			<input type="search" aria-label="搜索模型" placeholder="搜索模型…" bind:value={search} />
			<div class="model-list" role="group" aria-label="模型">
				{#each visible as item, index (item.value)}
					<div class="model-row" class:previewing={activeId === item.value}>
						<button
							type="button"
							role="menuitem"
							data-model-index={index}
							aria-haspopup="menu"
							aria-expanded={activeId === item.value}
							aria-current={effectiveValues.includes(item.value) ? 'true' : undefined}
							on:click={() => {
								void reveal(item, true);
							}}
						>
							<span class="check" aria-hidden="true"
								>{effectiveValues.includes(item.value) ? '✓' : ''}</span
							>
							<span class="item-copy"
								><span class="item-label">{item.label}</span><span class="description"
									>{item.model.info?.meta?.description || item.value}</span
								></span
							>
							<span class="chevron" aria-hidden="true">›</span>
						</button>
						{#if compareEnabled && values.includes(item.value) && values.length > 1}
							<button
								class="aux"
								type="button"
								aria-label={`移除 ${item.label}`}
								on:click={() => {
									values = values.filter((id) => id !== item.value);
								}}>−</button
							>
						{/if}
						<button
							class="aux"
							type="button"
							aria-label={`${$pinnedModels.includes(item.value) ? '取消固定' : '固定'} ${item.label}`}
							aria-pressed={$pinnedModels.includes(item.value)}
							on:click={() => pinModelHandler(item.value)}
							>{$pinnedModels.includes(item.value) ? '★' : '☆'}</button
						>
					</div>
				{/each}
				{#if !visible.length}<p class="empty">
						{items.length ? '没有匹配的模型' : '暂无可用模型，请先在设置中配置云端连接。'}
					</p>{/if}
			</div>
			<div class="menu-footer">
				{#if multipleEnabled}<label
						><input
							type="checkbox"
							checked={compareEnabled}
							on:change={(event) => {
								compareEnabled = event.currentTarget.checked;
								if (!compareEnabled) values = values.slice(0, 1);
							}}
						/>比较模型</label
					>{/if}
				{#if showSetDefault}<button
						type="button"
						disabled={!values.some(Boolean)}
						on:click={onSetDefault}>设为默认</button
					>{/if}
			</div>
		</div>
		{#if active}
			<div class="effort-panel" role="group" aria-label={`${active.label} 的思考强度`}>
				<button class="back" type="button" on:click={back}>‹ 返回模型</button>
				<div class="menu-heading">思考强度<span class="description">{active.label}</span></div>
				{#each effortLevels as level}
					{@const enabled = allowed.length ? allowed.includes(level) : level === 'none'}
					<button
						type="button"
						role="menuitemradio"
						data-effort={level}
						aria-checked={selectedEffort(active.model, params) === level}
						disabled={!enabled}
						on:click={() => selectLevel(active, level)}
					>
						<span class="check" aria-hidden="true"
							>{selectedEffort(active.model, params) === level ? '✓' : ''}</span
						>
						<span class="item-copy"
							><span class="item-label">{level}</span><span class="description"
								>{!allowed.length && level === 'none'
									? '此模型不附加思考强度参数'
									: enabled
										? effortDescriptions[level]
										: '此模型不支持'}</span
							></span
						>
					</button>
				{/each}
			</div>
		{/if}
	</div>
</Dropdown>

<style>
	.model-pill {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		max-width: 100%;
		min-height: 2.25rem;
		padding: 0.45rem 0.75rem;
		border-radius: 999px;
		background: rgb(128 128 128 / 0.09);
		font-size: 0.8125rem;
		color: inherit;
	}
	.model-name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.pill-effort {
		flex-shrink: 0;
		color: var(--kakam-muted);
		font-size: 0.75rem;
		padding-left: 0.5rem;
		border-left: 1px solid var(--kakam-border);
	}
	button:focus-visible,
	input:focus-visible {
		outline: 2px solid #808080;
		outline-offset: -2px;
	}
	button:disabled {
		opacity: 0.4;
		cursor: default;
	}
	:global(.kakam-cascade-popup) {
		z-index: 60;
		overflow: auto !important;
		width: min(21rem, calc(100vw - 1rem));
		border: 1px solid var(--kakam-border);
		border-radius: 1.125rem;
		background: #fff;
		color: var(--kakam-text);
		box-shadow: 0 12px 40px rgb(0 0 0 / 0.15);
		max-width: calc(100vw - 1rem);
	}
	:global(.dark .kakam-cascade-popup) {
		background: #252525;
	}
	.cascade {
		display: flex;
		width: 100%;
		height: min(29rem, 65dvh);
		max-width: calc(100vw - 1rem);
		outline: none;
	}
	.models-panel {
		display: flex;
		flex-direction: column;
		width: 100%;
		min-width: 0;
		flex-shrink: 0;
		padding: 0.5rem;
	}
	.menu-heading {
		font-size: 0.875rem;
		font-weight: 600;
		padding: 0.6rem;
	}
	input[type='search'] {
		width: 100%;
		padding: 0.65rem 0.75rem;
		border-radius: 0.75rem;
		background: var(--kakam-surface);
		font-size: 0.875rem;
		margin-bottom: 0.5rem;
	}
	.model-list {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}
	.model-row {
		display: flex;
		align-items: center;
		border-radius: 0.75rem;
	}
	.model-row:hover,
	.model-row.previewing,
	.effort-panel button:not(:disabled):hover {
		background: rgb(128 128 128 / 0.1);
	}
	.model-row > button:first-child,
	.effort-panel > button {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		text-align: left;
		width: 100%;
		min-width: 0;
		padding: 0.7rem 0.4rem;
		border-radius: 0.75rem;
		min-height: 2.75rem;
	}
	.item-copy {
		display: flex;
		flex-direction: column;
		min-width: 0;
		gap: 0.2rem;
	}
	.item-label {
		font-size: 0.875rem;
		overflow-wrap: anywhere;
	}
	.description {
		display: block;
		font-size: 0.6875rem;
		font-weight: 400;
		color: var(--kakam-muted);
		line-height: 1.45;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 100%;
	}
	.check {
		width: 1rem;
		flex-shrink: 0;
		text-align: center;
	}
	.chevron {
		margin-left: auto;
		color: var(--kakam-muted);
	}
	.aux {
		flex-shrink: 0;
		width: 1.75rem;
		min-height: 2.75rem;
		color: var(--kakam-muted);
	}
	.menu-footer {
		border-top: 1px solid var(--kakam-border);
		margin-top: 0.5rem;
		padding: 0.75rem 0.5rem 0.25rem;
		display: flex;
		gap: 1rem;
		align-items: center;
		justify-content: space-between;
		font-size: 0.75rem;
	}
	.menu-footer label {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.effort-panel {
		flex: 1;
		min-width: 0;
		overflow-y: auto;
		padding: 0.5rem;
	}
	.models-panel.hidden {
		display: none;
	}
	.effort-panel .back {
		display: flex;
		font-size: 0.875rem;
		padding-left: 0.75rem;
	}
	.empty {
		padding: 1rem;
		font-size: 0.875rem;
		color: var(--kakam-muted);
	}
	@media (max-width: 639px) {
		.model-pill {
			min-height: 2.75rem;
		}
		input[type='search'] {
			font-size: 1rem;
		}
		.aux {
			width: 2.5rem;
		}
	}
</style>
