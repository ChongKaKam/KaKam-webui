<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		inspectSession,
		setSessionScope,
		decideProposal,
		proposeMemory,
		editMemory,
		createCollection,
		assignCollection,
		deleteMemory
	} from '../api';
	import type { ManagerView, Memory } from '../types';
	export let sessionId: string;
	export let sourceMessageId = '';
	let view: ManagerView | null = null;
	let busy = false;
	let error = '';
	let notice = '';
	let alive = true;
	let search = '';
	let content = '';
	let collection = '';
	let parent = '';
	let editing: Memory | null = null;
	let tagText = '';
	$: visible = (view?.memories ?? []).filter((m) =>
		`${m.content} ${m.kind} ${(m.tags ?? []).join(' ')}`
			.toLowerCase()
			.includes(search.toLowerCase())
	);
	async function load() {
		const result = await inspectSession(sessionId);
		if (alive) view = result;
	}
	async function action(work: () => Promise<unknown>, message = '') {
		if (busy) return;
		busy = true;
		error = '';
		notice = '';
		try {
			await work();
			await load();
			if (alive) notice = message;
		} catch (e) {
			if (alive) error = e instanceof Error ? e.message : String(e);
		} finally {
			if (alive) busy = false;
		}
	}
	function selection(id: string, value: string) {
		if (!view) return;
		const selections = { ...view.session.selections };
		if (value === 'auto') delete selections[id];
		else selections[id] = value as 'prefer' | 'exclude';
		void action(
			() => setSessionScope(sessionId, { ...view!.session, selections }),
			'已保存，下次发送消息时生效。'
		);
	}
	function saveScope() {
		if (view)
			void action(() => setSessionScope(sessionId, view!.session), '已保存，下次发送消息时生效。');
	}
	function startEdit(memory: Memory) {
		editing = { ...memory };
		tagText = (memory.tags ?? []).join(', ');
	}
	onMount(() => {
		void action(load);
	});
	onDestroy(() => {
		alive = false;
	});
</script>

<section
	class="manager my-4 rounded-xl border border-gray-200 p-4 dark:border-gray-700"
	aria-label="Session Memory"
