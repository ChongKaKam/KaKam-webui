<script lang="ts">
	import { onDestroy } from 'svelte';
	import { models, socket } from '$lib/stores';
	import { copyToClipboard } from '$lib/utils';
	import { generateHandoff } from '../api';
	import { buildHandoffInput } from '../service';
	import { prepareHandoff } from '../../memory/api';
	import type { HandoffHistory } from '../types';
	import type { ContextDetails } from '../../memory/types';
	import type { ChatParams } from '../../chat/effort';
	export let history: HandoffHistory;
	export let messageId: string;
	export let defaultModel: string;
	export let details: ContextDetails | null = null;
	export let params: ChatParams = {};
	export let sessionId = '';
	export let managerEnabled = false;
	let modelId = defaultModel;
	let result = '';
	let resultModel = '';
	let busy = false;
	let error = '';
	let status = '';
	let controller: AbortController | null = null;
	let alive = true;
	let timeout: ReturnType<typeof setTimeout>;
	let deadline: ReturnType<typeof setTimeout>;
	let timer: ReturnType<typeof setInterval>;
	let elapsed = 0;
	let phase = '正在连接模型';
	$: available = $models.filter((model) => !model.info?.meta?.hidden);
	let source = buildHandoffInput(history, messageId, details);
	async function generate() {
		if (busy) return;
		source = buildHandoffInput(history, messageId, details);
		const model = available.find((item) => item.id === modelId);
		if (!model) {
			error = '当前模型不可用，请选择一个可用模型。';
			return;
		}
		if (!source.count) {
			error = '当前分支没有可交接的对话文本。';
			return;
		}
		const request = new AbortController();
		controller = request;
		busy = true;
		error = '';
		status = '';
		let timedOut = false;
		let receivedText = false;
		elapsed = 0;
		phase = '正在连接模型';
		const started = Date.now();
		timer = setInterval(() => {
			elapsed = Math.floor((Date.now() - started) / 1000);
		}, 1000);
		const expire = () => {
			timedOut = true;
			request.abort();
		};
		const refreshTimeout = () => {
			clearTimeout(timeout);
			timeout = setTimeout(expire, 180_000);
		};
		refreshTimeout();
		deadline = setTimeout(expire, 600_000);
		try {
			let sourceText = source.text;
			if (managerEnabled && sessionId)
				sourceText = (await prepareHandoff(sessionId, sourceText)).source;
			if (request.signal.aborted) return;
			const text = await generateHandoff(model, sourceText, params, request.signal, $socket?.id, {
				onActivity: refreshTimeout,
				onPhase: (next) => {
					if (alive)
						phase = {
							waiting: '已连接，等待模型输出',
							thinking: '模型正在推理',
							writing: '正在接收交接正文'
						}[next];
				},
				onText: (text) => {
					if (!alive || request.signal.aborted) return;
					receivedText = true;
					result = text;
					resultModel = model.name || model.id;
				}
			});
			if (alive && !request.signal.aborted) {
				result = text;
				resultModel = model.name || model.id;
				status = '交接内容已生成，可直接编辑。';
			}
		} catch (cause) {
			if (alive)
				error = request.signal.aborted
					? timedOut
						? '模型长时间未响应或已达到等待上限，请重试或更换模型。'
						: '已停止生成。'
					: cause instanceof Error
						? cause.message
						: '生成失败，请重试。';
			if (alive && receivedText) error += ' 已保留收到的部分正文，内容尚不完整。';
		} finally {
			clearTimeout(timeout);
			clearTimeout(deadline);
			clearInterval(timer);
			if (alive) {
				busy = false;
				controller = null;
			}
		}
	}
	async function copy() {
		try {
			const ok = await copyToClipboard(result);
			if (ok === false) throw new Error();
			status = '已复制交接内容';
		} catch {
			error = '复制失败，请在文本框中选择并复制。';
		}
	}
	function download() {
		const url = URL.createObjectURL(new Blob([result], { type: 'text/markdown;charset=utf-8' }));
		const link = document.createElement('a');
		link.href = url;
		link.download = `handoff-${new Date().toISOString().slice(0, 10)}.md`;
		link.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
		status = '已导出 Markdown';
	}
	onDestroy(() => {
		alive = false;
		controller?.abort();
		clearTimeout(timeout);
		clearTimeout(deadline);
		clearInterval(timer);
	});
