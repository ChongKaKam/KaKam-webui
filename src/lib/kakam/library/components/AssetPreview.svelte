<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { getFileBlob } from '../api';
	import { previewDocument } from '../service';
	import type { ChatAsset } from '../types';
	import LibraryIcon from './LibraryIcon.svelte';
	export let asset: ChatAsset;
	export let close: () => void;
	let text = asset.artifact?.content ?? '';
	let imageUrl = '';
	let error = '';
	let busy = !asset.artifact;
	let source = false;
	const controller = new AbortController();
	$: document = ['text/html', 'image/svg+xml'].includes(asset.mime || '');
	onMount(async () => {
		if (asset.artifact || !asset.fileId) return;
		try {
			const result = await getFileBlob(localStorage.token, asset.fileId, controller.signal);
			if (result.blob.size > 2 * 1024 * 1024)
				throw new Error('文件超过在线预览大小，请下载后查看。');
			if (controller.signal.aborted) return;
			if (asset.mime?.startsWith('image/') && !document)
				imageUrl = URL.createObjectURL(result.blob);
			else text = await result.blob.text();
		} catch (e) {
			if (!controller.signal.aborted) error = String(e);
		} finally {
			busy = false;
		}
	});
	onDestroy(() => {
		controller.abort();
		if (imageUrl) URL.revokeObjectURL(imageUrl);
	});
</script>

<section class="lib-preview" aria-label="产物预览">
	<div class="lib-preview-heading">
		<div>
			<span class="lib-eyebrow">产物预览</span>
			<h3>{asset.title}</h3>
		</div>
		<button class="lib-icon-button" aria-label="关闭预览" on:click={close}
			><LibraryIcon name="close" /></button
		>
	</div>
	{#if busy}<p class="lib-empty" role="status">正在加载预览…</p>
	{:else if error}<p class="lib-error" role="alert">{error}</p>
	{:else if imageUrl}<img class="lib-image-preview" src={imageUrl} alt={asset.title} />
	{:else}
		{#if document}<div class="lib-preview-toolbar">
				<button class="lib-text-button" on:click={() => (source = !source)}
					>{source ? '查看效果' : '查看源码'}</button
				><span>预览不加载外部资源</span>
			</div>{/if}
		{#if document && !source}<iframe
				title={asset.title}
				sandbox="allow-scripts"
				referrerpolicy="no-referrer"
				srcdoc={previewDocument(text)}
			></iframe>
		{:else}<pre aria-label="产物源码">{text}</pre>{/if}
	{/if}
</section>
