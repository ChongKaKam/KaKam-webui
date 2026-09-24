<script lang="ts">
	import { extractArtifacts, previewDocument, saveText } from '../service';
	import type { Artifact } from '../types';
	export let content: string;
	export let title = 'artifact';
	let preview: Artifact | null = null;
	$: artifacts = extractArtifacts(content, title);
</script>

{#if artifacts.length}
	<div class="mt-3 space-y-2">
		{#each artifacts as artifact}
			<div class="flex flex-wrap items-center gap-2 rounded-xl bg-gray-50 p-3 dark:bg-gray-900">
				<span class="min-w-0 flex-1 break-all text-xs">{artifact.name}</span>
				{#if artifact.preview}<button
						class="text-xs underline"
						on:click={() => (preview = preview === artifact ? null : artifact)}>预览</button
					>{/if}
				<button
					class="rounded-lg border px-3 py-1 text-xs dark:border-gray-700"
					on:click={() => saveText(artifact.content, artifact.name, artifact.mime)}>下载</button
				>
			</div>
		{/each}
		{#if preview}
			<p class="text-xs text-gray-500">
				隔离预览：外部资源和网络请求已禁用。下载后的文件保留原始代码。
			</p>
			<iframe
				title={preview.name}
				class="h-80 w-full rounded-xl border bg-white"
				sandbox="allow-scripts"
				referrerpolicy="no-referrer"
				srcdoc={previewDocument(preview.content)}
			></iframe>
		{/if}
	</div>
{/if}
