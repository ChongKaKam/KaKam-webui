<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { showSettings } from '$lib/stores';
	import { getNote, getFileBlob } from '../api';
	import { fileId, previewDocument, saveBlob, saveText } from '../service';
	import type { Attachment, Entry, NoteDetail } from '../types';
	import ArtifactList from './ArtifactList.svelte';
	import ChatArtifacts from './ChatArtifacts.svelte';
	export let entry: Entry;
	export let close: () => void;
	export let openChat: (id: string) => void;
	let note: NoteDetail | null = null;
	let error = '';
	let busy = true;
	let fileText: string | null = null;
	let preview = false;
	const controller = new AbortController();
	onMount(async () => {
		try {
			if (entry.kind === 'chat') return;
			if (entry.kind === 'note')
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
</script>

{#if entry.kind === 'chat'}
	<ChatArtifacts {entry} {close} {openChat} backLabel="返回文件列表" />
{:else}
	<section class="space-y-4">
		<button class="text-sm text-gray-500 hover:underline" on:click={close}>← 返回列表</button>
		<h3 class="break-words text-lg font-semibold">{note?.title || entry.title}</h3>
		{#if error}<p role="alert" class="text-sm text-red-600">{error}</p>{/if}
		{#if busy}<p role="status">正在读取…</p>{/if}
		{#if note}
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
					<pre
						class="max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs">{fileText}</pre>
				</details>
			{:else}<p class="text-xs text-gray-500">
					此文件请下载后查看；在线文本预览支持 2 MiB 以内的文本文件。
				</p>{/if}
		{/if}
	</section>
{/if}
