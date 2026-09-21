import { afterEach, expect, it, vi } from 'vitest';
vi.mock('$lib/constants', () => ({ WEBUI_BASE_URL: '' }));
import { probeImages } from './api';
const draft = {
	engine: 'openai' as const,
	base_url: 'https://images.test/v1',
	api_key: 'draft-key',
	model: 'test',
	api_version: '',
	size: '',
	method: 'predict' as const,
	params: {}
};
afterEach(() => {
	vi.unstubAllGlobals();
});
it.each(['models', 'generate'] as const)(
	'sends only the explicitly requested %s action to the authenticated BFF',
	async (action) => {
		const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ generated: true })));
		vi.stubGlobal('fetch', fetcher);
		const signal = new AbortController().signal;
		await probeImages('session-token', draft, action, signal);
		const [url, options] = fetcher.mock.calls[0];
		expect(url).toBe('/api/custom/images/probe');
		expect(options.headers.Authorization).toBe('Bearer session-token');
		expect(JSON.parse(options.body)).toEqual({ ...draft, action });
		expect(options.signal).toBe(signal);
		expect(fetcher).toHaveBeenCalledTimes(1);
	}
);
it('shows a sanitized transport error rather than a raw proxy response', async () => {
	vi.stubGlobal(
		'fetch',
		vi.fn().mockResolvedValue(new Response('secret proxy response', { status: 502 }))
	);
	await expect(
		probeImages('session', draft, 'models', new AbortController().signal)
	).rejects.toThrow('HTTP 502');
});
it('reports BFF validation errors', async () => {
	vi.stubGlobal(
		'fetch',
		vi
			.fn()
			.mockResolvedValue(new Response(JSON.stringify({ detail: '未返回图片' }), { status: 422 }))
	);
	await expect(
		probeImages('session', draft, 'generate', new AbortController().signal)
	).rejects.toThrow('未返回图片');
});
