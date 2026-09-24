<script lang="ts">
	import type { ChatAsset } from '../types';
	import { assetFormat, canPreviewAsset, formatBytes } from '../service';
	import LibraryIcon from './LibraryIcon.svelte';
	export let asset: ChatAsset;
	export let preview: () => void;
	export let download: () => void;
	export let openChat: () => void;
	export let busy = false;
</script>

<article class="lib-asset-card">
	<div class="lib-asset-top">
		<span class="lib-file-icon"
			><LibraryIcon
				name={asset.artifact ? 'code' : asset.mime?.startsWith('image/') ? 'image' : 'file'}
				size={24}
			/></span
		><span class="lib-format">{assetFormat(asset)}</span>
	</div>
	<h4 title={asset.title}>{asset.title}</h4>
	<p class="lib-asset-meta">
		{asset.artifact
			? '从对话提取'
			: asset.fileId
				? '已保存的文件'
				: '外部或临时资源'}{#if asset.size !== null}<span> · {formatBytes(asset.size)}</span>{/if}
	</p>
	<div class="lib-asset-actions">
		{#if canPreviewAsset(asset)}<button class="lib-button lib-button-small" on:click={preview}
				>预览</button
			>{/if}
		{#if asset.fileId || asset.artifact}<button
				class="lib-text-button"
				disabled={busy}
				on:click={download}
				><LibraryIcon name="download" size={14} />{busy ? '下载中…' : '下载'}</button
			>
		{:else}<button class="lib-text-button" on:click={openChat}
				>返回对话查看 <LibraryIcon name="external" size={13} /></button
			>{/if}
	</div>
</article>
