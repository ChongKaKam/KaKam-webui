<script lang="ts">
	export let chatId: string;
	export let onClose: () => void = () => {};
</script>

<a
	href={`/library?chat_id=${encodeURIComponent(chatId)}`}
	on:click={onClose}
	class="flex h-[1.6875rem] w-full items-center gap-2 rounded-xl px-2 text-[0.8125rem] hover:bg-gray-50/40 dark:hover:bg-gray-800/40"
>
	<svg
		aria-hidden="true"
		class="size-3.5"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="1.5"><path d="M3 5h7l2 3h9v12H3z" /></svg
	>
	查看对话产物
</a>
