<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { settings } from '$lib/stores';
	import { getPolicies, getMemories, addMemory, deleteMemory, probeMemory } from '../api';
	import type { Capabilities, Memory, MemoryPreferences } from '../types';
	export let saveSettings: (value: Record<string, unknown>) => void | Promise<void>;
	const dispatch = createEventDispatcher();
	let capabilities: Capabilities | null = null;
	let prefs: MemoryPreferences = { enabled: true, policy: 'default', days: 30, cache: true };
	let memories: Memory[] = [];
	let content = '';
	let error = '';
	let busy = false;
	let loading = true;
	let probeStatus = '';
	async function probe() {
		busy = true;
		probeStatus = '';
		try {
			await probeMemory();
			probeStatus = 'Memory API、数据库与 embedding 调用成功。';
		} catch (e) {
			probeStatus = `连接测试失败：${String(e)}`;
		} finally {
			busy = false;
		}
	}

	async function load() {
		loading = true;
		error = '';
		try {
			capabilities = await getPolicies();
			dispatch('availability', capabilities);
			prefs = { ...prefs, ...$settings.kakamMemory };
			if (capabilities.available) memories = await getMemories();
		} catch (e) {
			error = String(e);
		} finally {
			loading = false;
		}
	}

	async function save() {
		busy = true;
		error = '';
		try {
			await saveSettings({ kakamMemory: { ...prefs } });
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}

	async function add() {
		busy = true;
		error = '';
		try {
			const result = await addMemory(content);
			if (!result.created) error = '该记忆已存在或已被遗忘，不会重复添加。';
			else content = '';
			memories = await getMemories();
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}

	async function forget(id: string) {
		busy = true;
		error = '';
		try {
			await deleteMemory(id);
			memories = memories.filter((m) => m.id !== id);
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
	onMount(load);
</script>

<section class="mb-5 space-y-3 text-xs" aria-label="KaKam Memory 设置">
	<div class="flex items-center justify-between">
		<span class="font-medium">KaKam Memory</span><span class="text-gray-500"
			>Manager · default v2</span
		>
	</div>
	{#if loading}
		<p class="text-gray-500">正在检查 Memory 服务…</p>
	{:else if !capabilities}
		<p class="text-amber-600">无法读取 Memory 配置，请检查连接后重试。</p>
	{:else if !capabilities.enabled}
		<p class="text-gray-500">
			服务尚未启用。请部署独立 Memory 服务并设置 KAKAM_MEMORY_ENABLED=true。
		</p>
	{:else}
		{#if !capabilities.available}<p role="status" class="text-amber-600">
				Memory 服务不可用，聊天会继续运行。恢复后点击重试。
			</p>{/if}
		<label class="flex justify-between"
			>使用长期记忆<input
				type="checkbox"
				bind:checked={prefs.enabled}
				disabled={busy}
				on:change={save}
			/></label
		>
		<label class="flex items-center justify-between"
			>Memory policy
			<select
				class="rounded border border-gray-200 bg-transparent p-1 dark:border-gray-700"
				bind:value={prefs.policy}
				disabled={busy || !capabilities.available}
				on:change={save}
			>
				{#each capabilities.policies as policy}<option value={policy.id}
						>{policy.name} ({policy.id})</option
					>{/each}
			</select>
		</label>
		<label class="flex items-center justify-between"
			>近期召回优先窗口
			<select
				class="rounded border border-gray-200 bg-transparent p-1 dark:border-gray-700"
				bind:value={prefs.days}
				disabled={busy}
				on:change={save}
			>
				{#each [7, 14, 30] as days}<option value={days}>优先最近 {days} 天</option>{/each}
			</select>
		</label>
		<label class="flex justify-between"
			>复用召回缓存<input
				type="checkbox"
				bind:checked={prefs.cache}
				disabled={busy}
				on:change={save}
			/></label
		>
		<p class="text-gray-500 leading-relaxed">
			记忆默认长期保留；此窗口只影响召回优先级，不会删除旧记忆。置顶、稳定偏好和高度相关的旧记忆仍可召回。
			System → 长期记忆 → 当前分支的 Session 历史 → 当前
			Prompt。临时聊天不读写长期记忆。只有主动保存或确认模型建议才会写入。每个会话的优先/排除、压缩、分类和集合在
			Context 侧栏管理。
		</p>
		<button type="button" class="underline" disabled={busy} on:click={probe}
			>测试真实服务连接</button
		>
		{#if probeStatus}<p role="status" class="text-gray-500">{probeStatus}</p>{/if}
		{#if capabilities.available}
			<div class="border-t border-gray-200 pt-3 dark:border-gray-800">
				<label class="block mb-2" for="kakam-memory-content">添加长期记忆</label>
				<textarea
					id="kakam-memory-content"
					class="w-full rounded border border-gray-200 bg-transparent p-2 dark:border-gray-700"
					bind:value={content}
					maxlength="2000"
					rows="2"
					placeholder="例如：我偏好中文回答"
				></textarea>
				<button
					type="button"
					class="mt-1 rounded border px-3 py-1 disabled:opacity-40"
					disabled={busy || !content.trim()}
					on:click={add}>保存记忆</button
				>
			</div>
			<div class="space-y-2 max-h-56 overflow-y-auto">
				{#each memories as memory (memory.id)}
					<div
						class="flex items-start justify-between gap-3 border-b border-gray-100 py-2 dark:border-gray-800"
					>
						<div>
							<p class="whitespace-pre-wrap break-words">{memory.content}</p>
							<small class="text-gray-500"
								>{memory.kind} · {memory.expires_at
									? `到期 ${new Date(memory.expires_at).toLocaleDateString()}`
									: '长期保留'}</small
							>
						</div>
						<button
							type="button"
							class="shrink-0 text-gray-500 hover:text-red-500"
							disabled={busy}
							on:click={() => forget(memory.id)}>遗忘</button
						>
					</div>
				{:else}<p class="text-gray-500">尚无长期记忆，Session 历史仍会用于当前对话。</p>{/each}
			</div>
		{/if}
	{/if}
	{#if error}<p role="alert" class="text-red-500">{error}</p>{/if}
	{#if !loading && (!capabilities?.available || error)}<button
			type="button"
			class="underline"
			on:click={load}>重试</button
		>{/if}
</section>
