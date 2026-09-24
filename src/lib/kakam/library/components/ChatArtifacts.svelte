<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { getFileBlob } from '../api';
	import { collectChatAssets, saveBlob, saveText } from '../service';
	import { createChatAssetsStore } from '../store';
	import type { ChatAsset, Entry } from '../types';
	import AssetCard from './AssetCard.svelte';
	import AssetPreview from './AssetPreview.svelte';
	import GroupTag from './GroupTag.svelte';
	import LibraryIcon from './LibraryIcon.svelte';
	export let entry: Entry;
	export let close: () => void;
	export let openChat: (id: string) => void;
	export let backLabel = '返回对话 Gallery';
	const collection = createChatAssetsStore(() => localStorage.token, entry.id);
	let query = '';
	let preview: ChatAsset | null = null;
	let previewContainer: HTMLDivElement;
	let actionError = '';
	let downloading: string[] = [];
	let visible = 36;
	$: assets = collectChatAssets($collection.chat, $collection.files);
	$: filtered = assets.filter((asset) =>
		asset.title.toLocaleLowerCase().includes(query.toLocaleLowerCase())
	);
	$: generated = filtered.filter((asset) => asset.origin === 'generated');
	$: uploaded = filtered.filter((asset) => asset.origin === 'uploaded');
	$: related = filtered.filter((asset) => asset.origin === 'related');
	onMount(collection.load);
	onDestroy(collection.destroy);
	async function inspect(asset: ChatAsset) {
		preview = asset;
		await tick();
		previewContainer?.focus();
		previewContainer?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
	}
	async function download(asset: ChatAsset) {
		actionError = '';
		if (asset.artifact) {
			saveText(asset.artifact.content, asset.title, asset.mime || 'text/plain');
			return;
		}
		if (!asset.fileId) return;
		downloading = [...downloading, asset.id];
		try {
			const result = await getFileBlob(localStorage.token, asset.fileId);
			saveBlob(result.blob, result.filename || asset.title);
		} catch (e) {
			actionError = String(e);
		} finally {
			downloading = downloading.filter((id) => id !== asset.id);
		}
	}
</script>

<section class="lib-collection">
	<button class="lib-text-button lib-breadcrumb" on:click={close}
		><LibraryIcon name="back" size={15} />{backLabel}</button
	>
	<header class="lib-collection-header">
		<span class="lib-collection-icon"><LibraryIcon name="folder" size={28} /></span>
		<div class="lib-collection-title">
			<h2>{$collection.chat?.title || entry.title}</h2>
			<div class="lib-title-meta">
				<GroupTag group={$collection.chat ? $collection.chat.group : entry.group} /><span
					>对话产物</span
				>
			</div>
		</div>
		<button class="lib-button" on:click={() => openChat(entry.id)}
			>打开原对话 <LibraryIcon name="external" size={14} /></button
		>
	</header>
	<p class="lib-description">这段对话里的成果，集中在这里。选择产物即可预览或下载。</p>
	{#if $collection.error}<div class="lib-error" role="alert">
			{$collection.error}<button class="lib-text-button" on:click={collection.load}>重新加载</button
			>
		</div>{/if}
	{#if actionError}<p class="lib-error" role="alert">{actionError}</p>{/if}
	{#if $collection.loading}<div class="lib-empty" role="status">正在整理对话产物…</div>
	{:else if $collection.chat}
		{#if $collection.filesError}<div class="lib-error" role="alert">
				部分文件未能加载：{$collection.filesError}<button
					class="lib-text-button"
					on:click={collection.loadFiles}>重试文件加载</button
				>
			</div>{/if}
		{#if assets.length}
			<div class="lib-detail-toolbar">
				<span
					>{assets.length} 项{#if $collection.files.length < $collection.total}已加载{/if}</span
				><label class="lib-search"
					><LibraryIcon name="search" size={16} /><input
						aria-label="搜索对话产物"
						placeholder="搜索产物名称…"
						bind:value={query}
						on:input={() => (visible = 36)}
					/><span class="sr-only">搜索产物名称</span></label
				>
			</div>
		{/if}
		{#if preview}<div bind:this={previewContainer} tabindex="-1" class="lib-preview-container">
				{#key preview.id}<AssetPreview asset={preview} close={() => (preview = null)} />{/key}
			</div>{/if}
		<section class="lib-asset-section" aria-label="生成产物">
			<div class="lib-section-heading">
				<h3>生成产物</h3>
				<span>{generated.length}</span>
			</div>
			{#if generated.length}<div class="lib-assets-grid">
					{#each generated.slice(0, visible) as asset (asset.id)}<AssetCard
							{asset}
							preview={() => inspect(asset)}
							download={() => download(asset)}
							busy={downloading.includes(asset.id)}
							openChat={() => openChat(entry.id)}
						/>{/each}
				</div>
			{:else}<div class="lib-empty lib-empty-products">
					<LibraryIcon name="file" size={28} />
					<h4>{query ? '没有匹配的产物' : '这段对话还没有生成产物'}</h4>
					<p>{query ? '试试其他名称，或清空搜索。' : '生成的网页、代码和文件会显示在这里。'}</p>
				</div>{/if}
		</section>
		{#each [{ label: '上传附件', description: '你在对话中提供的参考资料', items: uploaded }, { label: '关联文件', description: '已关联到这段对话的其他文件', items: related }] as section}
			{#if section.items.length}<details
					class="lib-secondary-assets"
					open={!!query || !generated.length}
				>
					<summary
						><span>{section.label}<span class="lib-count">{section.items.length}</span></span><span
							class="lib-summary-description">{section.description}</span
						></summary
					>
					<div class="lib-assets-grid">
						{#each section.items.slice(0, visible) as asset (asset.id)}<AssetCard
								{asset}
								preview={() => inspect(asset)}
								download={() => download(asset)}
								busy={downloading.includes(asset.id)}
								openChat={() => openChat(entry.id)}
							/>{/each}
					</div>
				</details>{/if}
		{/each}
		{#if Math.max(generated.length, uploaded.length, related.length) > visible}<button
				class="lib-button lib-load-more"
				on:click={() => (visible += 36)}>显示更多产物</button
			>{/if}
		{#if $collection.files.length < $collection.total}<button
				class="lib-button lib-load-more"
				disabled={$collection.loadingMore}
				on:click={collection.loadFiles}
				>{$collection.loadingMore
					? '加载中…'
					: `加载更多关联文件（${$collection.files.length} / ${$collection.total}）`}</button
			>{/if}
	{/if}
</section>
