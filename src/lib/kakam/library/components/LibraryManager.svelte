<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { showSettings } from '$lib/stores';
	import { getFileBlob } from '../api';
	import { formatBytes, saveBlob } from '../service';
	import { createLibraryStore } from '../store';
	import type { Entry, Kind } from '../types';
	import RecordDetail from './RecordDetail.svelte';
	export let initialChatId = '';
	const library = createLibraryStore(() => localStorage.token);
	let kind: Kind = 'chat';
	let query = '';
	let age = 0;
	let offset = 0;
	let selected: string[] = [];
	let confirmation = false;
	let deleting = false;
	let notice = '';
	let actionError = '';
	let downloading = '';
	let detail: Entry | null = null;
	const tabs: { kind: Kind; label: string }[] = [
		{ kind: 'chat', label: '会话与消息' },
		{ kind: 'file', label: '文件与附件' },
		{ kind: 'note', label: '笔记' }
	];
	onMount(() => {
		library.refreshSummary();
		load();
		if (initialChatId) inspectChat(initialChatId);
	});
	onDestroy(library.destroy);
	function load() {
		selected = [];
		confirmation = false;
		library.load({
			kind,
			q: query,
			offset,
			before: age ? Math.floor(Date.now() / 1000) - age * 86400 : undefined
		});
	}
	function filter() {
		offset = 0;
		load();
	}
	function inspectChat(id: string) {
		detail = {
			id,
			kind: 'chat',
			title: '会话记录',
			updated_at: 0,
			size: null,
			content_type: null,
			origin: 'unknown',
			sources: [],
			archived: false
		};
	}
	function openChat(id: string) {
		showSettings.set(false);
		goto(`/c/${encodeURIComponent(id)}`);
	}
	function select(id: string) {
		selected = selected.includes(id) ? selected.filter((value) => value !== id) : [...selected, id];
	}
	$: selectedEntries = $library.page.items.filter((e) => selected.includes(e.id));
	$: selectedBytes = selectedEntries.reduce((sum, e) => sum + (e.size || 0), 0);
	async function remove() {
		deleting = true;
		notice = '';
		actionError = '';
		try {
			const result = await library.remove(selectedEntries);
			notice = `已删除 ${result.deleted} 项。`;
			actionError = result.failed.join('\n');
			offset = 0;
			selected = [];
			confirmation = false;
		} finally {
			deleting = false;
		}
	}
	async function download(entry: Entry) {
		downloading = entry.id;
		actionError = '';
		try {
			const result = await getFileBlob(localStorage.token, entry.id);
			saveBlob(result.blob, result.filename || entry.title);
		} catch (e) {
			actionError = String(e);
		} finally {
			downloading = '';
		}
	}
</script>

