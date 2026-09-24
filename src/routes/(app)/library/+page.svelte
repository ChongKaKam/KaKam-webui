<script lang="ts">
	import { page } from '$app/stores';
	import { showSidebar, mobile } from '$lib/stores';
	import LibraryManager from '$lib/kakam/library/components/LibraryManager.svelte';
</script>

<svelte:head><title>消息与文件</title></svelte:head>
<div
	class="flex h-screen max-h-[100dvh] w-full flex-col {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<header class="flex items-center gap-3 px-5 py-3">
		<button
			aria-label="切换侧边栏"
			class="rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-gray-900"
			on:click={() => showSidebar.set(!$showSidebar)}>☰</button
		><a
			href="/"
			class="text-xs text-gray-500"
			on:click={() => {
				if ($mobile) showSidebar.set(false);
			}}>返回聊天</a
		>
	</header>
	<main class="mx-auto min-h-0 w-full max-w-5xl flex-1 px-5 pb-5">
		{#key $page.url.searchParams.get('chat_id')}<LibraryManager
				initialChatId={$page.url.searchParams.get('chat_id') || ''}
			/>{/key}
	</main>
</div>
