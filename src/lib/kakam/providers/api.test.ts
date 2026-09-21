import { afterEach, describe, expect, it, vi } from 'vitest';
vi.mock('$lib/constants', () => ({ OPENAI_API_BASE_URL: '/openai' }));
vi.mock('$lib/apis', () => ({ getModels: vi.fn() }));
vi.mock('$lib/apis/openai', () => ({ getOpenAIConfig: vi.fn(), updateOpenAIConfig: vi.fn() }));
import { probeProvider, reloadModelPool } from './api';
import { getModels } from '$lib/apis';
afterEach(() => {
	vi.unstubAllGlobals();
});
describe('admin provider probe', () => {
	it('refreshes the server pool while retaining enabled personal connections', async () => {
		const direct = { OPENAI_API_BASE_URLS: ['https://personal.test/v1'] };
		await reloadModelPool('session', direct);
		expect(getModels).toHaveBeenCalledWith('session', direct, false, true);
	});
	it('uses the authenticated server probe with edited credentials and abort signal', async () => {
		const fetcher = vi
			.fn()
			.mockResolvedValue(new Response(JSON.stringify({ data: [{ id: 'a' }] })));
		vi.stubGlobal('fetch', fetcher);
		const signal = new AbortController().signal;
		expect(
			await probeProvider(
				'session',
				{ url: 'https://example.test/v1/', key: 'edited-key', config: { api_type: 'responses' } },
				signal
			)
		).toEqual([{ id: 'a', name: 'a' }]);
		const [url, options] = fetcher.mock.calls[0];
		expect(url).toBe('/openai/verify');
		expect(options.signal).toBe(signal);
		expect(options.headers.Authorization).toBe('Bearer session');
		expect(JSON.parse(options.body).key).toBe('edited-key');
	});
	it('rejects authorization failures without exposing remote error contents', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(new Response('sensitive provider payload', { status: 403 }))
		);
		await expect(
			probeProvider(
				'session',
				{ url: 'https://example.test', key: '', config: {} },
				new AbortController().signal
			)
		).rejects.toThrow('API Key');
	});
});
