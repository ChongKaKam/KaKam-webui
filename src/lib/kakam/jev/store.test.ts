import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getJevStatus, getPromptModels, runJevTurn } from './api';
import { createJevSession } from './store';
import type { TurnEvent } from './types';

vi.mock('./api', () => ({ getJevStatus: vi.fn(), getPromptModels: vi.fn(), runJevTurn: vi.fn() }));
const connected = {
	configured: true,
	connected: true,
	model: 'jev-latest',
	checked_at: 1,
	message: 'ok'
};

beforeEach(() => {
	vi.resetAllMocks();
	vi.mocked(getJevStatus).mockResolvedValue(connected);
	vi.mocked(getPromptModels).mockResolvedValue({ models: [{ id: 'm', name: 'Prompt model' }] });
});

describe('Defer to session state', () => {
	it('distinguishes a failed model request from an empty successful list and recovers', async () => {
		const session = createJevSession();
		vi.mocked(getPromptModels).mockRejectedValueOnce(new Error('500'));
		await session.load();
		expect(get(session).modelsLoaded).toBe(false);
		expect(get(session).error).toContain('润色模型列表加载失败');
		expect(await session.send('问题')).toBe(false);
		vi.mocked(getPromptModels).mockResolvedValueOnce({ models: [] });
		await session.load();
		expect(get(session).modelsLoaded).toBe(true);
		expect(get(session).models).toEqual([]);
		expect(get(session).error).toBe('');
		await session.load();
		expect(get(session).modelId).toBe('m');
		vi.mocked(getPromptModels).mockRejectedValueOnce(new Error('500'));
		await session.load();
		expect(get(session).modelsLoaded).toBe(false);
		expect(await session.send('不能使用过期列表')).toBe(false);
		expect(runJevTurn).not.toHaveBeenCalled();
		session.destroy();
	});
	it('selects an available model and preserves Jev cards after polishing failure', async () => {
		const session = createJevSession();
		await session.load('unavailable');
		expect(get(session).modelId).toBe('m');
		vi.mocked(runJevTurn).mockImplementation(async (_id, _messages, _signal, receive) => {
			receive({
				type: 'result',
				evaluation: {
					model: 'jev-latest',
					state: 'Evidence',
					questions: { q: { type: 'noul', instructions: 'Yes?' } }
				},
				display: { q: { title: '是否', options: { true: '是', false: '否' } } },
				response: {
					model: 'jev-1.13.0',
					answers: { q: { type: 'noul', noul: 0.7 } },
					usage: { input_tokens: 10, output_tokens: 3 }
				}
			});
			receive({ type: 'warning', message: '润色失败' });
			receive({ type: 'stage', stage: 'done' });
		});
		expect(await session.send('有完整含义的输入')).toBe(true);
		await vi.waitFor(() => expect(get(session).running).toBe(false));
		expect(get(session).turns[0].result?.response.answers.q).toEqual({ type: 'noul', noul: 0.7 });
		expect(get(session).turns[0].warning).toBe('润色失败');
		session.destroy();
	});
	it('prevents overlapping submissions and clears safely during an in-flight call', async () => {
		const session = createJevSession();
		await session.load();
		let signal: AbortSignal | undefined;
		let receive: ((event: TurnEvent) => void) | undefined;
		vi.mocked(runJevTurn).mockImplementation((_id, _messages, abortSignal, onEvent) => {
			signal = abortSignal;
			receive = onEvent;
			return new Promise((_resolve, reject) =>
				abortSignal.addEventListener('abort', () =>
					reject(new DOMException('Aborted', 'AbortError'))
				)
			);
		});
		await session.send('第一个问题');
		expect(await session.send('第二个问题')).toBe(false);
		session.clear();
		expect(signal?.aborted).toBe(true);
		receive?.({ type: 'summary', summary: 'late response' });
		await Promise.resolve();
		expect(get(session).turns).toEqual([]);
		expect(get(session).running).toBe(false);
		session.destroy();
	});
	it('does not infer connection success from a configured key', async () => {
		vi.mocked(getJevStatus).mockResolvedValue({
			...connected,
			connected: false,
			message: '鉴权失败'
		});
		const session = createJevSession();
		await session.load();
		expect(get(session).connection?.connected).toBe(false);
		session.destroy();
	});
});
