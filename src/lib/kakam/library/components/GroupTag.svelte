<script lang="ts">
	import type { Group } from '../types';
	import { groupTone } from '../service';
	import LibraryIcon from './LibraryIcon.svelte';
	export let group: Group | null | undefined = null;
</script>

<span class="lib-tag" data-tone={groupTone(group?.name || '')} title={group?.name || '未分组'}>
	<LibraryIcon name="folder" size={12} /><span>{group?.name || '未分组'}</span>
</span>
