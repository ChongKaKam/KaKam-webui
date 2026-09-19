<script lang="ts">
	import { onMount } from 'svelte';
	import { getMemoryActivity } from '../api';
	import { labels } from '../service';
	import {
		activityCalendar,
		dayColor,
		proportions,
		segmentColors,
		segmentKinds
	} from '../activity';
	import type { MemoryActivity as Activity, MemoryActivityDay, SegmentKind } from '../types';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	let activity: Activity | null = null;
	let days = 180;
	let filter: SegmentKind | 'all' = 'all';
	const filters: (SegmentKind | 'all')[] = ['all', ...segmentKinds];
	let selectedDate: string | null = null;
	let loading = true;
	let error = '';
	let requestVersion = 0;
	$: calendar = activityCalendar(activity?.heatmap ?? []);
	$: selected = activity?.heatmap.find((d) => d.date === selectedDate);
	$: shares = activity ? proportions(selected?.characters ?? activity.characters) : [];
	$: total = shares.reduce((sum, item) => sum + item.characters, 0);
	$: requests = selected?.requests ?? activity?.requests ?? 0;

	async function load() {
		const version = ++requestVersion;
		loading = true;
		error = '';
		selectedDate = null;
		try {
			const result = await getMemoryActivity(days);
			if (version === requestVersion) activity = result;
		} catch (e) {
			if (version === requestVersion) {
				activity = null;
				error = String(e);
			}
		} finally {
			if (version === requestVersion) loading = false;
		}
	}

	function tooltip(day: MemoryActivityDay): string {
		if (!day.requests) return `${day.date} UTC · 无已保存的 Prompt 统计`;
		return `${day.date} UTC · ${day.requests} 次请求\n${proportions(day.characters)
			.map(
				(s) => `${labels[s.kind]} ${s.percent.toFixed(1)}%（${s.characters.toLocaleString()} 字符）`
			)
			.join('\n')}`;
	}
	onMount(() => {
		void load();
		return () => {
			requestVersion++;
		};
	});
</script>

