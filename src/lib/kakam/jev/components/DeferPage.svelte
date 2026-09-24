<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { config, showSettings, showSidebar, user } from '$lib/stores';
	import { createJevSession } from '../store';
	import JevIcon from './JevIcon.svelte';
	import ProgressSteps from './ProgressSteps.svelte';
	import DecisionCard from './DecisionCard.svelte';
	const session = createJevSession();
	let input = '';
	let scrollArea: HTMLDivElement;
	let composer: HTMLTextAreaElement;
	let follow = true;
	let observedTurns: unknown;
	$: if ($session.turns !== observedTurns) {
		observedTurns = $session.turns;
		if (follow)
			void tick().then(() => {
				if (scrollArea) scrollArea.scrollTop = scrollArea.scrollHeight;
			});
	}
	async function submit() {
		if (await session.send(input)) {
			input = '';
			follow = true;
			await tick();
			composer?.focus();
		}
	}
	function newConversation() {
		session.clear();
		input = '';
		composer?.focus();
	}
	function keydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
			event.preventDefault();
			void submit();
		}
	}
	onMount(() => {
		void session.load($config?.default_models?.split(',')[0] || '');
		const refresh = () => {
			if (!document.hidden) void session.refreshConnection();
		};
		const changed = () => {
			void session.load();
		};
		window.addEventListener('focus', refresh);
		window.addEventListener('kakam-jev-config-changed', changed);
		const timer = setInterval(refresh, 60000);
		return () => {
			clearInterval(timer);
			window.removeEventListener('focus', refresh);
			window.removeEventListener('kakam-jev-config-changed', changed);
			session.destroy();
		};
	});
</script>

<svelte:head><title>defer to · KaKam</title></svelte:head>

