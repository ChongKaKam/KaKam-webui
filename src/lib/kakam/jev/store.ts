import { get, writable } from 'svelte/store';
import { getJevStatus, getPromptModels, runJevTurn } from './api';
import { conversation } from './service';
import type { SessionState, Turn, TurnEvent } from './types';

export function createJevSession() {
	const state = writable<SessionState>({
		turns: [],
		running: false,
		loading: true,
		error: '',
		models: [],
		modelsLoaded: false,
		modelId: '',
		connection: null
	});
	let controller: AbortController | null = null;
	const lifetime = new AbortController();
	let refreshing = false;
	const change = (id: string, values: Partial<Turn>) =>
		state.update((s) => ({
			...s,
			turns: s.turns.map((t) => (t.id === id ? { ...t, ...values } : t))
		}));

	async function refreshConnection() {
		if (refreshing || lifetime.signal.aborted) return;
		refreshing = true;
		try {
			const connection = await getJevStatus(lifetime.signal);
			if (!lifetime.signal.aborted) state.update((s) => ({ ...s, connection }));
		} catch {
			if (!lifetime.signal.aborted)
				state.update((s) => ({
					...s,
					connection: {
						configured: s.connection?.configured ?? false,
						connected: false,
						model: 'jev-latest',
						checked_at: Date.now() / 1000,
						message: '无法获取连接状态，请刷新重试。'
					}
				}));
		} finally {
			refreshing = false;
		}
	}

	async function load(preferred = '') {
		state.update((s) => ({ ...s, loading: true, modelsLoaded: false, error: '' }));
		await Promise.all([
			refreshConnection(),
			getPromptModels(lifetime.signal)
				.then(({ models }) => {
					state.update((s) => ({
						...s,
						models,
						modelsLoaded: true,
						modelId: models.some((m) => m.id === s.modelId)
							? s.modelId
							: models.find((m) => m.id === preferred)?.id || models[0]?.id || ''
					}));
				})
				.catch(() => {
					if (!lifetime.signal.aborted)
						state.update((s) => ({ ...s, error: '润色模型列表加载失败，请重试。' }));
				})
		]);
		if (!lifetime.signal.aborted) state.update((s) => ({ ...s, loading: false }));
	}

	async function send(input: string) {
		const current = get(state);
		input = input.trim();
		if (
			!input ||
			current.running ||
			current.loading ||
			!current.modelsLoaded ||
			!current.modelId ||
			!current.connection?.configured
		)
			return false;
		let messages;
		try {
			messages = conversation(current.turns, input);
		} catch (error) {
			state.update((s) => ({ ...s, error: (error as Error).message }));
			return false;
		}
		const id = crypto.randomUUID();
		const active = new AbortController();
		controller = active;
		state.update((s) => ({
			...s,
			error: '',
			running: true,
			turns: [
				...s.turns,
				{
					id,
					input,
					modelName: current.models.find((m) => m.id === current.modelId)?.name || current.modelId,
					stage: 'preparing',
					startedAt: Date.now()
				}
			]
		}));
		const receive = (event: TurnEvent) => {
			if (active.signal.aborted) return;
			switch (event.type) {
				case 'stage':
					change(id, { stage: event.stage });
					break;
				case 'result':
					change(id, { result: event });
					state.update((s) => ({
						...s,
						connection: {
							configured: true,
							connected: true,
							model: event.response.model,
							checked_at: Date.now() / 1000,
							message: 'Jev 已完成判断'
						}
					}));
					break;
				case 'summary':
					change(id, { summary: event.summary });
					break;
				case 'clarification':
					change(id, { clarification: event.message });
					break;
				case 'warning':
					change(id, { warning: event.message });
					break;
				case 'error':
					change(id, { stage: 'error', error: event.message });
					if (['authentication', 'unavailable', 'not_configured'].includes(event.code)) {
						state.update((s) => ({
							...s,
							connection: {
								configured: event.code !== 'not_configured',
								connected: false,
								model: 'jev-latest',
								checked_at: Date.now() / 1000,
								message: event.message
							}
						}));
					}
					break;
			}
		};
		void runJevTurn(current.modelId, messages, active.signal, receive)
			.catch((error) =>
				change(
					id,
					active.signal.aborted
						? { stage: 'cancelled' }
						: { stage: 'error', error: (error as Error).message }
				)
			)
			.finally(() => {
				if (controller === active) {
					controller = null;
					state.update((s) => ({ ...s, running: false }));
				}
			});
		return true;
	}

	function stop() {
		controller?.abort();
	}
	function clear() {
		stop();
		controller = null;
		state.update((s) => ({ ...s, turns: [], running: false, error: '' }));
	}
	return {
		subscribe: state.subscribe,
		load,
		send,
		stop,
		clear,
		refreshConnection,
		selectModel: (modelId: string) => state.update((s) => ({ ...s, modelId })),
		destroy: () => {
			stop();
			lifetime.abort();
		}
	};
}
