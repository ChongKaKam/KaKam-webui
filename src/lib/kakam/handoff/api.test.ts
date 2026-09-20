import { afterEach, describe, expect, it, vi } from 'vitest';
vi.mock('$lib/constants', () => ({ WEBUI_BASE_URL: '' }));
import { generateHandoff } from './api';
afterEach(() => {
	vi.unstubAllGlobals();
});
describe('ephemeral handoff request', () => {
	it('uses authentication, model effort and cancellation without chat writes or inherited tools', async () => {
		vi.stubGlobal('localStorage', { token: 'test-token' });
		const fetcher = vi
			.fn()
			.mockResolvedValue(
				new Response(JSON.stringify({ choices: [{ message: { content: '# Done' } }] }))
			);
		vi.stubGlobal('fetch', fetcher);
		const controller = new AbortController();
		expect(
			await generateHandoff(
				{ id: 'gpt-6-astra', owned_by: 'openai' },
				'source',
				{ kakam_effort: { 'gpt-6-astra': 'extra high' }, tools: ['unwanted'] },
				controller.signal
			)
		).toBe('# Done');
		const [url, options] = fetcher.mock.calls[0];
		const body = JSON.parse(options.body);
		expect(url).toBe('/api/chat/completions');
		expect(options.signal).toBe(controller.signal);
		expect(options.headers.Authorization).toBe('Bearer test-token');
		expect(body._kakam_reasoning_effort).toBe('xhigh');
		expect(body).not.toHaveProperty('chat_id');
		expect(body).not.toHaveProperty('parent_id');
		expect(body.params).not.toHaveProperty('tools');
		expect(body.tool_ids).toEqual([]);
	});
	it('reports permission failures and lets callers handle cancellation', async () => {
		vi.stubGlobal('localStorage', { token: 'test-token' });
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 403 })));
		await expect(
			generateHandoff({ id: 'unknown' }, 'source', {}, new AbortController().signal)
		).rejects.toThrow('无权');
		vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('Cancelled', 'AbortError')));
		await expect(
			generateHandoff({ id: 'unknown' }, 'source', {}, new AbortController().signal)
		).rejects.toHaveProperty('name', 'AbortError');
	});
});