<div class="defer-page">
	<header>
		<button
			class="sidebar-toggle icon-button"
			aria-label="展开侧边栏"
			on:click={() => showSidebar.set(!$showSidebar)}
			><svg
				width="19"
				height="19"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="1.6"
				aria-hidden="true"
				><rect x="3" y="4" width="18" height="16" rx="3" /><path d="M9 4v16" /></svg
			></button
		>
		<div class="connection-group">
			<button
				class="connection"
				title={$session.connection?.message || '检查连接中'}
				on:click={() => session.refreshConnection()}
				aria-label="刷新 Jev 连接状态"
				><span class="status-dot" class:connected={$session.connection?.connected}></span><strong
					>Jev</strong
				><span class="connection-label"
					>{$session.connection?.connected
						? '已连接'
						: $session.connection?.configured
							? '连接异常'
							: $session.loading
								? '连接中'
								: '未配置'}</span
				></button
			><span class="divider"></span><label class="model-selector"
				><span>润色模型</span><select
					aria-label="润色模型"
					value={$session.modelId}
					disabled={$session.running || !$session.models.length}
					on:change={(event) => session.selectModel(event.currentTarget.value)}
					>{#if !$session.models.length}<option value=""
							>{$session.loading ? '加载中…' : '暂无可用模型'}</option
						>{/if}{#each $session.models as model}<option value={model.id}>{model.name}</option
						>{/each}</select
				></label
			>
		</div>
		<button
			class="new-conversation icon-button"
			title="新对话"
			aria-label="开始新对话"
			on:click={newConversation}
			><svg
				width="19"
				height="19"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="1.6"
				aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg
			></button
		>
	</header>
	<div
		class="messages"
		bind:this={scrollArea}
		on:scroll={() => {
			follow = scrollArea.scrollHeight - scrollArea.scrollTop - scrollArea.clientHeight < 100;
		}}
	>
		<div class="conversation" class:empty={!$session.turns.length}>
			{#if !$session.turns.length}
				<div class="welcome">
					<div class="welcome-mark"><JevIcon className="size-8" /></div>
					<div class="wordmark">defer to</div>
					<h1>让判断，清晰一点。</h1>
					<p>描述你的问题、选项与判断标准。<br />Jev 给出选择、评分，或是非判断。</p>
					<div class="primitives">
						<span>Choice<span>选择</span></span><span>Score<span>评分</span></span><span
							>Noul<span>判断</span></span
						>
					</div>
				</div>
			{:else}
				{#each $session.turns as turn (turn.id)}
					<section class="turn" aria-label="一次判断">
						<div class="user-message">{turn.input}</div>
						<div class="assistant-message">
							<div class="assistant-heading">
								<span class="assistant-mark"><JevIcon /></span><strong>defer to</strong><span
									>{turn.modelName}</span
								>
							</div>
							<ProgressSteps stage={turn.stage} clarification={!!turn.clarification} />
							{#if turn.clarification}<p class="summary">{turn.clarification}</p>{/if}
							{#if turn.result}<div class="cards">
									{#each Object.entries(turn.result.response.answers) as [key, answer]}<DecisionCard
											{answer}
											display={turn.result.display[key]}
										/>{/each}
								</div>{/if}
							{#if turn.summary}<div class="reading">
									<span>结果解读</span>
									<p class="summary">{turn.summary}</p>
								</div>{/if}
							{#if turn.warning}<p class="warning" role="status">{turn.warning}</p>{/if}
							{#if turn.error}<div class="error" role="alert">
									{turn.error}<button
										disabled={$session.running}
										on:click={() => {
											input = turn.input;
											composer?.focus();
										}}>重新编辑</button
									>
								</div>{/if}
							{#if turn.result}<div class="result-meta">
									<span>{turn.result.response.model}</span><span
										>{turn.result.response.usage.input_tokens +
											turn.result.response.usage.output_tokens} Jev tokens</span
									>
								</div>
								<details>
									<summary>查看英文判断内容</summary>
									<pre>{typeof turn.result.evaluation.state === 'string'
											? turn.result.evaluation.state
											: JSON.stringify(turn.result.evaluation.state, null, 2)}</pre>
									{#each Object.entries(turn.result.evaluation.questions) as [key, question]}<div
											class="english-question"
										>
											<strong>{turn.result.display[key].title}</strong>
											<pre>{typeof question.instructions === 'string'
													? question.instructions
													: JSON.stringify(question.instructions, null, 2)}</pre>
										</div>{/each}
								</details>{/if}
						</div>
					</section>
				{/each}
			{/if}
		</div>
	</div>
	<div class="composer-area">
		{#if !$session.loading && !$session.connection?.connected}<div class="connection-notice">
				<span>{$session.connection?.message || 'Jev 尚未连接'}</span
				>{#if $user?.role === 'admin'}<button on:click={() => showSettings.set('admin:jev')}
						>配置 Jev ↗</button
					>{:else}<button on:click={() => session.refreshConnection()}>刷新状态</button>{/if}
			</div>{/if}
		{#if !$session.loading && !$session.models.length}<div class="connection-notice">
				<span>请先在模型管理中启用一个可用的 LLM，作为润色模型。</span><button
					on:click={() => session.load()}>重新加载</button
				>
			</div>{/if}
		{#if $session.error}<p class="error" role="alert">
				{$session.error}<button on:click={() => session.load()}>重试</button>
			</p>{/if}
		<form class="composer" on:submit|preventDefault={submit}>
			<textarea
				bind:this={composer}
				bind:value={input}
				aria-label="输入判断问题"
				placeholder="把问题交给 Jev…"
				rows="3"
				maxlength="12000"
				on:keydown={keydown}
			></textarea>
			<div class="composer-footer">
				<span>保留原意 · 自动转为英文</span>{#if $session.running}<button
						type="button"
						class="send"
						aria-label="停止判断"
						on:click={session.stop}><span class="stop-square"></span></button
					>{:else}<button
						type="submit"
						class="send"
						aria-label="发送判断"
						disabled={!input.trim() ||
							!$session.modelId ||
							!$session.connection?.configured ||
							$session.loading}
						><svg
							width="19"
							height="19"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6" /></svg
						></button
					>{/if}
			</div>
		</form>
		<div class="composer-hint">
			<span>Enter 发送 · Shift + Enter 换行</span><span>会话仅保留在当前页面</span>
		</div>
	</div>
</div>

<style>
	.defer-page {
		display: flex;
		flex-direction: column;
		height: 100dvh;
		flex: 1;
		min-width: 0;
		color: var(--kakam-text, #242424);
		background: transparent;
	}
	header {
		display: flex;
		flex-shrink: 0;
		gap: 0.6rem;
		align-items: center;
		padding: 1.1rem 1.4rem;
		min-height: 4.5rem;
	}
	.icon-button {
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.7rem;
		padding: 0.5rem;
	}
	.icon-button:hover {
		background: var(--kakam-surface);
	}
	.connection-group {
		display: flex;
		align-items: center;
		gap: 1rem;
		min-width: 0;
	}
	.connection {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
		flex-shrink: 0;
	}
	.connection strong {
		font-weight: 600;
	}
	.connection-label {
		font-size: 0.68rem;
		color: var(--kakam-muted);
	}
	.status-dot {
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 50%;
		background: #a3a3a3;
	}
	.connected {
		background: #10b981;
		box-shadow: 0 0 0 3px #10b98112;
	}
	.divider {
		width: 1px;
		height: 1.1rem;
		background: var(--kakam-border);
	}
	.model-selector {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		min-width: 0;
	}
	.model-selector > span {
		color: var(--kakam-muted);
		font-size: 0.68rem;
		white-space: nowrap;
	}
	select {
		min-width: 0;
		max-width: 16rem;
		font-size: 0.8rem;
		background: transparent;
		border: 0;
		padding: 0.4rem 0.2rem;
		text-overflow: ellipsis;
		outline-offset: 3px;
	}
	select option {
		background: var(--kakam-surface);
		color: var(--kakam-text);
	}
	.new-conversation {
		margin-left: auto;
	}
	.messages {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		overscroll-behavior: contain;
	}
	.conversation {
		max-width: 48rem;
		padding: 1.4rem 1.5rem 2.5rem;
		margin: auto;
	}
	.empty {
		min-height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		padding-bottom: 3rem;
	}
	.welcome {
		text-align: center;
		padding: 1rem 0;
	}
	.welcome-mark {
		display: inline-flex;
		padding: 0.9rem;
		border-radius: 1.2rem;
		background: var(--kakam-surface);
		margin-bottom: 1rem;
	}
	.wordmark {
		font-size: 0.72rem;
		letter-spacing: 0.16em;
		color: var(--kakam-muted);
		margin-bottom: 1rem;
	}
	h1 {
		font-size: clamp(1.65rem, 3vw, 2.1rem);
		font-weight: 500;
		letter-spacing: -0.035em;
	}
	.welcome p {
		font-size: 0.87rem;
		line-height: 1.9;
		color: var(--kakam-muted);
		margin: 0.9rem 0 1.5rem;
	}
	.primitives {
		display: flex;
		justify-content: center;
		gap: 1.5rem;
	}
	.primitives > span {
		display: flex;
		gap: 0.35rem;
		align-items: center;
		font-size: 0.7rem;
	}
	.primitives span span {
		color: var(--kakam-muted);
		font-size: 0.63rem;
	}
	.turn + .turn {
		margin-top: 2.5rem;
	}
	.user-message {
		margin-left: auto;
		width: fit-content;
		max-width: 88%;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-size: 0.93rem;
		line-height: 1.8;
		padding: 0.75rem 1.1rem;
		border-radius: 1.2rem 1.2rem 0.3rem 1.2rem;
		background: var(--kakam-surface);
		margin-bottom: 1.75rem;
	}
	.assistant-heading {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		margin-bottom: 0.7rem;
	}
	.assistant-mark {
		padding: 0.35rem;
		border: 1px solid var(--kakam-border);
		border-radius: 0.6rem;
	}
	.assistant-heading strong {
		font-size: 0.83rem;
		font-weight: 600;
	}
	.assistant-heading > span:last-child {
		font-size: 0.62rem;
		color: var(--kakam-muted);
		margin-left: auto;
		max-width: 45%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.cards {
		display: grid;
		gap: 0.8rem;
		margin-top: 1rem;
	}
	.summary {
		font-size: 0.91rem;
		line-height: 1.9;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		margin-top: 0.65rem;
	}
	.reading {
		margin-top: 1.2rem;
	}
	.reading > span {
		color: var(--kakam-muted);
		font-size: 0.68rem;
	}
	.result-meta {
		display: flex;
		gap: 0.8rem;
		margin-top: 1rem;
		font-size: 0.61rem;
		color: var(--kakam-muted);
	}
	details {
		margin-top: 0.5rem;
		font-size: 0.7rem;
		color: var(--kakam-muted);
	}
	summary {
		cursor: pointer;
		width: fit-content;
	}
	pre {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-family: inherit;
		font-size: 0.74rem;
		line-height: 1.8;
		margin-top: 0.7rem;
		padding: 0.7rem;
		border-radius: 0.7rem;
		background: var(--kakam-surface);
	}
	.english-question {
		margin-top: 0.75rem;
	}
	.composer-area {
		flex-shrink: 0;
		width: 100%;
		max-width: 48rem;
		padding: 0.5rem 1.5rem 1rem;
		margin: 0 auto;
	}
	.composer {
		border-radius: 1.35rem;
		background: var(--kakam-surface);
		padding: 0.7rem 0.8rem 0.6rem;
	}
	textarea {
		width: 100%;
		resize: none;
		background: transparent;
		padding: 0.3rem 0.4rem;
		font-size: 0.95rem;
		line-height: 1.7;
		outline: none;
		border: 0;
		min-height: 5rem;
		max-height: 12rem;
	}
	textarea::placeholder {
		color: var(--kakam-muted);
		opacity: 0.7;
	}
	.composer-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-left: 0.4rem;
	}
	.composer-footer > span {
		font-size: 0.65rem;
		color: var(--kakam-muted);
	}
	.send {
		width: 2rem;
		height: 2rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		background: var(--kakam-text);
		color: var(--kakam-surface);
	}
	.send:disabled {
		opacity: 0.25;
		cursor: not-allowed;
	}
	.stop-square {
		width: 0.6rem;
		height: 0.6rem;
		background: currentColor;
		border-radius: 0.1rem;
	}
	.composer-hint {
		display: flex;
		justify-content: center;
		flex-wrap: wrap;
		gap: 0.7rem;
		font-size: 0.59rem;
		color: var(--kakam-muted);
		margin-top: 0.6rem;
		opacity: 0.65;
	}
	.connection-notice {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.7rem;
		font-size: 0.72rem;
		line-height: 1.6;
		padding: 0.7rem 0.3rem;
		color: var(--kakam-muted);
	}
	.connection-notice button {
		flex-shrink: 0;
		color: var(--kakam-text);
		text-decoration: underline;
		text-underline-offset: 3px;
	}
	.error,
	.warning {
		font-size: 0.78rem;
		margin-top: 0.8rem;
		line-height: 1.7;
		color: #c97925;
	}
	.error {
		color: #d75e5e;
	}
	.error button {
		text-decoration: underline;
		margin-left: 0.7rem;
	}
	@media (max-width: 640px) {
		header {
			padding: 0.8rem 0.65rem;
			gap: 0.2rem;
		}
		.connection-group {
			gap: 0.55rem;
		}
		.connection-label {
			display: none;
		}
		.model-selector {
			flex-direction: column;
			align-items: flex-start;
			gap: 0;
		}
		.model-selector > span {
			font-size: 0.57rem;
		}
		select {
			max-width: 44vw;
			font-size: 0.72rem;
			padding: 0.15rem 0;
		}
		.conversation {
			padding: 1rem 1rem 1.5rem;
		}
		.composer-area {
			padding: 0.3rem 0.8rem max(0.7rem, env(safe-area-inset-bottom));
		}
		.empty {
			padding-bottom: 1rem;
		}
		.primitives {
			gap: 1rem;
		}
	}
</style>
