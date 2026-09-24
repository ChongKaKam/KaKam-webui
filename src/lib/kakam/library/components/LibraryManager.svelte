<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { showSettings } from '$lib/stores';
	import { getGroups } from '../api';
	import { createLibraryStore } from '../store';
	import type { Entry, Group, Kind } from '../types';
	import ConversationCard from './ConversationCard.svelte';
	import ChatArtifacts from './ChatArtifacts.svelte';
	import ResourceManager from './ResourceManager.svelte';
	import LibraryIcon from './LibraryIcon.svelte';
	import '../library.css';

	export let initialChatId = '';
	const library = createLibraryStore(() => localStorage.token);
	const controller = new AbortController();
	let view: Kind = 'chat';
	let query = '';
	let group = '';
	let groups: Group[] = [];
	let groupsError = '';
	let offset = 0;
	let detail: Entry | null = null;
	let pane: HTMLDivElement;
	let heading: HTMLHeadingElement;
	let galleryScroll = 0;
	const tabs = [
		{ id: 'chat' as const, label: '对话产物', icon: 'grid' as const },
		{ id: 'file' as const, label: '全部文件', icon: 'file' as const },
		{ id: 'note' as const, label: '笔记', icon: 'note' as const }
	];
	onMount(() => {
		library.refreshSummary();
		refreshGroups();
		load();
		if (initialChatId)
			detail = {
				id: initialChatId,
				kind: 'chat',
				title: '对话产物',
				updated_at: 0,
				size: null,
				content_type: null,
				origin: 'unknown',
				sources: [],
				archived: false
			};
	});
	onDestroy(() => {
		library.destroy();
		controller.abort();
	});
	async function refreshGroups() {
		groupsError = '';
		try {
			groups = await getGroups(localStorage.token, controller.signal);
		} catch (e) {
			if (!controller.signal.aborted) groupsError = String(e);
		}
	}
	function load() {
		library.load({
			kind: 'chat',
			q: query,
			offset,
			group_id: group && group !== '__ungrouped__' ? group : undefined,
			ungrouped: group === '__ungrouped__' ? true : undefined
		});
	}
	function filter() {
		offset = 0;
		load();
	}
	async function inspect(entry: Entry) {
		galleryScroll = pane.scrollTop;
		detail = entry;
		await tick();
		pane.scrollTop = 0;
	}
	async function close() {
		detail = null;
		await tick();
		heading?.focus({ preventScroll: true });
		pane.scrollTop = galleryScroll;
	}
	function openChat(id: string) {
		showSettings.set(false);
		goto(`/c/${encodeURIComponent(id)}`);
	}
</script>

<div id="tab-library" class="kakam-library" bind:this={pane}>
	{#if detail}
		{#key detail.id}<ChatArtifacts entry={detail} {close} {openChat} />{/key}
	{:else}
		<header class="lib-page-header">
			<div class="lib-eyebrow">
				<LibraryIcon name="folder" size={15} />个人空间<span>/</span>资料库
			</div>
			<h2 tabindex="-1" bind:this={heading}>消息与文件</h2>
			<p class="lib-description">按对话整理网页、代码和文件，随时预览或下载。</p>
		</header>
		<nav class="lib-view-tabs" aria-label="资料库视图">
			{#each tabs.filter((tab) => tab.id !== 'note' || $library.summary?.notes_enabled) as tab}
				<button
					class:active={view === tab.id}
					aria-current={view === tab.id ? 'page' : undefined}
					on:click={() => (view = tab.id)}
					><LibraryIcon name={tab.icon} size={16} />{tab.label}</button
				>
			{/each}
		</nav>
		{#if view === 'chat'}
			<form class="lib-gallery-toolbar" on:submit|preventDefault={filter}>
				<label class="lib-search"
					><LibraryIcon name="search" size={16} /><input
						aria-label="搜索对话名称"
						placeholder="搜索对话名称…"
						bind:value={query}
						maxlength="200"
					/><span class="sr-only">搜索对话名称</span></label
				>
				<button class="lib-button" type="submit">搜索</button>
				<label class="lib-group-filter"
					><LibraryIcon name="folder" size={15} /><select
						aria-label="筛选分组"
						bind:value={group}
						on:change={filter}
						><option value="">全部分组</option><option value="__ungrouped__">未分组</option
						>{#each groups as item}<option value={item.id}>{item.name}</option>{/each}</select
					></label
				>
				<button
					type="button"
					class="lib-icon-button"
					title="刷新资料库"
					aria-label="刷新资料库"
					disabled={$library.loading}
					on:click={() => {
						load();
						refreshGroups();
						library.refreshSummary();
					}}><LibraryIcon name="refresh" size={17} /></button
				>
			</form>
			{#if groupsError}<div class="lib-error" role="alert">
					分组加载失败。<button class="lib-text-button" on:click={refreshGroups}>重试</button>
				</div>{/if}
			<div class="lib-gallery-caption">
				<span
					>对话 Gallery <span class="lib-count">{$library.loading ? '…' : $library.page.total}</span
					></span
				><span>最近更新优先</span>
			</div>
			{#if $library.error}<div class="lib-error" role="alert">
					{$library.error}<button class="lib-text-button" on:click={load}>重新加载</button>
				</div>
			{:else if $library.loading}<div
					class="lib-gallery"
					aria-label="正在加载对话"
					aria-busy="true"
				>
					{#each [1, 2, 3, 4, 5, 6] as item (item)}<div class="lib-skeleton" aria-hidden="true">
							<div></div>
							<span></span><span></span>
						</div>{/each}
				</div>
			{:else if !$library.page.items.length}<div class="lib-empty lib-empty-gallery">
					<LibraryIcon name="folder" size={38} />
					<h3>{query || group ? '没有找到匹配的对话' : '从一段对话，开始积累成果'}</h3>
					<p>
						{query || group
							? '试试其他名称或分组。'
							: '保存的对话会成为一张卡片，产物和附件都可以在卡片中找到。'}
					</p>
					{#if query || group}<button
							class="lib-button"
							on:click={() => {
								query = '';
								group = '';
								filter();
							}}>清空筛选</button
						>{:else}<button
							class="lib-button"
							on:click={() => {
								showSettings.set(false);
								goto('/');
							}}>开始对话 <LibraryIcon name="arrow" size={14} /></button
						>{/if}
				</div>
			{:else}<div class="lib-gallery">
					{#each $library.page.items as entry (entry.id)}<ConversationCard
							{entry}
							open={() => inspect(entry)}
						/>{/each}
				</div>{/if}
			{#if $library.page.total > 30}<div class="lib-pagination">
					<button
						class="lib-button"
						disabled={!offset || $library.loading}
						on:click={() => {
							offset -= 30;
							load();
						}}>上一页</button
					><span>第 {Math.floor(offset / 30) + 1} / {Math.ceil($library.page.total / 30)} 页</span
					><button
						class="lib-button"
						disabled={offset + 30 >= $library.page.total || $library.loading}
						on:click={() => {
							offset += 30;
							load();
						}}>下一页</button
					>
				</div>{/if}
		{:else}
			{#key view}<ResourceManager initialKind={view} />{/key}
		{/if}
	{/if}
</div>
