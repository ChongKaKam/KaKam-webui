<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { showSettings } from '$lib/stores';
	import { getChat, getNote, getFileBlob, getEntries } from '../api';
	import {
		exportChat,
		fileId,
		messageFiles,
		messageText,
		previewDocument,
		saveBlob,
		saveText
	} from '../service';
	import type { Attachment, ChatDetail, Entry, NoteDetail } from '../types';
	import ArtifactList from './ArtifactList.svelte';
	export let entry: Entry;
	export let close: () => void;
	export let openChat: (id: string) => void;
	let chat: ChatDetail | null = null;
	let note: NoteDetail | null = null;
	let error = '';
	let busy = true;
	let search = '';
	let visible = 30;
	let related: Entry[] = [];
	let relatedTotal = 0;
	let relatedBusy = false;
	let fileText: string | null = null;
	let preview = false;
	const controller = new AbortController();
	onMount(async () => {
		try {
			if (entry.kind === 'chat') {
				chat = await getChat(localStorage.token, entry.id, controller.signal);
				await loadFiles();
			} else if (entry.kind === 'note')
				note = await getNote(localStorage.token, entry.id, controller.signal);
			else if (
				entry.size !== null &&
				entry.size <= 2 * 1024 * 1024 &&
				/^(text\/|image\/svg|application\/(json|xml))/.test(entry.content_type || '')
			) {
				const result = await getFileBlob(localStorage.token, entry.id);
				if (result.blob.size <= 2 * 1024 * 1024) fileText = await result.blob.text();
			}
		} catch (e) {
			if (!controller.signal.aborted) error = String(e);
		} finally {
			busy = false;
		}
	});
	onDestroy(() => controller.abort());
	$: messages = (chat?.messages || []).filter(
		(m) => !search || `${m.id} ${messageText(m)}`.toLowerCase().includes(search.toLowerCase())
	);
	async function download(file: Attachment) {
		const id = fileId(file);
		if (!id) return;
		try {
			const result = await getFileBlob(localStorage.token, id);
			saveBlob(result.blob, result.filename || file.name || file.filename || `${id}.bin`);
		} catch (e) {
			error = String(e);
		}
	}
	async function loadFiles() {
		relatedBusy = true;
		try {
			const result = await getEntries(
				localStorage.token,
				{ kind: 'file', q: '', offset: related.length, chat_id: entry.id },
				controller.signal
			);
			related = [...related, ...result.items];
			relatedTotal = result.total;
		} catch (e) {
			if (!controller.signal.aborted) error = String(e);
		} finally {
			relatedBusy = false;
		}
	}
</script>

