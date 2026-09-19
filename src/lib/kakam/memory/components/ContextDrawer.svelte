<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import type { Composition, ContextDetails } from '../types';
	import { getContextDetails } from '../api';
	import { labels } from '../service';
	import { segmentColors } from '../activity';
	import PromptMatrix from './PromptMatrix.svelte';
	export let report: Composition;
	const dispatch = createEventDispatcher();
	let dialog: HTMLDialogElement;
	let details: ContextDetails | null = null;
	let loading = false;
	let error = '';
	let alive = true;
	async function load() {
		if (!report.detail_id) return;
		loading = true;
		error = '';
		try {
			const result = await getContextDetails(report.detail_id);
			if (alive && result.message_id === report.message_id) details = result;
		} catch {
			if (alive)
				error = '详情暂不可用：可能已过期、服务重启，或当前实例没有这份快照。数量统计仍然保留。';
		} finally {
			if (alive) loading = false;
		}
	}
	onMount(() => {
		// Native modal dialog provides focus trapping, Escape and background inertness.
		const previous = document.activeElement as HTMLElement | null;
		const overflow = document.body.style.overflow;
		document.body.appendChild(dialog);
		dialog.showModal();
		document.body.style.overflow = 'hidden';
		void load();
		return () => {
			alive = false;
			dialog.close();
			dialog.remove();
			document.body.style.overflow = overflow;
			previous?.focus();
		};
	});
	function backdrop(event: MouseEvent) {
		if (event.target !== dialog) return;
		const rect = dialog.getBoundingClientRect();
		if (
			event.clientX < rect.left ||
			event.clientX > rect.right ||
			event.clientY < rect.top ||
			event.clientY > rect.bottom
		)
			dispatch('close');
	}
</script>

<dialog
	bind:this={dialog}
	aria-label="Context 组成详情"
	class="context-drawer bg-white text-gray-900 dark:bg-gray-900 dark:text-gray-100"
	on:close={() => dispatch('close')}
	on:click={backdrop}
>
	<header
		class="flex shrink-0 items-start justify-between gap-3 border-b border-gray-100 p-5 dark:border-gray-800"
	>
		<div class="min-w-0">
			<h2 class="text-base font-semibold">Context 组成</h2>
			<p class="mt-1 break-all text-xs text-gray-500">{report.policy} · {report.model}</p>
		</div>
		<button
			type="button"
			class="shrink-0 rounded-lg px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
			aria-label="关闭 Context 详情"
			on:click={() => dispatch('close')}>关闭 ✕</button
		>
	</header>
	<div class="min-h-0 flex-1 overflow-y-auto overscroll-contain p-5">
		<p class="text-xs leading-relaxed text-gray-500">
			选中响应的推理前文本快照，不是输入框预览或完整供应商请求。点击下面的分类展开原文。
		</p>
		<PromptMatrix {report} />
		{#if report.status === 'unavailable'}
			<div
				role="status"
				class="my-4 rounded-xl bg-amber-50 p-3 text-xs leading-relaxed text-amber-800 dark:bg-amber-950/30 dark:text-amber-200"
			>
				这次长期记忆召回失败，聊天已继续。服务端开关已打开；请管理员检查 Memory
				API、服务密钥、embedding 配置和召回超时。恢复后发送新消息验证，旧快照不会变成成功状态。
			</div>
		{/if}
		<p class="my-4 text-xs leading-relaxed text-gray-500">
			原文仅在服务端内存短时保留（最多 15 分钟，容量满时提前淘汰），不额外写入聊天记录。System
			原文仅管理员可查看。每类最多预览 16,000 字符。
		</p>
		{#if loading}<p role="status" class="py-4 text-sm text-gray-500">正在读取 Context 详情…</p>
		{:else if error}<p role="status" class="mb-4 text-xs text-gray-500">
				{error} <button class="underline" type="button" on:click={load}>重试</button>
			</p>{/if}
		{#each report.segments as segment}
			{@const section = details?.sections.find((s) => s.kind === segment.kind)}
			<details class="mb-3 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700">
				<summary class="cursor-pointer px-4 py-3 text-sm">
					<span
						class="ml-1 inline-block size-2 rounded-sm"
						style:background={segmentColors[segment.kind]}
					></span>
					{labels[segment.kind]}
					<span class="text-xs text-gray-500">{segment.characters.toLocaleString()} 字符</span>
				</summary>
				<div class="border-t border-gray-100 p-4 dark:border-gray-800">
					{#if section?.restricted}<p class="text-xs text-gray-500">
							System 可能包含管理员配置，仅管理员可查看原文。
						</p>
					{:else if section?.content}<pre
							class="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{section.content}</pre>
						{#if section.truncated}<p class="mt-3 text-xs text-amber-600">
								内容较长，已截断预览；上方数量按完整文本计算。
							</p>{/if}
					{:else if !segment.characters}<p class="text-xs text-gray-500">
							本次请求未包含此部分文本。
						</p>
					{:else}<p class="text-xs text-gray-500">
							{loading
								? '正在加载…'
								: '没有可用原文。旧记录仅保存数量，未记录、过期或重启丢失的快照不会重新拼接。'}
						</p>{/if}
				</div>
			</details>
		{/each}
	</div>
</dialog>

<style>
	.context-drawer {
		position: fixed;
		inset: 0 0 0 auto;
		margin: 0;
		width: min(40rem, 100vw);
		max-width: 100vw;
		height: 100dvh;
		max-height: 100dvh;
		padding: 0;
		border: 0;
		overflow: hidden;
		box-shadow: -12px 0 48px #0002;
	}
	.context-drawer[open] {
		display: flex;
		flex-direction: column;
		animation: enter 180ms ease-out;
	}
	.context-drawer::backdrop {
		background: #0006;
	}
	pre {
		overflow-wrap: anywhere;
	}
	@keyframes enter {
		from {
			transform: translateX(100%);
		}
		to {
			transform: translateX(0);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.context-drawer[open] {
			animation: none;
		}
	}
	@media (max-width: 640px) {
		.context-drawer {
			width: 100%;
		}
	}
	header {
		padding-top: max(1.25rem, env(safe-area-inset-top));
	}
	.context-drawer > div {
		padding-bottom: max(1.25rem, env(safe-area-inset-bottom));
	}
</style>