<section aria-label="记忆占比活动" class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-3">
		<h3 class="text-xs font-medium text-gray-900 dark:text-white">记忆占比</h3>
		<div class="flex items-center gap-3 text-xs text-gray-500">
			<label class="flex items-center gap-2"
				>统计周期
				<select
					class="rounded-lg bg-gray-50 px-2 py-1 dark:bg-gray-850"
					bind:value={days}
					on:change={load}
				>
					{#each [7, 30, 90, 180] as period}<option value={period}>最近 {period} 天</option>{/each}
				</select>
			</label>
			<button
				type="button"
				on:click={load}
				disabled={loading}
				class="hover:text-gray-900 disabled:opacity-40 dark:hover:text-white">刷新</button
			>
		</div>
	</div>
	{#if loading}
		<div class="flex h-48 items-center justify-center" role="status" aria-label="正在加载记忆占比">
			<Spinner className="size-5" />
		</div>
	{:else if error}
		<div class="rounded-xl bg-red-50 p-3 text-xs text-red-600 dark:bg-red-950/20" role="alert">
			无法读取记忆活动：{error}
			<button type="button" class="underline" on:click={load}>重试</button>
		</div>
	{:else if activity}
		<div class="flex flex-wrap items-center justify-between gap-2 text-[0.6875rem] text-gray-500">
			<span
				>{selectedDate ?? `最近 ${activity.days} 天`} · {requests.toLocaleString()} 次已记录请求 · {total.toLocaleString()}
				字符</span
			>
			{#if selectedDate}<button
					type="button"
					class="underline"
					on:click={() => (selectedDate = null)}>返回整个周期</button
				>{/if}
		</div>
		<div class="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-4">
			{#each shares as segment}
				<div>
					<div class="text-lg font-medium tabular-nums text-gray-900 dark:text-white">
						{total ? `${segment.percent.toFixed(1)}%` : '—'}
					</div>
					<div class="mt-1 flex items-center gap-1.5 text-[0.6875rem] text-gray-500">
						<span class="size-2 rounded-sm" style:background={segmentColors[segment.kind]}
						></span>{labels[segment.kind]}
					</div>
					<div class="mt-0.5 text-[0.6875rem] tabular-nums text-gray-400">
						{segment.characters.toLocaleString()} 字符
					</div>
				</div>
			{/each}
		</div>
		<div
			class="flex h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800"
			role="img"
			aria-label={shares.map((s) => `${labels[s.kind]} ${s.percent.toFixed(1)}%`).join('，')}
		>
			{#each shares as segment}<span
					style:width={`${segment.percent}%`}
					style:background={segmentColors[segment.kind]}
					title={`${labels[segment.kind]} ${segment.percent.toFixed(1)}%`}
				></span>{/each}
		</div>
		<div>
			<div class="mb-3 flex flex-wrap items-center justify-between gap-3">
				<h4 class="text-xs text-gray-400 dark:text-gray-500">Memory 活动</h4>
				<div class="flex flex-wrap gap-x-3 gap-y-2 text-[0.6875rem]">
					{#each filters as kind}
						<button
							type="button"
							aria-pressed={filter === kind}
							class={filter === kind
								? 'text-gray-900 dark:text-white'
								: 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}
							on:click={() => (filter = kind as SegmentKind | 'all')}
							>{kind === 'all' ? '全部' : labels[kind]}</button
						>
					{/each}
				</div>
			</div>
			<div
				class="calendar"
				style:--columns={calendar.columns}
				style:max-width={`${calendar.columns * 14 - 4}px`}
			>
				{#each calendar.cells as day}
					{#if day}
						{@const color = dayColor(day, filter)}
						<Tooltip content={tooltip(day)}>
							<button
								type="button"
								class="day bg-gray-100 dark:bg-gray-800"
								class:selected={selectedDate === day.date}
								aria-label={tooltip(day)}
								aria-pressed={selectedDate === day.date}
								style:background-color={color.color ?? undefined}
								style:opacity={color.color ? color.opacity : 1}
								on:click={() => (selectedDate = selectedDate === day.date ? null : day.date)}
							></button>
						</Tooltip>
					{:else}<span></span>{/if}
				{/each}
			</div>
			<div
				class="mx-auto mt-2 grid text-[0.6875rem] text-gray-400"
				style:max-width={`${calendar.columns * 14 - 4}px`}
				style:grid-template-columns={`repeat(${calendar.columns}, minmax(0, 1fr))`}
				style:gap="4px"
			>
				{#each calendar.months as month}<span
						class="whitespace-nowrap"
						style:grid-column={`${month.column + 1} / span ${Math.min(3, calendar.columns - month.column)}`}
						>{month.label}</span
					>{/each}
			</div>
			<div
				class="mt-3 flex flex-wrap items-center justify-between gap-2 text-[0.6875rem] text-gray-400"
			>
				<span>每格一天（UTC）· 点击查看当天占比</span>
				<span>浅 → 深：{filter === 'all' ? '当天占比最高的类型' : labels[filter]}占比增大</span>
			</div>
		</div>
		{#if !activity.requests}<p
				role="status"
				class="rounded-xl bg-gray-50 p-3 text-xs text-gray-500 dark:bg-gray-850"
			>
				暂无已保存的 Prompt 统计。启用 Memory 后完成一次普通对话，再刷新查看；旧对话不会自动补算。
			</p>{/if}
		{#if activity.truncated}<p role="status" class="text-xs text-amber-600">
				记录较多，本页只统计所选周期中最新 5000 条候选响应内的有效快照，不代表完整用量。
			</p>{/if}
		<p class="text-[0.6875rem] leading-relaxed text-gray-400">
			占比 = 各类文本字符数 ÷ 已记录 Prompt 总字符数，按文本量加权，非计费
			Token。统计周期与长期记忆保留窗口独立；不含临时对话、图片、工具 schema 或供应商追加内容。
		</p>
	{/if}
</section>

<style>
	.calendar {
		display: grid;
		grid-auto-flow: column;
		grid-template-columns: repeat(var(--columns), minmax(0, 1fr));
		grid-template-rows: repeat(7, minmax(0, 1fr));
		gap: 4px;
		aspect-ratio: var(--columns) / 7;
		margin: 0 auto;
		width: 100%;
	}
	.day {
		display: block;
		width: 100%;
		height: 100%;
		border-radius: 2px;
		transition: opacity 0.15s;
	}
	.day:hover {
		outline: 1px solid #64748b;
		outline-offset: 2px;
	}
	.day.selected,
	.day:focus-visible {
		outline: 2px solid #64748b;
		outline-offset: 2px;
	}
</style>