>
	<div class="flex items-center justify-between gap-2">
		<h3 class="font-medium">Session Memory</h3>
		<button type="button" disabled={busy} on:click={() => action(load)}>刷新</button>
	</div>
	<p class="mt-2 text-xs text-gray-500">
		这里控制本会话后续请求，不会改写上方历史快照。优先使用仍受预算和有效期限制；排除一定不注入。
	</p>
	{#if error}<p role="alert" class="mt-3 text-xs text-red-500">{error}</p>{/if}
	{#if notice}<p role="status" class="mt-3 text-xs text-emerald-600">{notice}</p>{/if}
	{#if view}
		<fieldset disabled={busy} class="mt-4 space-y-3 text-xs">
			<label class="flex items-center justify-between gap-2"
				>策略<select bind:value={view.session.policy} on:change={saveScope}
					>{#each view.policies as policy}<option value={policy.id}>{policy.name}</option
						>{/each}</select
				></label
			>
			<label class="flex items-center justify-between gap-2"
				>自动检索相关记忆<input
					type="checkbox"
					bind:checked={view.session.settings.automatic_recall}
					on:change={saveScope}
				/></label
			>
			<label class="flex items-center justify-between gap-2"
				>自动压缩上下文<input
					type="checkbox"
					bind:checked={view.session.settings.auto_compact}
					on:change={saveScope}
				/></label
			>
			<label class="flex items-center justify-between gap-2"
				>压缩触发估算额度<input
					aria-label="压缩触发估算额度"
					type="number"
					min="2000"
					max="100000"
					step="1000"
					class="w-24"
					bind:value={view.session.settings.token_budget}
					on:change={saveScope}
				/></label
			>
			<p class="text-gray-500">
				按文本 UTF-8 字节保守估算，不是模型实际 token 数。保留最近 {view.session.settings
					.keep_messages} 条消息和完整工具调用；图片与复杂输出暂不压缩。
			</p>
			{#if !view.compaction.available}<p class="text-amber-600">
					压缩模型未配置。请管理员在 Memory 服务设置 MEMORY_CONTEXT_BASE_URL / MODEL /
					API_KEY；目前保留原始上下文。
				</p>{/if}
			{#if view.compaction.summary}<details>
					<summary class="cursor-pointer"
						>查看最近压缩摘要（{view.compaction.cut} 条历史消息）</summary
					>
					<pre class="mt-2 whitespace-pre-wrap break-words text-xs">{view.compaction.summary}</pre>
				</details>{/if}
			{#if view.proposals.length}
				<h4 class="pt-2 font-medium">待确认的知识</h4>
				{#each view.proposals as proposal (proposal.id)}<article
						class="rounded-lg bg-amber-50 p-3 dark:bg-amber-950/30"
					>
						<p class="whitespace-pre-wrap break-words">{proposal.content}</p>
						<details class="mt-2">
							<summary>来源：用户原文</summary>
							<pre class="whitespace-pre-wrap break-words">{proposal.evidence}</pre>
						</details>
						<div class="mt-2 flex gap-2">
							<button
								type="button"
								on:click={() =>
									action(
										() => decideProposal(proposal.id, true),
										'已处理保存请求；重复或已遗忘的记忆不会重建。'
									)}>确认保存</button
							><button
								type="button"
								on:click={() => action(() => decideProposal(proposal.id, false))}>拒绝</button
							>
						</div>
					</article>{/each}
			{/if}
			<details>
				<summary class="cursor-pointer font-medium">主动沉淀知识</summary>
				<textarea
					aria-label="要沉淀的知识"
					bind:value={content}
					maxlength="2000"
					rows="3"
					class="mt-2 w-full"
					placeholder="输入本次对话中需要记住的知识；保存前还会显示确认。"
				></textarea>
				<button
					type="button"
					disabled={!content.trim() || !sourceMessageId}
					on:click={() =>
						action(async () => {
							await proposeMemory(sessionId, content, sourceMessageId);
							content = '';
						})}>创建待确认记忆</button
				>
			</details>
			<input
				aria-label="搜索记忆"
				placeholder="搜索记忆、类型或标签"
				class="w-full"
				bind:value={search}
			/>
			<div class="max-h-80 space-y-3 overflow-y-auto">
				{#each visible as memory (memory.id)}<article
						class="rounded-lg border border-gray-200 p-3 dark:border-gray-700"
					>
						<p class="whitespace-pre-wrap break-words">{memory.content}</p>
						<p class="mt-1 text-gray-500">
							{memory.kind} · {(memory.tags ?? []).join(' · ')} · {new Date(
								memory.expires_at
							).toLocaleDateString()} 到期
						</p>
						<div class="mt-2 flex flex-wrap items-center gap-2">
							<select
								aria-label={`使用方式：${memory.content.slice(0, 30)}`}
								value={view.session.selections[memory.id] ?? 'auto'}
								on:change={(e) => selection(memory.id, e.currentTarget.value)}
								><option value="auto">自动</option><option value="prefer">优先使用</option><option
									value="exclude">排除</option
								></select
							>
							<button type="button" on:click={() => startEdit(memory)}>编辑</button>
							<button
								type="button"
								on:click={() => {
									if (confirm('遗忘这条记忆？正文与历史版本会被清除，无法恢复。'))
										void action(() => deleteMemory(memory.id));
								}}>遗忘</button
							>
							<select
								aria-label="加入知识集合"
								value=""
								on:change={(e) => {
									const id = e.currentTarget.value;
									if (id) void action(() => assignCollection(memory.id, id));
								}}
								><option value="">加入集合…</option>{#each view.collections as c}<option
										value={c.id}>{c.name}</option
									>{/each}</select
							>
						</div>
					</article>{:else}<p class="text-gray-500">
						没有匹配的长期记忆。普通聊天不会自动写入；可主动保存或让模型提出建议。
					</p>{/each}
			</div>
			{#if editing}<div class="space-y-2 rounded-lg border p-3">
					<label class="block"
						>编辑内容<textarea
							class="mt-1 w-full"
							maxlength="2000"
							rows="3"
							bind:value={editing.content}
						></textarea></label
					>
					<label class="block"
						>分类 <select bind:value={editing.kind}
							>{#each ['profile', 'preference', 'instruction', 'fact', 'episode'] as kind}<option
									value={kind}>{kind}</option
								>{/each}</select
						></label
					>
					<label class="block"
						>标签（英文逗号分隔）<input class="mt-1 w-full" bind:value={tagText} /></label
					>
					<button
						type="button"
						on:click={() =>
							action(async () => {
								await editMemory({
									...editing!,
									tags: tagText
										.split(',')
										.map((t) => t.trim())
										.filter(Boolean)
								});
								editing = null;
							})}>保存修改</button
					>
					<button type="button" on:click={() => (editing = null)}>取消</button>
				</div>{/if}
			<details>
				<summary class="cursor-pointer font-medium">知识关系 / 集合</summary>
				<p class="my-2 text-gray-500">
					以分类和集合组织记忆；一条记忆可属于多个集合。这里显示存储关系，不代表本轮全部使用。
				</p>
				<div class="flex flex-wrap gap-2">
					<input
						aria-label="新集合名称"
						maxlength="100"
						placeholder="集合名称"
						bind:value={collection}
					/><select aria-label="父集合" bind:value={parent}
						><option value="">顶层集合</option>{#each view.collections as c}<option value={c.id}
								>{c.name}</option
							>{/each}</select
					><button
						type="button"
						disabled={!collection.trim()}
						on:click={() =>
							action(async () => {
								await createCollection(collection.trim(), parent || null);
								collection = '';
							})}>新建集合</button
					>
				</div>
				<div class="mt-3 space-y-3 border-l-2 border-emerald-400 pl-3">
					{#each view.collections as c}<div>
							<strong
								>{c.parent_id
									? `${view.collections.find((p) => p.id === c.parent_id)?.name ?? '上级'} / `
									: ''}{c.name}</strong
							>
							{#each view.relations.filter((r) => r.collection_id === c.id) as relation}<div
									class="ml-3 mt-1 border-l border-blue-400 pl-2"
								>
									<span
										>{view.memories.find((m) => m.id === relation.memory_id)?.content ??
											'未在当前列表中'}</span
									>
									<button
										type="button"
										on:click={() => action(() => assignCollection(relation.memory_id, c.id, false))}
										>移出</button
									>
								</div>{/each}
						</div>{:else}<p class="text-gray-500">还没有知识集合。</p>{/each}
				</div>
			</details>
			<details>
				<summary class="cursor-pointer font-medium">最近 Manager 操作</summary>
				{#each view.operations as op}<p class="mt-2 break-words text-gray-500">
						{new Date(op.created_at).toLocaleString()} · {op.operation} · {op.state}{op.facts
							.selected_ids
							? ` · 选中 ${op.facts.selected_ids.length} 条`
							: ''}{op.facts.omitted_preferred?.length
							? ` · ${op.facts.omitted_preferred.length} 条优先记忆未注入（预算或有效性限制）`
							: ''}
					</p>{/each}
			</details>
		</fieldset>
	{:else if busy}<p role="status" class="mt-3 text-xs">正在连接 Memory Manager…</p>{/if}
</section>

<style>
	.manager button,
	.manager select,
	.manager input:not([type='checkbox']),
	.manager textarea {
		border: 1px solid #8885;
		border-radius: 0.4rem;
		background: transparent;
		padding: 0.35rem 0.5rem;
		max-width: 100%;
	}
	.manager button {
		font-size: 0.75rem;
	}
	.manager button:hover {
		background: #8881;
	}
	.manager :disabled {
		opacity: 0.5;
	}
	.manager pre {
		overflow-wrap: anywhere;
	}
</style>
