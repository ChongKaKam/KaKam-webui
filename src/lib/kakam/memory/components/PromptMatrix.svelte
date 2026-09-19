<script lang="ts">
	import type { Composition, SegmentKind } from '../types';
	import { labels, makeCells } from '../service';
	export let report: Composition | null = null;
	let selected: SegmentKind | null = null;
	$: matrix = report ? makeCells(report) : null;
</script>

{#if report && matrix}
	<section class="composition" aria-label="对话 Prompt 组成">
		<div class="heading">
			<span>CONTEXT <span class="muted">/ {report.policy} · {report.model}</span></span>
			<span class="muted"
				>{report.status === 'unavailable'
					? '记忆服务不可用 · 已降级'
					: report.status === 'disabled'
						? '长期记忆关闭'
						: report.status === 'shadow'
							? 'Shadow · 未注入'
							: report.cache_hit
								? '召回缓存命中'
								: '召回缓存未命中'}</span
			>
		</div>
		<div
			class="matrix"
			role="img"
			aria-label={report.segments.map((s) => `${labels[s.kind]} ${s.characters} 字符`).join('，')}
		>
			{#each matrix.cells as cell}
				<span
					class="cell {cell.kind}"
					class:dimmed={selected !== null && selected !== cell.kind}
					title={`${labels[cell.kind]} · ${cell.characters} 字符`}
				></span>
			{/each}
			{#each Array(Math.max(0, 224 - matrix.cells.length)) as _}
				<span class="cell empty"></span>
			{/each}
		</div>
		<div class="legend">
			{#each report.segments as segment}
				<button
					type="button"
					aria-pressed={selected === segment.kind}
					on:click={() => (selected = selected === segment.kind ? null : segment.kind)}
					title={`约 ${segment.estimated_tokens} tokens（文本估算）`}
				>
					<span class="dot {segment.kind}"></span>{labels[segment.kind]}
					<span class="muted">{segment.characters.toLocaleString()}</span>
				</button>
			{/each}
		</div>
		<div class="caption">
			选中响应 · 每格 ≤ {matrix.unit} 字符 · 最近 {report.days} 天 / {report.memory_count} 条记忆
			· 不含图片、工具 schema 及供应商追加内容；非账单 token 或供应商缓存统计
		</div>
	</section>
{/if}

<style>
	.composition {
		margin: 0.5rem 0;
		padding: 0.65rem 0;
		color: #64748b;
	}
	.heading {
		display: flex;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.4rem;
		font:
			10px/1.5 ui-monospace,
			monospace;
		margin-bottom: 0.5rem;
	}
	.muted {
		opacity: 0.7;
	}
	.matrix {
		display: grid;
		grid-template-columns: repeat(32, minmax(0, 1fr));
		gap: 3px;
	}
	.cell {
		display: block;
		aspect-ratio: 1;
		border-radius: 2px;
		max-height: 12px;
		transition: opacity 0.15s;
	}
	.system {
		background: #8b5cf6;
	}
	.long_term {
		background: #10b981;
	}
	.session {
		background: #3b82f6;
	}
	.current {
		background: #f59e0b;
	}
	.empty {
		background: rgba(148, 163, 184, 0.14);
	}
	.dimmed {
		opacity: 0.15;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
		margin-top: 0.5rem;
	}
	.legend button {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 10px;
		border-radius: 3px;
	}
	.legend button:focus-visible {
		outline: 2px solid #94a3b8;
		outline-offset: 3px;
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 2px;
	}
	.caption {
		font-size: 9px;
		margin-top: 0.35rem;
		opacity: 0.7;
	}
	@media (max-width: 480px) {
		.matrix {
			grid-template-columns: repeat(24, minmax(0, 1fr));
		}
	}
</style>
