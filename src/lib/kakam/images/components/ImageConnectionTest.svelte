<script lang="ts">
	import { onDestroy } from 'svelte';
	import { probeImages } from '../api';
	import { imageProbeDraft } from '../service';
	import type { ImageProbeDraft, ImageProbeResult } from '../types';
	export let config: Record<string, unknown>;
	export let target: 'generation' | 'edit' = 'generation';
	export let selectedModel = '';
	let draft: ImageProbeDraft | null = null;
	let draftError = '';
	let result: ImageProbeResult | null = null;
	let error = '';
	let busy: 'models' | 'generate' | null = null;
	let request: AbortController | null = null;
	let checked = '';
	let generated = false;
	let search = '';
	$: {
		try {
			draft = imageProbeDraft(config, target);
			draftError = '';
		} catch (cause) {
			draft = null;
			draftError = (cause as Error).message;
		}
	}
	$: fingerprint = JSON.stringify(draft);
	$: if (checked && checked !== fingerprint) {
		request?.abort();
		request = null;
		busy = null;
		result = null;
		generated = false;
		error = '';
		checked = '';
	}
	$: visible = (result?.models ?? []).filter((model) =>
		`${model.id} ${model.name}`.toLowerCase().includes(search.toLowerCase())
	);
	async function run(action: 'models' | 'generate') {
		if (!draft || busy) return;
		const snapshot = draft;
		const controller = new AbortController();
		request = controller;
		busy = action;
		error = '';
		checked = fingerprint;
		if (action === 'models') result = null;
		else generated = false;
		const timeout = setTimeout(() => controller.abort(), action === 'generate' ? 130000 : 30000);
		try {
			const response = await probeImages(localStorage.token, snapshot, action, controller.signal);
			if (request !== controller || checked !== fingerprint) return;
			if (action === 'models') result = response;
			else generated = response.generated === true;
		} catch (cause) {
			if (request === controller)
				error = controller.signal.aborted
					? action === 'generate'
						? '测试超时或已停止；生成请求可能已被处理，重试可能再次计费。'
						: '连接测试超时，请稍后重试。'
					: cause instanceof Error
						? cause.message
						: '连接测试失败。';
		} finally {
			clearTimeout(timeout);
			if (request === controller) {
				request = null;
				busy = null;
			}
		}
	}
	onDestroy(() => {
		request?.abort();
		request = null;
	});
</script>

{#if draft || draftError}
	<div
		class="image-connection-test"
		aria-label={target === 'generation' ? '图片生成连接验证' : '图片编辑连接验证'}
	>
		<h4>连接与模型验证</h4>
		<p>
			使用当前填写的配置测试，无需先保存。修改配置后请重新测试。读取模型列表不生成图片；列表中可见不代表具备图片生成或编辑权限。
		</p>
		<div class="actions">
			<button
				type="button"
				disabled={!!busy || !draft?.base_url || !!draftError}
				on:click={() => run('models')}
				>{busy === 'models' ? '正在读取…' : '测试连接并读取模型'}</button
			>
			{#if target === 'generation'}<button
					type="button"
					disabled={!!busy || !draft?.base_url || !draft?.model || !!draftError}
					on:click={() => run('generate')}
					>{busy === 'generate' ? '正在生成验证…' : '验证生成（可能计费）'}</button
				>{/if}
		</div>
		{#if target === 'generation'}<p>
				生成验证会用所选模型生成 1
				张测试图，可能产生费用。只检查返回结果，不保存图片或聊天；与正式生成使用相同的尺寸及附加参数。关闭窗口或修改配置不保证取消供应商已收到的生成请求。
			</p>{/if}
		{#if busy}<p role="status">
				{busy === 'generate' ? '正在等待供应商返回测试图片…' : '正在验证地址、密钥和模型列表…'}
			</p>{/if}
		{#if result}
			<p role="status">
				连接成功，发现 {result.models?.length ?? 0} 个模型。{result.model_status === 'available'
					? '当前模型已在列表中找到。'
					: result.model_status === 'not_listed'
						? '当前模型未在列表中找到，请核对名称或权限。'
						: '尚未确认当前模型。'}{!result.complete
					? '供应商列表不完整，未找到的模型不能据此判定为不可用。'
					: ''}
			</p>
			{#if result.models?.length}
				<label
					>筛选模型<input type="search" bind:value={search} placeholder="模型名称或 ID" /></label
				>
				<div class="model-options" role="group" aria-label="探测到的模型">
					{#each visible.slice(0, 100) as model (model.id)}<button
							type="button"
							disabled={!!busy}
							on:click={() => (selectedModel = model.id)}>{model.id}<span>使用此模型</span></button
						>{/each}
				</div>
				{#if visible.length > 100}<p>当前显示前 100 项，请搜索缩小范围。</p>{/if}
			{/if}
		{/if}
		{#if generated}<p role="status">生成验证通过：供应商已返回图片数据或图片链接。</p>{/if}
		{#if error || draftError}<p role="alert" class="error">{draftError || error}</p>{/if}
	</div>
{/if}

<style>
	.image-connection-test {
		margin-top: 1rem;
		padding: 1rem;
		border: 1px solid #8884;
		border-radius: 0.875rem;
	}
	h4 {
		font-size: 0.875rem;
		font-weight: 600;
	}
	p {
		font-size: 0.8125rem;
		line-height: 1.6;
		color: var(--kakam-muted, #888);
		margin: 0.6rem 0;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	button,
	input {
		border: 1px solid #8885;
		border-radius: 0.6rem;
		padding: 0.5rem 0.75rem;
		font-size: 0.875rem;
		background: transparent;
	}
	button:disabled {
		opacity: 0.5;
	}
	input {
		display: block;
		width: 100%;
		margin-top: 0.25rem;
	}
	label {
		font-size: 0.8125rem;
	}
	.model-options {
		max-height: 10rem;
		overflow-y: auto;
		overscroll-behavior: contain;
		margin-top: 0.5rem;
	}
	.model-options button {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		width: 100%;
		border: 0;
		text-align: left;
		overflow-wrap: anywhere;
	}
	.model-options span {
		flex-shrink: 0;
		font-size: 0.75rem;
		opacity: 0.6;
	}
	.error {
		color: #c2410c;
	}
	:global(.dark) .error {
		color: #fdba74;
	}
	@media (max-width: 767px) {
		input {
			font-size: 1rem;
		}
	}
</style>