</script>

<section class="handoff" aria-label="Hand-off 交接" aria-busy={busy}>
	<div class="heading">
		<h3>Hand-off</h3>
		<span>把当前进度交给下一位助手</span>
	</div>
	<label for="handoff-model">生成模型</label>
	<div class="controls">
		<select id="handoff-model" bind:value={modelId} disabled={busy}>
			{#if !available.some((model) => model.id === modelId)}<option value={modelId} disabled
					>当前模型不可用</option
				>{/if}
			{#each available as model}<option value={model.id}>{model.name || model.id}</option>{/each}
		</select>
		{#if busy}<button type="button" on:click={() => controller?.abort()}>停止</button>{:else}<button
				type="button"
				disabled={!available.length || !source.count}
				on:click={generate}>{result ? '重新生成' : '生成'}</button
			>{/if}
	</div>
	<p class="note">
		点击“生成”后，将根据当前分支的 {source.count} 条消息{source.hasMemory
			? '及可见长期记忆'
			: ''}生成，不含 System、图片和附件原文件。{source.truncated
			? '长对话已保留最初目标和最近消息，部分内容省略。'
			: ''}
	</p>
	{#if busy}<p role="status">{phase} · {elapsed} 秒</p>{/if}
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	<label for="handoff-result">交接 prompt{resultModel ? ` · ${resultModel}` : ''}</label>
	<textarea
		id="handoff-result"
		bind:value={result}
		readonly={busy}
		placeholder="生成结果会显示在这里，你可以继续编辑后复制或导出。"
		spellcheck="false"
	></textarea>
	<div class="actions">
		<button type="button" disabled={busy || !result.trim()} on:click={copy}>复制</button><button
			type="button"
			disabled={busy || !result.trim()}
			on:click={download}>导出 Markdown</button
		>
	</div>
	<p class="note" role="status">{status}</p>
</section>

<style>
	.handoff {
		padding: 1rem;
		margin-bottom: 1.5rem;
		border: 1px solid var(--kakam-border);
		border-radius: 1rem;
		background: var(--kakam-surface);
		font-size: 0.875rem;
	}
	.heading {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}
	h3 {
		font-size: 1rem;
		font-weight: 600;
	}
	.heading span,
	.note {
		color: var(--kakam-muted);
		font-size: 0.8125rem;
		line-height: 1.6;
	}
	label {
		display: block;
		margin: 0.75rem 0 0.4rem;
	}
	.controls,
	.actions {
		display: flex;
		gap: 0.5rem;
	}
	select {
		min-width: 0;
		flex: 1;
	}
	select,
	textarea {
		background: transparent;
		border: 1px solid var(--kakam-border);
		border-radius: 0.65rem;
		padding: 0.6rem;
	}
	textarea {
		width: 100%;
		min-height: 20rem;
		resize: vertical;
		font-size: 0.875rem;
		line-height: 1.7;
	}
	button {
		padding: 0.5rem 0.75rem;
		border-radius: 0.65rem;
		background: rgb(128 128 128 / 0.12);
		flex-shrink: 0;
		min-height: 2.5rem;
	}
	button:disabled {
		opacity: 0.4;
	}
	button:focus-visible,
	select:focus-visible,
	textarea:focus-visible {
		outline: 2px solid #888;
		outline-offset: 2px;
	}
	.note {
		margin: 0.6rem 0;
	}
	.error {
		color: #c2410c;
		margin: 0.6rem 0;
	}
	:global(.dark) .error {
		color: #fdba74;
	}
	@media (max-width: 640px) {
		select,
		textarea {
			font-size: 1rem;
		}
		.handoff {
			padding: 0.75rem;
		}
	}
</style>
