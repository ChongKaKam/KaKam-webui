<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { user, temporaryChatEnabled, showSettings } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Bookmark from '$lib/components/icons/Bookmark.svelte';
	import { addMemory } from '../api';
	import { canAccessMemoryPolicy, memoryPolicyTab } from '../navigation';
	import {
		rememberDraft,
		isSavedMemoryChat,
		memoryContentError,
		memoryContentLimit,
		type RememberHistory
	} from '../remember';

	export let chatId: string;
	export let messageId: string;
	export let history: RememberHistory;
	export let answer: string;
	export let visible = true;
	export let readOnly = false;
	export let failed = false;
	let show = false;
	let content = '';
	let busy = false;
	let error = '';
	let source: { external_chat_id: string; external_message_id: string } | null = null;
	$: draft = rememberDraft(history, messageId, answer);
	$: savedChat = !$temporaryChatEnabled && isSavedMemoryChat(chatId);
	$: validation = memoryContentError(content);
	function open() {
		if (!draft || !savedChat || busy) return;
		content = draft.content;
		source = { external_chat_id: chatId, external_message_id: messageId };
		error = '';
		show = true;
	}
	async function save() {
		if (busy || validation || !source) return;
		busy = true;
		error = '';
		try {
			const result = await addMemory(content.trim(), { kind: 'episode', source });
			if (!result.created) {
				error = '相同内容已存在，或仍处于删除后的去重保护期；本次未新增记忆。';
				return;
			}
			show = false;
			toast.success('已保存到个人长期记忆', {
				action: { label: '查看 Memory', onClick: () => showSettings.set(memoryPolicyTab.id) }
			});
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '记忆保存失败，请稍后重试。';
		} finally {
			busy = false;
		}
	}
</script>

{#if !readOnly && !failed && draft && canAccessMemoryPolicy($user)}
	<Tooltip
		content={savedChat ? 'Remember it · 记住这轮问答' : '请先保存聊天，再加入长期记忆'}
		placement="bottom"
	>
		<button
			type="button"
			aria-label="Remember it"
			disabled={!savedChat || busy}
			on:click={open}
			class="{visible
				? 'visible'
				: 'hover-reveal'} p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg dark:hover:text-white hover:text-black transition disabled:opacity-40 disabled:cursor-not-allowed"
		>
			<Bookmark className="w-4 h-4" strokeWidth="2.3" />
		</button>
	</Tooltip>
{/if}

<Modal
	bind:show
	size="lg"
	className="bg-white dark:bg-gray-900 rounded-3xl !min-h-0 max-h-[calc(100dvh-2rem)] flex flex-col overflow-hidden"
>
	<div class="flex shrink-0 items-center justify-between gap-3 px-5 pt-5">
		<h2 class="text-lg font-semibold">Remember it</h2>
		<button
			type="button"
			class="rounded-lg p-2 hover:bg-black/5 dark:hover:bg-white/5"
			aria-label="关闭记忆预览"
			on:click={() => (show = false)}>✕</button
		>
	</div>
	<form class="flex min-h-0 flex-col" on:submit|preventDefault={save}>
		<div class="min-h-0 overflow-y-auto overscroll-contain px-5 pt-3">
			<p class="mb-3 text-sm leading-relaxed text-gray-500">
				核对并编辑后保存到个人长期记忆，供以后相关对话召回。默认长期保留，可在 Memory 中管理或删除。
			</p>
			<p class="mb-3 text-sm leading-relaxed text-gray-500">
				仅保存这轮问答的可见文字，不含隐藏推理、附件原文件或整段历史。模型回答不会自动成为已验证事实。
			</p>
			<label class="block text-sm font-medium"
				>要记住的内容
				<textarea
					bind:value={content}
					on:input={() => (error = '')}
					disabled={busy}
					rows="12"
					class="mt-2 w-full resize-y rounded-xl border border-gray-200 bg-transparent p-3 text-base leading-relaxed dark:border-gray-700"
				></textarea>
			</label>
			<p class="my-2 text-xs text-gray-500">
				{Array.from(content.trim()).length.toLocaleString()} / {memoryContentLimit.toLocaleString()} 字
			</p>
			{#if validation}<p class="mb-2 text-sm text-amber-700 dark:text-amber-300" role="status">
					{validation}
				</p>{/if}
			{#if error}<p class="mb-2 text-sm text-red-600 dark:text-red-300" role="alert">
					{error}
				</p>{/if}
		</div>
		<div class="flex shrink-0 justify-end gap-2 border-t border-gray-100 p-5 dark:border-gray-800">
			<button
				type="button"
				class="rounded-full border border-gray-300 px-4 py-2 text-sm dark:border-gray-600"
				on:click={() => (show = false)}>取消</button
			>
			<button
				type="submit"
				disabled={busy || !!validation}
				class="rounded-full bg-black px-4 py-2 text-sm text-white disabled:opacity-40 dark:bg-white dark:text-black"
				>{busy ? '正在保存…' : '保存到长期记忆'}</button
			>
		</div>
	</form>
</Modal>