<section class="space-y-4">
	<button class="text-sm text-gray-500 hover:underline" on:click={close}>← 返回列表</button>
	<h3 class="break-words text-lg font-semibold">{chat?.title || note?.title || entry.title}</h3>
	{#if error}<p role="alert" class="text-sm text-red-600">{error}</p>{/if}
	{#if busy}<p role="status">正在读取…</p>{/if}
	{#if chat}
		<div class="flex flex-wrap gap-3 text-sm">
			<button class="underline" on:click={() => openChat(chat!.id)}>打开原会话</button>
			<button class="underline" on:click={() => saveText(exportChat(chat!), `${chat!.title}.md`)}
				>导出 Markdown</button
			>
			<button
				class="underline"
				on:click={() =>
					saveText(JSON.stringify(chat, null, 2), `${chat!.title}.json`, 'application/json')}
				>导出 JSON</button
			>
		</div>
		<p class="text-xs text-gray-500">
			显示全部 {chat.messages.length} 条消息（含分支）。导出包含附件引用，附件需单独下载。网页和代码直接从原消息提取，不额外占用文件存储。
		</p>
		{#if related.length}
			<details open class="rounded-xl bg-gray-50 p-3 dark:bg-gray-900">
				<summary class="cursor-pointer text-sm">本会话已保存的文件（{relatedTotal}）</summary>
				{#each related as file}<div class="mt-2 flex items-center gap-2 text-xs">
						<span class="min-w-0 flex-1 break-all">{file.title}</span><button
							class="underline"
							on:click={() => download({ id: file.id, name: file.title })}>下载</button
						>
					</div>{/each}
				{#if related.length < relatedTotal}<button
						class="mt-2 text-xs underline"
						disabled={relatedBusy}
						on:click={loadFiles}>加载更多文件</button
					>{/if}
			</details>
		{/if}
		<input
			class="w-full rounded-xl border bg-transparent p-2 dark:border-gray-700"
			placeholder="搜索本会话的消息内容或 ID"
			aria-label="搜索消息"
			bind:value={search}
			on:input={() => (visible = 30)}
		/>
		{#each messages.slice(0, visible) as message (message.id)}
			<article class="rounded-xl border p-3 dark:border-gray-800">
				<div class="mb-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
					<strong
						>{message.role === 'user'
							? '用户'
							: message.role === 'assistant'
								? '模型'
								: message.role}</strong
					><span class="break-all">{message.id}</span><button
						class="ml-auto underline"
						on:click={() => saveText(messageText(message), `${message.id}.md`)}>下载消息</button
					>
				</div>
				<details>
					<summary class="cursor-pointer truncate text-sm"
						>{messageText(message).slice(0, 130) || '附件 / 工具输出'}</summary
					>
					<pre
						class="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs">{messageText(
							message
						)}</pre>
				</details>
				{#each messageFiles(message) as file}
					<div class="mt-2 flex flex-wrap items-center gap-2 text-xs">
						<span class="break-all"
							>{message.role === 'user' ? '上传附件' : '模型输出'} · {file.name ||
								file.filename ||
								file.path ||
								file.url ||
								file.id}</span
						>
						{#if fileId(file)}<button class="underline" on:click={() => download(file)}
								>下载附件</button
							>{:else}<span class="text-gray-500">外部或临时资源，请在原会话中打开</span>{/if}
					</div>
				{/each}
				{#if message.role === 'assistant'}<ArtifactList
						content={messageText(message)}
						title={`message-${message.id}`}
					/>{/if}
			</article>
		{/each}
		{#if messages.length > visible}<button
				class="rounded-xl border p-2 text-sm"
				on:click={() => (visible += 30)}>显示更多消息</button
			>{/if}
	{:else if note}
		<div class="flex flex-wrap gap-3 text-sm">
			<a
				href={`/notes/${encodeURIComponent(note.id)}`}
				on:click={() => showSettings.set(false)}
				class="underline">打开笔记编辑器</a
			><button class="underline" on:click={() => saveText(note!.content, `${note!.title}.md`)}
				>下载 Markdown</button
			>
		</div>
		<p class="text-xs text-gray-500">
			保留原始笔记。下方可单独下载其中的 HTML、SVG 或代码；旧笔记未记录会话来源。
		</p>
		<ArtifactList content={note.content} title={note.title} />
		<details>
			<summary class="cursor-pointer text-sm">查看笔记原文</summary>
			<pre
				class="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs">{note.content}</pre>
		</details>
	{:else if entry.kind === 'file' && !busy}
		<button
			class="rounded-lg border px-3 py-2 text-xs"
			on:click={() => download({ id: entry.id, name: entry.title })}>下载原文件</button
		>
		{#if fileText !== null}
			{#if ['text/html', 'image/svg+xml'].includes(entry.content_type || '')}
				<button class="ml-3 text-xs underline" on:click={() => (preview = !preview)}
					>切换网页 / SVG 预览</button
				>
				{#if preview}<p class="text-xs text-gray-500">隔离预览：外部资源和网络请求已禁用。</p>
					<iframe
						title={entry.title}
						class="h-96 w-full rounded-xl border bg-white"
						sandbox="allow-scripts"
						referrerpolicy="no-referrer"
						srcdoc={previewDocument(fileText)}
					></iframe>{/if}
			{:else}<ArtifactList content={fileText} title={entry.title} />{/if}
			<details>
				<summary class="cursor-pointer">查看文件原文</summary>
				<pre class="max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs">{fileText}</pre>
			</details>
		{:else}<p class="text-xs text-gray-500">
				此文件请下载后查看；在线文本预览支持 2 MiB 以内的文本文件。
			</p>{/if}
	{/if}
</section>
