import { afterEach, expect, it, vi } from 'vitest';
vi.mock('$lib/constants', () => ({ WEBUI_BASE_URL: '' }));
import { addMemory } from './api';
afterEach(() => {
	vi.unstubAllGlobals();
});
it('saves confirmed edited text as an episode with authenticated opaque provenance', async () => {
	vi.stubGlobal('localStorage', { token: 'fixture-token' });
	const fetcher = vi
		.fn()
		.mockResolvedValue(new Response(JSON.stringify({ created: true, id: 'memory-id' })));
	vi.stubGlobal('fetch', fetcher);
	const source = { external_chat_id: 'chat-id', external_message_id: 'answer-id' };
	await expect(addMemory('用户编辑后的内容', { kind: 'episode', source })).resolves.toMatchObject({
		created: true
	});
	const [url, request] = fetcher.mock.calls[0];
	expect(url).toBe('/api/custom/memory');
	expect(request.headers.Authorization).toBe('Bearer fixture-token');
	expect(JSON.parse(request.body)).toEqual({
		content: '用户编辑后的内容',
		kind: 'episode',
		source
	});
});
it('does not report a rejected or duplicate memory as created', async () => {
	vi.stubGlobal('localStorage', { token: 'fixture' });
	vi.stubGlobal(
		'fetch',
		vi
			.fn()
			.mockResolvedValue(
				new Response(JSON.stringify({ detail: 'Memory was rejected' }), { status: 422 })
			)
	);
	await expect(addMemory('invalid')).rejects.toThrow('rejected');
	vi.stubGlobal(
		'fetch',
		vi.fn().mockResolvedValue(new Response(JSON.stringify({ created: false })))
	);
	expect((await addMemory('duplicate')).created).toBe(false);
});
