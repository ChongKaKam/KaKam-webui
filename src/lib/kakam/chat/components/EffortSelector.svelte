<script lang="ts">
	import { models } from '$lib/stores';
	import {
		effortLevels,
		selectedEffort,
		selectEffort,
		supportedEfforts,
		type ChatParams
	} from '../effort';
	export let modelIds: string[] = [];
	export let params: ChatParams = {};
	export let disabled = false;
	$: selected = modelIds.map((id) => $models.find((model) => model.id === id)).filter(Boolean);
	$: allowed = effortLevels.filter(
		(level) =>
			selected.length > 0 && selected.every((model) => supportedEfforts(model).includes(level))
	);
	$: values = selected.map((model) => selectedEffort(model, params));
	$: mixed = new Set(values).size > 1;
	$: value = mixed ? '' : (values[0] ?? 'none');
	$: hint = !allowed.length
		? selected.length > 1
			? '所选模型没有共同的思考强度选项；每个请求使用对应模型的有效值。'
			: '此模型不支持可调思考强度；请求中不附加该参数。'
		: '思考强度 · 更高强度可能需要更长时间';
</script>

<label class="kakam-effort" title={hint}>
	<span class="sr-only">思考强度 (Effort)</span>
	<select
		aria-label="思考强度 (Effort)"
		{value}
		disabled={disabled || !allowed.length}
		on:change={(event) => {
			for (const model of selected)
				if (model) params = selectEffort(params, model, event.currentTarget.value);
		}}
	>
		{#if mixed}<option value="" disabled>按模型</option>{/if}
		{#each effortLevels as level}<option value={level} disabled={!allowed.includes(level)}
				>{level}</option
			>{/each}
	</select>
</label>

<style>
	.kakam-effort {
		display: flex;
		align-items: center;
		flex-shrink: 0;
	}
	select {
		max-width: 7.5rem;
		min-height: 2.25rem;
		border: 0;
		border-radius: 0.75rem;
		background-color: transparent;
		color: inherit;
		padding: 0.35rem 1.25rem 0.35rem 0.5rem;
		font-size: 0.8125rem;
		cursor: pointer;
	}
	select:hover {
		background-color: rgb(128 128 128 / 0.08);
	}
	select:focus-visible {
		outline: 2px solid #64748b;
		outline-offset: 2px;
	}
	select:disabled {
		opacity: 0.5;
		cursor: default;
	}
	@media (max-width: 640px) {
		select {
			min-height: 2.75rem;
			max-width: 7.5rem;
			font-size: 1rem;
		}
	}
</style>
