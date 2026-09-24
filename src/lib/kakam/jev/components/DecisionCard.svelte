<script lang="ts">
	import type { Answer, QuestionDisplay } from '../types';
	import { answerRows, probability } from '../service';
	export let answer: Answer;
	export let display: QuestionDisplay;
	$: rows = answerRows(answer, display);
	$: maxScore = answer.type === 'score' ? Object.keys(answer.legend).length - 1 : 1;
	$: typeLabel =
		answer.type === 'choice' ? '选项判断' : answer.type === 'score' ? '量表评分' : '是非判断';
</script>

<article
	class="decision"
	class:choice={answer.type === 'choice'}
	class:score={answer.type === 'score'}
	class:noul={answer.type === 'noul'}
	aria-label={display.title}
>
	<div class="eyebrow">
		<span class="type">{answer.type}</span><span>{typeLabel}</span>
		{#if answer.type !== 'noul' && answer.confidence !== undefined}<span
				class="confidence"
				title="Jev 根据概率分布计算的置信度，与单个选项的概率不同"
				>置信度 {probability(answer.confidence)}</span
			>{/if}
	</div>
	<h3>{display.title}</h3>
	{#if answer.type === 'choice'}
		<div class="choice-result">
			<span class="result-label">Jev 的选择</span><strong
				>{display.options[answer.choice] || answer.choice}</strong
			><span class="chosen-probability"
				>{probability(answer.probabilities[answer.choice])}<small>选项概率</small></span
			>
		</div>
	{:else if answer.type === 'score'}
		<div class="score-result">
			<strong title={String(answer.score)}>{Number(answer.score.toFixed(2))}</strong><span
				>/ {maxScore}<small>量表范围 0–{maxScore}</small></span
			>
		</div>
		<div class="scale" aria-hidden="true">
			<div class="scale-track">
				<span style:left={`${(answer.score / maxScore) * 100}%`}></span>
			</div>
			<div class="scale-labels"><span>0</span><span>{maxScore}</span></div>
		</div>
	{:else}
		<div class="noul-result">
			<div
				class="ring"
				style:background={`conic-gradient(var(--accent) ${answer.noul * 100}%, var(--kakam-border) 0)`}
			>
				<div><strong>{probability(answer.noul)}</strong><span>是的概率</span></div>
			</div>
			<div class="noul-verdict">
				<span class="result-label">Jev 的判断</span><strong
					>{answer.noul === 0.5 ? '暂不确定' : answer.noul > 0.5 ? '倾向是' : '倾向否'}</strong
				><span
					>{answer.noul === 0.5
						? '是与否的概率相同'
						: display.options[answer.noul > 0.5 ? 'true' : 'false']}</span
				>
			</div>
		</div>
	{/if}
	<div class="distribution" aria-label="概率分布">
		{#each rows as row}
			<div class="distribution-row">
				<div class="row-label">
					<span
						>{#if answer.type === 'score'}<b>{row.key}</b>{/if}{row.label}</span
					><strong title={String(row.value)}>{probability(row.value)}</strong>
				</div>
				<div
					class="track"
					role="meter"
					aria-label={row.label}
					aria-valuemin={0}
					aria-valuemax={100}
					aria-valuenow={row.value * 100}
					aria-valuetext={probability(row.value)}
				>
					<span style:width={`${row.value * 100}%`}></span>
				</div>
			</div>
		{/each}
	</div>
	{#if answer.type === 'score'}<p class="footnote">
			分数是各等级位置的概率加权值；每一级的含义见上方量表。
		</p>{/if}
</article>

<style>
	.decision {
		--accent: #059669;
		border: 1px solid var(--kakam-border);
		border-radius: 1.2rem;
		padding: 1.25rem 1.4rem;
		background: var(--jev-card, #fff);
		overflow: hidden;
	}
	.score {
		--accent: #6c75df;
	}
	.noul {
		--accent: #138b9e;
	}
	:global(.dark) .decision {
		--jev-card: #1d1d1f;
	}
	.eyebrow {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--kakam-muted);
		font-size: 0.66rem;
	}
	.type {
		font-size: 0.62rem;
		text-transform: uppercase;
		letter-spacing: 0.09em;
		font-weight: 600;
		color: var(--accent);
		border: 1px solid var(--kakam-border);
		border-radius: 0.35rem;
		padding: 0.15rem 0.35rem;
	}
	.confidence {
		margin-left: auto;
		font-variant-numeric: tabular-nums;
	}
	h3 {
		font-size: 0.98rem;
		font-weight: 500;
		line-height: 1.7;
		margin: 0.9rem 0 1rem;
		overflow-wrap: anywhere;
	}
	.result-label {
		font-size: 0.7rem;
		color: var(--kakam-muted);
	}
	.choice-result {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.3rem 1rem;
		margin: 1rem 0 1.3rem;
	}
	.choice-result > strong {
		grid-column: 1;
		font-size: 1.4rem;
		font-weight: 600;
		letter-spacing: -0.025em;
		line-height: 1.4;
		overflow-wrap: anywhere;
	}
	.chosen-probability {
		grid-column: 2;
		grid-row: 1 / 3;
		align-self: center;
		text-align: right;
		font-size: 1.3rem;
		font-variant-numeric: tabular-nums;
		color: var(--accent);
	}
	small {
		display: block;
		font-size: 0.63rem;
		font-weight: 400;
		color: var(--kakam-muted);
		margin-top: 0.2rem;
		letter-spacing: 0;
	}
	.score-result {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		margin-top: 0.2rem;
	}
	.score-result > strong {
		font-size: 2.65rem;
		font-weight: 500;
		line-height: 1.2;
		letter-spacing: -0.06em;
	}
	.score-result > span {
		color: var(--kakam-muted);
		font-size: 1rem;
	}
	.scale {
		margin: 1.2rem 0.2rem 1rem;
	}
	.scale-track {
		height: 0.4rem;
		border-radius: 2rem;
		background: linear-gradient(90deg, #6c75df20, #6c75df99);
		position: relative;
	}
	.scale-track > span {
		position: absolute;
		top: -0.25rem;
		width: 0.9rem;
		height: 0.9rem;
		border-radius: 50%;
		background: var(--accent);
		border: 2px solid var(--jev-card, #fff);
		transform: translateX(-50%);
	}
	.scale-labels {
		display: flex;
		justify-content: space-between;
		font-size: 0.65rem;
		margin-top: 0.5rem;
		color: var(--kakam-muted);
	}
	.noul-result {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		margin: 0.5rem 0 1.4rem;
	}
	.ring {
		width: 6rem;
		height: 6rem;
		padding: 0.4rem;
		border-radius: 50%;
		flex: none;
	}
	.ring > div {
		height: 100%;
		border-radius: 50%;
		background: var(--jev-card, #fff);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
	}
	.ring strong {
		font-size: 1.05rem;
		font-variant-numeric: tabular-nums;
	}
	.ring span {
		font-size: 0.6rem;
		color: var(--kakam-muted);
		margin-top: 0.2rem;
	}
	.noul-verdict {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 0;
	}
	.noul-verdict strong {
		font-size: 1.4rem;
		font-weight: 600;
	}
	.noul-verdict > span:last-child {
		font-size: 0.75rem;
		color: var(--kakam-muted);
		overflow-wrap: anywhere;
	}
	.distribution {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
		max-height: 24rem;
		overflow-y: auto;
		padding-right: 0.15rem;
	}
	.row-label {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
		font-size: 0.75rem;
		margin-bottom: 0.35rem;
		line-height: 1.6;
	}
	.row-label > span {
		overflow-wrap: anywhere;
	}
	.row-label b {
		font-weight: 400;
		color: var(--kakam-muted);
		margin-right: 0.5rem;
	}
	.row-label strong {
		flex-shrink: 0;
		font-weight: 500;
		font-size: 0.7rem;
		font-variant-numeric: tabular-nums;
	}
	.track {
		height: 0.3rem;
		border-radius: 1rem;
		background: var(--kakam-border);
		overflow: hidden;
	}
	.track > span {
		display: block;
		height: 100%;
		background: var(--accent);
		border-radius: inherit;
	}
	.footnote {
		font-size: 0.64rem;
		color: var(--kakam-muted);
		line-height: 1.6;
		margin-top: 1rem;
	}
	@media (max-width: 480px) {
		.decision {
			padding: 1rem;
		}
		.confidence {
			font-size: 0.6rem;
		}
		.choice-result > strong {
			font-size: 1.2rem;
		}
	}
</style>
