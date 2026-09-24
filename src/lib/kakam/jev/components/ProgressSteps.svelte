<script lang="ts">
	import { stageLabels } from '../service';
	import type { Stage } from '../types';
	export let stage: Stage;
	export let clarification = false;
	$: steps = (
		clarification ? ['preparing', 'done'] : ['preparing', 'deciding', 'polishing', 'done']
	) as Stage[];
	$: current = steps.indexOf(stage);
</script>

<div class="progress" aria-live="polite" aria-label={stageLabels[stage]}>
	{#if stage === 'error' || stage === 'cancelled'}
		<span class="stopped">{stageLabels[stage]}</span>
	{:else}
		{#each steps as step, index}
			<span
				class="step"
				class:active={current === index}
				class:complete={index < current || stage === 'done'}
			>
				<span class="point" class:working={current === index && stage !== 'done'} aria-hidden="true"
					>{index < current || stage === 'done' ? '✓' : ''}</span
				>
				{stageLabels[step]}
			</span>
			{#if index < steps.length - 1}<span class="line" aria-hidden="true"></span>{/if}
		{/each}
	{/if}
</div>

<style>
	.progress {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.45rem;
		font-size: 0.68rem;
		color: var(--kakam-muted);
		min-height: 1.4rem;
	}
	.step {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		opacity: 0.45;
	}
	.active,
	.complete {
		opacity: 1;
	}
	.point {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 0.9rem;
		width: 0.9rem;
		border: 1px solid var(--kakam-border);
		border-radius: 50%;
		font-size: 0.65rem;
	}
	.complete .point {
		background: #10b98116;
		color: #059669;
		border-color: #10b98133;
	}
	.working {
		border-color: #10b981;
		border-top-color: transparent;
		animation: spin 1s linear infinite;
	}
	.line {
		width: 1rem;
		height: 1px;
		background: var(--kakam-border);
	}
	.stopped {
		opacity: 0.7;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.working {
			animation: none;
		}
	}
	@media (max-width: 480px) {
		.line {
			width: 0.4rem;
		}
		.progress {
			gap: 0.3rem;
			font-size: 0.6rem;
		}
	}
</style>