<div id="tab-library" class="h-full min-h-0 overflow-y-auto pr-1 text-sm">
	<div class="mb-5 flex flex-wrap items-start justify-between gap-3">
		<div>
			<h2 class="text-xl font-semibold">消息与文件</h2>
			<p class="mt-1 text-xs text-gray-500">会话记录、上传附件、模型产物与笔记，统一查找和下载。</p>
		</div>
		{#if !detail}<button
				class="rounded-lg border px-3 py-1.5 text-xs dark:border-gray-700"
				disabled={$library.loading || deleting}
				on:click={() => {
					load();
					library.refreshSummary();
				}}>刷新</button
			>{/if}
	</div>
	{#if detail}
		{#key `${detail.kind}:${detail.id}`}<RecordDetail
				entry={detail}
				close={() => (detail = null)}
				{openChat}
			/>{/key}
	{:else}
		{#if $library.summary}
			<div class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
				{#each [{ label: '会话', value: $library.summary.chats }, { label: '文件', value: $library.summary.files }, { label: '笔记', value: $library.summary.notes }, { label: '文件存储', value: formatBytes($library.summary.file_bytes) }] as stat}
					<div class="rounded-xl bg-gray-50 p-3 dark:bg-gray-900">
						<p class="text-xs text-gray-500">{stat.label}</p>
						<p class="mt-1 text-lg font-semibold">{stat.value}</p>
					</div>
				{/each}
			</div>
			<p class="mb-4 text-xs text-gray-500">
				存储统计为本人文件的已记录原始大小，不含数据库、索引、备份和外部临时资源。{#if $library.summary.unknown_size_files}另有
					{$library.summary.unknown_size_files} 个文件大小未记录。{/if}
			</p>
		{/if}
		<div class="mb-4 flex flex-wrap gap-1" role="tablist" aria-label="记录类型">
			{#each tabs.filter((t) => t.kind !== 'note' || $library.summary?.notes_enabled) as tab}
				<button
					role="tab"
					aria-selected={kind === tab.kind}
					class="rounded-xl px-4 py-2 {kind === tab.kind
						? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900'
						: 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-900'}"
					disabled={deleting}
					on:click={() => {
						kind = tab.kind;
						query = '';
						filter();
					}}>{tab.label}</button
				>
			{/each}
		</div>
		<form class="mb-4 flex flex-wrap gap-2" on:submit|preventDefault={filter}>
			<input
				class="min-w-0 flex-1 rounded-xl border bg-transparent px-3 py-2 dark:border-gray-700"
				aria-label="按名称搜索"
				placeholder="搜索标题或文件名"
				bind:value={query}
				maxlength="200"
				disabled={deleting}
			/>
			<select
				aria-label="按最后修改时间筛选"
				class="rounded-xl border bg-transparent px-2 py-2 dark:border-gray-700"
				bind:value={age}
				disabled={deleting}
				on:change={filter}
				><option value={0}>全部时间</option><option value={30}>30 天未修改</option><option
					value={90}>90 天未修改</option
				><option value={365}>一年未修改</option></select
			>
			<button class="rounded-xl border px-3 py-2 dark:border-gray-700" disabled={deleting}
				>搜索</button
			>
		</form>
		{#if kind === 'note'}<a
				href="/notes"
				on:click={() => showSettings.set(false)}
				class="mb-4 inline-block text-xs underline">打开原笔记工作区 / 新建笔记</a
			>{/if}
		<details class="mb-4 rounded-xl bg-gray-50 p-3 text-xs text-gray-500 dark:bg-gray-900">
			<summary class="cursor-pointer">保存期限与清理规则</summary>
			<p class="mt-2">
				会话、原生文件和笔记沿用现有持久存储，本中心不设置自动过期。时间筛选只用于查找，不会自动删除。删除会话会删除其消息，但保留附件和笔记；需要释放文件空间时，请到「文件与附件」单独清理。外部链接、终端和浏览器临时文件由对应环境管理，不保证长期可用。
			</p>
		</details>
		{#if $library.error || actionError}<p
				role="alert"
				class="mb-3 whitespace-pre-wrap text-xs text-red-600"
			>
				{$library.error || actionError}
			</p>{/if}
		{#if notice}<p role="status" class="mb-3 text-xs text-gray-500">{notice}</p>{/if}
		{#if confirmation}
			<div class="mb-4 rounded-xl border border-red-300 p-4" role="region" aria-label="删除确认">
				<p class="font-semibold">永久删除选中的 {selected.length} 项？</p>
				<p class="my-2 text-xs">
					{#if kind === 'file'}已记录大小 {formatBytes(
							selectedBytes
						)}。文件将从存储中移除，引用它的会话、共享链接或知识库可能失效。未记录来源不代表文件未被使用。{:else if kind === 'chat'}会话、全部消息分支及会话分享将被删除。附件和笔记仍保留，不会同时释放附件空间。{:else}笔记原文将被删除，笔记分享和引用可能失效。{/if}此操作无法撤销。
				</p>
				<ul class="mb-3 max-h-28 overflow-auto text-xs">
					{#each selectedEntries as entry}<li class="break-all">{entry.title}</li>{/each}
				</ul>
				<div class="flex gap-3">
					<button
						class="rounded-lg bg-red-600 px-3 py-2 text-xs text-white"
						disabled={deleting}
						on:click={remove}>{deleting ? '正在删除…' : '确认永久删除'}</button
					><button class="text-xs" disabled={deleting} on:click={() => (confirmation = false)}
						>取消</button
					>
				</div>
			</div>
		{/if}
		<div class="mb-2 flex items-center justify-between text-xs text-gray-500">
			<label class="flex items-center gap-2"
				><input
					type="checkbox"
					aria-label="选择本页"
					disabled={deleting || !$library.page.items.length}
					checked={selected.length > 0 && selected.length === $library.page.items.length}
					on:change={(e) => {
						selected = e.currentTarget.checked ? $library.page.items.map((i) => i.id) : [];
						confirmation = false;
					}}
				/>选择本页 · {$library.page.total} 项</label
			>
			<button
				class="text-red-600 disabled:text-gray-400"
				disabled={!selected.length || deleting}
				on:click={() => (confirmation = true)}>清理所选（{selected.length}）</button
			>
		</div>
		{#if $library.loading}<p class="py-10 text-center text-gray-500" role="status">
				正在读取…
			</p>{:else if !$library.page.items.length && !$library.error}<p
				class="py-10 text-center text-gray-500"
			>
				没有符合条件的记录
			</p>{/if}
		<div class="divide-y dark:divide-gray-800">
			{#each $library.page.items as entry (entry.id)}
				<div class="flex gap-3 py-4">
					<input
						type="checkbox"
						class="mt-1 shrink-0"
						aria-label={`选择 ${entry.title}`}
						checked={selected.includes(entry.id)}
						disabled={deleting}
						on:change={() => {
							select(entry.id);
							confirmation = false;
						}}
					/>
					<div class="min-w-0 flex-1">
						<button
							class="break-all text-left font-medium hover:underline"
							on:click={() => (detail = entry)}>{entry.title}</button
						>
						<p class="mt-1 text-xs text-gray-500">
							{new Date(entry.updated_at * 1000).toLocaleDateString()}
							{entry.archived ? '· 已归档' : ''}{#if kind === 'file'}
								· {formatBytes(entry.size)} · {entry.origin === 'generated'
									? '模型产物'
									: '文件 / 附件'}{/if}
						</p>
						{#if kind === 'file'}
							{#each entry.sources as source}<button
									class="mt-1 block max-w-full truncate text-xs text-gray-500 underline"
									on:click={() => inspectChat(source.chat_id)}
									>来自：{source.title}{source.message_id ? ` · ${source.message_id}` : ''}</button
								>{:else}<p class="mt-1 text-xs text-gray-400">会话来源未记录或已删除</p>{/each}
						{/if}
					</div>
					{#if kind === 'file'}<button
							class="self-start rounded-lg border px-3 py-1.5 text-xs dark:border-gray-700"
							disabled={downloading === entry.id || deleting}
							on:click={() => download(entry)}
							>{downloading === entry.id ? '读取中' : '下载'}</button
						>{:else}<button
							class="self-start rounded-lg border px-3 py-1.5 text-xs dark:border-gray-700"
							on:click={() => (detail = entry)}>查看</button
						>{/if}
				</div>
			{/each}
		</div>
		<div class="mt-4 flex items-center justify-between pb-4 text-xs">
			<button
				disabled={!offset || $library.loading || deleting}
				class="disabled:opacity-30"
				on:click={() => {
					offset -= 30;
					load();
				}}>← 上一页</button
			><span>第 {Math.floor(offset / 30) + 1} 页</span><button
				disabled={offset + 30 >= $library.page.total || $library.loading || deleting}
				class="disabled:opacity-30"
				on:click={() => {
					offset += 30;
					load();
				}}>下一页 →</button
			>
		</div>
	{/if}
</div>
