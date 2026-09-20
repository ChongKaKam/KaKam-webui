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

<section aria-label="记忆占比活动" class="memory-activity space-y-6">
	<div class="flex flex-wrap items-center justify-between gap-3">
		<h3 class="text-base font-semibold text-gray-900 dark:text-white">记忆占比</h3>
		<div class="flex items-center gap-3 text-xs text-gray-500">
			<label class="flex items-center gap-2"
				>统计周期
				<select
					class="min-h-10 rounded-xl border border-gray-200/60 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-850"
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
		<div class="flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500">
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
		<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
			{#each shares as segment}
				<div
					class="rounded-2xl border border-gray-200/60 bg-gray-50/70 p-4 dark:border-gray-700/50 dark:bg-white/[0.025]"
				>
					<div
						class="text-3xl font-semibold tracking-tight tabular-nums text-gray-900 dark:text-white"
					>
						{total ? `${segment.percent.toFixed(1)}%` : '—'}
					</div>
					<div class="mt-1 flex items-center gap-1.5 text-xs text-gray-500">
						<span class="size-2 rounded-sm" style:background={segmentColors[segment.kind]}
						></span>{labels[segment.kind]}
					</div>
					<div class="mt-0.5 text-xs tabular-nums text-gray-400">
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
				<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Memory 活动</h4>
				<div class="flex flex-wrap gap-1 text-xs">
					{#each filters as kind}
						<button
							type="button"
							aria-pressed={filter === kind}
							class={filter === kind
								? 'rounded-lg bg-gray-100 px-3 py-2 text-gray-900 dark:bg-gray-800 dark:text-white'
								: 'rounded-lg px-3 py-2 text-gray-500 hover:bg-gray-50 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200'}
							on:click={() => (filter = kind as SegmentKind | 'all')}
							>{kind === 'all' ? '全部' : labels[kind]}</button
						>
					{/each}
				</div>
			</div>
			<!-- Keyboard users need to focus this region to scroll the wide calendar. -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<div
				class="calendar-scroll"
				tabindex="0"
				role="region"
				aria-label="Memory 活动日历，可横向滚动"
			>
				<div class="calendar-frame" style:--columns={calendar.columns}>
					<div class="calendar">
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
						class="calendar-months mt-3 grid text-xs text-gray-500"
						style:grid-template-columns={`repeat(${calendar.columns}, minmax(0, 1fr))`}
						style:gap="var(--cell-gap)"
					>
						{#each calendar.months as month}<span
								class="whitespace-nowrap"
								style:grid-column={`${month.column + 1} / span ${Math.min(3, calendar.columns - month.column)}`}
								>{month.label}</span
							>{/each}
					</div>
				</div>
			</div>
			<div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-400">
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
		<p class="text-xs leading-relaxed text-gray-400">
			占比 = 各类文本字符数 ÷ 已记录 Prompt 总字符数，按文本量加权，非计费
			Token。统计周期与长期记忆保留窗口独立；不含临时对话、图片、工具 schema 或供应商追加内容。
		</p>
	{/if}
</section>

<style>
	.calendar-scroll {
		overflow-x: auto;
		padding: 6px 3px 12px;
		overscroll-behavior-x: contain;
	}
	.calendar-frame {
		--cell-size: 24px;
		--cell-gap: 6px;
		width: calc(var(--columns) * (var(--cell-size) + var(--cell-gap)) - var(--cell-gap));
		margin-inline: auto;
	}
	@media (max-width: 767px) {
		.calendar-frame {
			--cell-size: 30px;
		}
	}

	.calendar {
		display: grid;
		grid-auto-flow: column;
		grid-template-columns: repeat(var(--columns), var(--cell-size));
		grid-template-rows: repeat(7, var(--cell-size));
		gap: var(--cell-gap);

		margin: 0 auto;
		width: 100%;
	}
	.day {
		display: block;
		width: 100%;
		height: 100%;
		border-radius: 5px;
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
