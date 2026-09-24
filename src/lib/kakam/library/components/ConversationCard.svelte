<script lang="ts">
	import type { Entry } from '../types';
	import GroupTag from './GroupTag.svelte';
	import LibraryIcon from './LibraryIcon.svelte';
	export let entry: Entry;
	export let open: () => void;
</script>

<button class="lib-conversation-card" on:click={open} aria-label={`查看 ${entry.title} 的产物`}>
	<div class="lib-card-cover" aria-hidden="true">
		<div class="lib-paper lib-paper-back"></div>
		<div class="lib-paper"><LibraryIcon name="file" size={25} /><span></span><span></span></div>
		<span class="lib-cover-caption">对话合集</span>
	</div>
	<div class="lib-card-body">
		<h3>{entry.title}</h3>
		<div class="lib-card-tags">
			<GroupTag group={entry.group} />{#if entry.archived}<span class="lib-muted-tag">已归档</span
				>{/if}
		</div>
		<div class="lib-card-footer">
			<time datetime={new Date(entry.updated_at * 1000).toISOString()}
				>{new Date(entry.updated_at * 1000).toLocaleDateString('zh-CN', {
					month: 'short',
					day: 'numeric'
				})} 更新</time
			><LibraryIcon name="arrow" size={16} />
		</div>
	</div>
</button>
